import pandas as pd
import pytest

from logisrisk.data.store import Store
from logisrisk.data.validation import validate
from logisrisk.security import PermissionDenied, UserContext, require


def _clean_wh():
    return validate("warehouses", pd.DataFrame([{"warehouse_id": "W1", "name": "a", "lat": "37.5", "lon": "127"}])).clean


def test_commit_versions_and_activation(store):
    ctx = store.context_for("local", "default")
    d1 = store.commit_dataset(ctx, "warehouses", _clean_wh(), filename="a.csv")
    d2 = store.commit_dataset(ctx, "warehouses", _clean_wh().assign(name="b"), filename="b.csv")
    ds = store.list_datasets(ctx, "warehouses")
    assert ds.set_index("id").loc[d2, "is_active"] and not ds.set_index("id").loc[d1, "is_active"]
    assert store.active_frame(ctx, "warehouses").iloc[0]["name"] == "b"
    store.activate_dataset(ctx, d1)  # 롤백
    assert store.active_frame(ctx, "warehouses").iloc[0]["name"] == "a"


def test_atomic_rollback_on_failure(store):
    ctx = store.context_for("local", "default")
    store.commit_dataset(ctx, "warehouses", _clean_wh())
    with pytest.raises(RuntimeError):
        store.commit_dataset(ctx, "warehouses", _clean_wh().assign(name="broken"), _fail_after_insert=True)
    ds = store.list_datasets(ctx, "warehouses")
    assert len(ds) == 1  # 실패한 버전 메타데이터도 남지 않음
    assert store.active_frame(ctx, "warehouses").iloc[0]["name"] == "a"  # 이전 활성 버전 유지


def test_workspace_isolation(store):
    store.add_user("alice")
    store.add_user("bob")
    store.add_workspace("acme", "ACME")
    store.add_workspace("beta", "BETA")
    store.grant("alice", "acme", "analyst")
    store.grant("bob", "beta", "admin")
    a = store.context_for("alice", "acme")
    store.commit_dataset(a, "warehouses", _clean_wh())
    b = store.context_for("bob", "beta")
    assert store.active_frame(b, "warehouses") is None
    with pytest.raises(PermissionDenied):
        store.context_for("bob", "acme")  # 멤버십 없음
    ds_id = int(store.list_datasets(a)["id"].iloc[0])
    with pytest.raises(PermissionDenied):
        store.activate_dataset(b, ds_id)  # 타 워크스페이스 데이터셋
    sid = store.save_scenario(a, "s", "cost_scenario", {}, {}, [])
    assert store.get_scenario(b, sid) is None


def test_role_permissions(store):
    store.add_user("v")
    store.grant("v", "default", "viewer")
    v = store.context_for("v", "default")
    with pytest.raises(PermissionDenied):
        store.commit_dataset(v, "warehouses", _clean_wh())
    with pytest.raises(PermissionDenied):
        store.save_scenario(v, "x", "k", {}, {}, [])
    with pytest.raises(PermissionDenied):
        store.audit_log(v)
    store.add_user("an")
    store.grant("an", "default", "analyst")
    an = store.context_for("an", "default")
    sid = store.save_scenario(an, "plan", "route_plan", {}, {}, [], status="proposed")
    with pytest.raises(PermissionDenied):
        store.set_scenario_status(an, sid, "approved")  # 승인은 manager 이상
    with pytest.raises(PermissionDenied):
        store.save_scenario(an, "x", "k", {}, {}, [], status="approved")  # 저장 시 승인 상태 불가
    store.add_user("m")
    store.grant("m", "default", "manager")
    store.set_scenario_status(store.context_for("m", "default"), sid, "approved")
    assert store.get_scenario(an, sid)["status"] == "approved"


def test_undefined_permission_fails_closed():
    with pytest.raises(PermissionDenied):
        require(UserContext("u", "w", "admin"), "nonexistent.permission")
    with pytest.raises(PermissionDenied):
        require(None, "data.read")


def test_demo_data_only_in_demo_workspace(store):
    ctx = store.context_for("local", "default")
    with pytest.raises(PermissionDenied):
        store.commit_dataset(ctx, "warehouses", _clean_wh(), is_demo=True)


def test_settings_scenarios_persist_across_instances(tmp_path):
    url = f"sqlite:///{(tmp_path / 'p.db').as_posix()}"
    s1 = Store(url)
    c = s1.context_for("local", "default")
    s1.set_setting(c, "targets", {"otif": 0.97})
    sid = s1.save_scenario(c, "A", "cost_scenario", {"diesel_pct": 10}, {"delta_total": 1.0}, ["가정"])
    s2 = Store(url)  # 재시작 시뮬레이션
    c2 = s2.context_for("local", "default")
    assert s2.get_setting(c2, "targets") == {"otif": 0.97}
    assert s2.get_scenario(c2, sid)["params"] == {"diesel_pct": 10}
    dup = s2.duplicate_scenario(c2, sid, "A copy")
    assert s2.get_scenario(c2, dup)["status"] == "draft"
    assert not s2.audit_log(c2).empty


