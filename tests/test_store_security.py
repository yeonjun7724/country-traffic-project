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