# ── 조치 ↔ 근거 (스키마 v2) ─────────────────────────────────────────────────
def test_v1_database_is_migrated_additively(tmp_path):
    """v1 DB(근거 컬럼 없음)를 열면 nullable 컬럼만 추가되고 기존 조치는 그대로 남는다. 다시 열어도 안전."""
    import sqlalchemy as sa

    from logisrisk.data import store as store_mod

    url = f"sqlite:///{(tmp_path / 'v1.db').as_posix()}"
    eng = sa.create_engine(url)
    with eng.begin() as c:  # v1 스키마의 조치 테이블 + 메타
        c.execute(sa.text("CREATE TABLE action_items (id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id VARCHAR(64) NOT NULL, "
                          "title VARCHAR(300) NOT NULL, source VARCHAR(200), detail TEXT, status VARCHAR(20), owner VARCHAR(64), "
                          "created_by VARCHAR(64), created_at DATETIME, updated_at DATETIME)"))
        c.execute(sa.text("CREATE TABLE schema_meta (key VARCHAR(40) PRIMARY KEY, value VARCHAR(200))"))
        c.execute(sa.text("INSERT INTO schema_meta VALUES ('schema_version', '1')"))
        c.execute(sa.text("INSERT INTO action_items (workspace_id, title, status) VALUES ('default', '기존 조치', 'open')"))
    eng.dispose()

    s = Store(url)
    cols = {c["name"] for c in sa.inspect(s.engine).get_columns("action_items")}
    assert {"ref_type", "ref_id"} <= cols
    with s.engine.connect() as c:
        assert c.execute(sa.text("SELECT value FROM schema_meta WHERE key='schema_version'")).scalar() == str(store_mod.SCHEMA_VERSION)
    ctx = s.context_for("local", "default")
    old = s.list_actions(ctx)
    assert list(old["title"]) == ["기존 조치"] and pd.isna(old.iloc[0]["ref_type"])
    s.create_action(ctx, "새 조치", "알림:KPI", ref_type="alert", ref_id="otif")
    s.engine.dispose()
    s2 = Store(url)  # 두 번째 기동: 마이그레이션 재실행 없음, 데이터 유지
    assert len(s2.list_actions(s2.context_for("local", "default"))) == 2


def test_action_refs_are_validated_and_workspace_scoped(store):
    mine, demo = store.context_for("local", "default"), store.context_for("local", "demo")
    sid = store.save_scenario(demo, "데모 시나리오", "cost_scenario", {"diesel_pct": 10}, {}, [], {})
    with pytest.raises(PermissionDenied):  # 다른 워크스페이스의 시나리오는 근거로 연결할 수 없다
        store.create_action(mine, "x", "s", ref_type="scenario", ref_id=str(sid))
    with pytest.raises(ValueError):
        store.create_action(mine, "x", "s", ref_type="email", ref_id="1")
    with pytest.raises(ValueError):
        store.create_action(mine, "x", "s", ref_type="alert")
    a1 = store.create_action(demo, "시나리오 조치", "s", ref_type="scenario", ref_id=str(sid))
    store.create_action(demo, "알림 조치", "a", ref_type="alert", ref_id="stockout")
    store.create_action(demo, "근거 없음", "-")
    linked = store.list_actions(demo, "scenario", str(sid))
    assert list(linked["id"]) == [a1]
    assert len(store.list_actions(mine, "scenario", str(sid))) == 0


# ── 저장된 보기 ─────────────────────────────────────────────────────────────
def test_saved_views_crud_permissions_and_cache_key(store):
    ctx = store.context_for("local", "default")
    rev = store.settings_revision(ctx)
    v1 = store.save_view(ctx, "호남 지연 점검", "control-tower", "?regions=%ED%98%B8%EB%82%A8&ledger=late")
    assert v1["query"] == "regions=%ED%98%B8%EB%82%A8&ledger=late"  # 앞의 ? 제거
    store.save_view(ctx, "경유가 비교", "scenario-lab", "a=10,0,0,0,1")
    assert [v["name"] for v in store.list_views(ctx)] == ["경유가 비교", "호남 지연 점검"]  # 최신 먼저
    store.save_view(ctx, "호남 지연 점검", "control-tower", "regions=x")  # 같은 이름은 덮어쓰기
    views = store.list_views(ctx)
    assert len(views) == 2 and views[0]["query"] == "regions=x"
    assert store.settings_revision(ctx) == rev  # 보기 저장은 계산 캐시 키를 바꾸지 않는다
    assert store.delete_view(ctx, views[0]["id"]) and not store.delete_view(ctx, "없음")
    assert len(store.list_views(ctx)) == 1
    assert store.list_views(store.context_for("local", "demo")) == []  # 워크스페이스별
    with pytest.raises(ValueError):
        store.save_view(ctx, "  ", "control-tower", "")
    store.add_user("vv")
    store.grant("vv", "default", "viewer")
    viewer = store.context_for("vv", "default")
    assert len(store.list_views(viewer)) == 1  # 조회는 가능
    with pytest.raises(PermissionDenied):
        store.save_view(viewer, "x", "control-tower", "")
