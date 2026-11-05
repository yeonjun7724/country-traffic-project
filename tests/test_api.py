"""FastAPI 계층: 인증·워크스페이스 격리·권한 거부·계산 불가 응답·엔진 수치 동등성·업로드 흐름."""
import io

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")  # python-multipart (업로드 폼)
from fastapi.testclient import TestClient  # noqa: E402

from backend import deps  # noqa: E402
from backend.main import create_app  # noqa: E402
from logisrisk.analytics import kpi  # noqa: E402
from logisrisk.config import FIXTURE_DIR  # noqa: E402
from logisrisk.data.store import Store  # noqa: E402
from logisrisk.services import Workbench  # noqa: E402
from logisrisk.views.control_tower import default_filters  # noqa: E402

DEMO = {"X-Workspace": "demo"}
MINE = {"X-Workspace": "default"}


@pytest.fixture(scope="module")
def api(demo_store):
    s, _ = demo_store
    deps.reset_singletons(s)
    with TestClient(create_app(seed=False)) as c:
        yield c
    deps.reset_singletons(None)


@pytest.fixture()
def fresh(tmp_path):
    """빈 저장소 (업로드·권한 시나리오용). 파일 DB — TestClient 는 별도 스레드에서 실행됨."""
    s = Store(f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    deps.reset_singletons(s)
    with TestClient(create_app(seed=False)) as c:
        yield c, s
    deps.reset_singletons(None)


def test_health(api):
    assert api.get("/api/health").json()["status"] == "ok"


def test_me_and_workspaces(api):
    me = api.get("/api/me", headers=DEMO).json()
    assert me["workspace"]["id"] == "demo" and me["is_demo"] and me["has_ops_data"]
    assert {w["id"] for w in me["workspaces"]} == {"default", "demo"}
    assert "data.upload" in me["permissions"]


def test_unknown_workspace_forbidden(api):
    assert api.get("/api/me", headers={"X-Workspace": "other-company"}).status_code == 403


def test_overview_matches_engine(api, demo_wb):
    body = api.get("/api/control-tower/overview", headers=DEMO).json()
    assert len(body["kpis"]) == 9
    flt = default_filters(demo_wb)
    ms = kpi.compute_with_comparison(demo_wb.frames, demo_wb.fact, flt, demo_wb.targets)
    for m in body["kpis"]:
        assert m["value"] == pytest.approx(ms[m["key"]].value), m["key"]
        assert m["n"] == ms[m["key"]].n


def test_filters_change_result(api, demo_wb):
    b = demo_wb.date_bounds()
    q = {"start": b[0].date().isoformat(), "end": b[1].date().isoformat(), "carriers": ["DEMO운송A"]}
    body = api.get("/api/control-tower/overview", headers=DEMO, params=q).json()
    flt = kpi.Filters(start=b[0].date(), end=b[1].date(), carriers=["DEMO운송A"])
    ms = kpi.compute(demo_wb.frames, demo_wb.fact, flt)
    got = {m["key"]: m for m in body["kpis"]}
    assert got["shipments"]["value"] == pytest.approx(ms["shipments"].value)
    assert got["orders"]["value"] == pytest.approx(ms["orders"].value)


def test_empty_workspace_not_computable(api):
    body = api.get("/api/control-tower/overview", headers=MINE).json()
    assert all(not m["ok"] and m["value"] is None for m in body["kpis"])
    assert api.get("/api/me", headers=MINE).json()["has_ops_data"] is False
    assert api.get("/api/control-tower/network", headers=MINE).json()["stores"] == []
    assert api.get("/api/filters", headers=MINE).json()["bounds"] is None


def test_daily_network_cts_ledger(api):
    assert len(api.get("/api/control-tower/daily", headers=DEMO).json()) > 0
    net = api.get("/api/control-tower/network", headers=DEMO).json()
    assert net["stores"] and net["warehouses"]
    assert api.get("/api/control-tower/cost-to-serve", headers=DEMO, params={"dim": "region"}).json()
    assert api.get("/api/control-tower/cost-to-serve", headers=DEMO, params={"dim": "bogus"}).status_code == 422
    led = api.get("/api/control-tower/ledger", headers=DEMO, params={"kind": "late"}).json()
    assert led["total"] >= len(led["rows"]) > 0
    sid = led["rows"][0]["store_id"]
    one = api.get("/api/control-tower/ledger", headers=DEMO, params={"kind": "late", "selected": [sid]}).json()
    assert one["rows"] and all(r["store_id"] == sid for r in one["rows"])


def test_ledger_csv_export(api):
    r = api.get("/api/control-tower/ledger.csv", headers=DEMO, params={"kind": "all"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith(b"\xef\xbb\xbf")  # utf-8-sig (Excel 한글)


def test_search(api):
    groups = api.get("/api/search", headers=DEMO, params={"q": "WH-A"}).json()
    assert any(g["entity"] == "warehouses" for g in groups)


def test_access_code_gate(fresh, monkeypatch):
    c, _ = fresh
    monkeypatch.setenv("LOGISRISK_ACCESS_CODE", "s3cret")
    assert c.get("/api/auth/status").json() == {"access_code_required": True, "authenticated": False, "locked": False}
    assert c.get("/api/me").status_code == 401
    assert c.post("/api/auth/login", json={"code": "nope"}).status_code == 401
    assert c.post("/api/auth/login", json={"code": "s3cret"}).status_code == 200
    assert c.get("/api/me").status_code == 200
    c.post("/api/auth/logout")
    assert c.get("/api/me").status_code == 401


def test_access_code_lockout(fresh, monkeypatch):
    c, _ = fresh
    monkeypatch.setenv("LOGISRISK_ACCESS_CODE", "s3cret")
    for _ in range(5):
        c.post("/api/auth/login", json={"code": "x"})
    assert c.post("/api/auth/login", json={"code": "s3cret"}).status_code == 429


def test_viewer_cannot_upload_or_export(fresh):
    c, s = fresh
    s.add_user("v1")
    s.grant("v1", "demo", "viewer")
    app = create_app(seed=False)
    app.dependency_overrides[deps.require_auth] = lambda: "v1"
    with TestClient(app) as v:
        f = {"file": ("w.csv", b"warehouse_id,name\nW1,a\n", "text/csv")}
        assert v.get("/api/me", headers=DEMO).json()["role"] == "viewer"
        assert v.post("/api/data/uploads", headers=DEMO, data={"entity": "warehouses"}, files=f).status_code == 403
        assert v.get("/api/control-tower/ledger.csv", headers=DEMO).status_code == 403
        assert v.post("/api/data/entities/orders/deactivate", headers=DEMO).status_code == 403
        assert v.get("/api/control-tower/overview", headers=DEMO).status_code == 200
        assert v.get("/api/me", headers=MINE).status_code == 403  # 멤버십 없는 워크스페이스


def _csv(name):
    return (FIXTURE_DIR / name).read_bytes()


def test_upload_validate_commit_flow(fresh):
    c, s = fresh
    up = c.post("/api/data/uploads", headers=MINE, data={"entity": "warehouses"},
                files={"file": ("wh.csv", _csv("DEMO_warehouses.csv"), "text/csv")}).json()
    assert up["n_rows"] == 3 and up["auto_mapping"]["warehouse_id"]
    # 검증 전 저장 불가
    assert c.post(f"/api/data/uploads/{up['upload_id']}/commit", headers=MINE, json={}).status_code == 409
    v = c.post(f"/api/data/uploads/{up['upload_id']}/validate", headers=MINE,
               json={"mapping": up["auto_mapping"]}).json()
    assert v["ok"] and v["n_valid"] == 3
    # 다른 워크스페이스에서는 같은 업로드에 접근 불가
    assert c.post(f"/api/data/uploads/{up['upload_id']}/commit", headers=DEMO, json={}).status_code == 404
    done = c.post(f"/api/data/uploads/{up['upload_id']}/commit", headers=MINE, json={}).json()
    assert done["version"] == 1 and done["rows"] == 3
    ents = {e["entity"]: e for e in c.get("/api/data/entities", headers=MINE).json()}
    assert ents["warehouses"]["loaded"] and not ents["warehouses"]["demo"]
    assert ents["stores"]["loaded"] is False
    # 업로드 데이터는 DEMO 로 표시되지 않음 + DEMO 워크스페이스와 섞이지 않음
    assert c.get("/api/me", headers=MINE).json()["is_demo"] is False


def test_upload_with_errors_requires_ack(fresh):
    c, _ = fresh
    for ent in ("warehouses", "stores"):
        u = c.post("/api/data/uploads", headers=MINE, data={"entity": ent},
                   files={"file": (f"{ent}.csv", _csv(f"DEMO_{ent}.csv"), "text/csv")}).json()
        c.post(f"/api/data/uploads/{u['upload_id']}/validate", headers=MINE, json={"mapping": u["auto_mapping"]})
        assert c.post(f"/api/data/uploads/{u['upload_id']}/commit", headers=MINE, json={}).status_code == 200
    u = c.post("/api/data/uploads", headers=MINE, data={"entity": "orders"},
               files={"file": ("bad.csv", _csv("DEMO_invalid_orders_for_validation.csv"), "text/csv")}).json()
    v = c.post(f"/api/data/uploads/{u['upload_id']}/validate", headers=MINE, json={"mapping": u["auto_mapping"]}).json()
    assert v["n_error_rows"] > 0 and v["error_summary"]
    err = c.get(f"/api/data/uploads/{u['upload_id']}/errors.csv", headers=MINE)
    assert err.status_code == 200 and "오류행번호".encode() in err.content
    assert c.post(f"/api/data/uploads/{u['upload_id']}/commit", headers=MINE, json={}).status_code == 409
    ok = c.post(f"/api/data/uploads/{u['upload_id']}/commit", headers=MINE, json={"acknowledge_excluded_rows": True})
    assert ok.status_code == 200 and ok.json()["rows"] == v["n_valid"]


def test_upload_rejects_bad_mapping_and_type(fresh):
    c, _ = fresh
    assert c.post("/api/data/uploads", headers=MINE, data={"entity": "warehouses"},
                  files={"file": ("x.exe", b"abc", "application/octet-stream")}).status_code == 415
    u = c.post("/api/data/uploads", headers=MINE, data={"entity": "warehouses"},
               files={"file": ("wh.csv", _csv("DEMO_warehouses.csv"), "text/csv")}).json()
    col = u["columns"][0]
    r = c.post(f"/api/data/uploads/{u['upload_id']}/validate", headers=MINE,
               json={"mapping": {"warehouse_id": col, "name": col}})
    assert r.status_code == 422
    r = c.post(f"/api/data/uploads/{u['upload_id']}/validate", headers=MINE, json={"mapping": {"nope": col}})
    assert r.status_code == 422


def test_demo_load_only_in_demo(fresh):
    c, _ = fresh
    assert c.post("/api/data/demo", headers=MINE).status_code == 403


def test_excel_sheets(fresh):
    import pandas as pd
    c, _ = fresh
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as w:
        pd.DataFrame({"x": [1]}).to_excel(w, sheet_name="메모", index=False)
        pd.read_csv(FIXTURE_DIR / "DEMO_warehouses.csv").to_excel(w, sheet_name="센터", index=False)
    u = c.post("/api/data/uploads", headers=MINE, data={"entity": "warehouses"},
               files={"file": ("wh.xlsx", buf.getvalue(), "application/vnd.ms-excel")}).json()
    assert u["sheets"] == ["메모", "센터"] and u["n_rows"] == 1
    u2 = c.put(f"/api/data/uploads/{u['upload_id']}/sheet", headers=MINE, json={"mapping": {}, "sheet": "센터"}).json()
    assert u2["n_rows"] == 3 and u2["sheet"] == "센터"


def test_datasets_activate_rollback(fresh):
    c, _ = fresh
    for _ in range(2):
        u = c.post("/api/data/uploads", headers=MINE, data={"entity": "warehouses"},
                   files={"file": ("wh.csv", _csv("DEMO_warehouses.csv"), "text/csv")}).json()
        c.post(f"/api/data/uploads/{u['upload_id']}/validate", headers=MINE, json={"mapping": u["auto_mapping"]})
        c.post(f"/api/data/uploads/{u['upload_id']}/commit", headers=MINE, json={})
    ds = c.get("/api/data/datasets", headers=MINE).json()
    v1 = next(d for d in ds if d["version"] == 1)
    assert c.post(f"/api/data/datasets/{v1['id']}/activate", headers=MINE).status_code == 204
    ents = {e["entity"]: e for e in c.get("/api/data/entities", headers=MINE).json()}
    assert ents["warehouses"]["version"] == 1
    assert c.post("/api/data/datasets/99999/activate", headers=MINE).status_code == 404


def test_quality_integrations_schema(api):
    q = api.get("/api/data/quality", headers=DEMO).json()
    assert q["entities"] and q["linkage"]
    i = api.get("/api/data/integrations", headers=DEMO).json()
    assert i["connectors"] and all(not x["configured"] for x in i["connectors"])
    sc = api.get("/api/data/schemas/orders", headers=DEMO).json()
    assert sc["primary_key"] == ["order_id"]
    assert api.get("/api/data/schemas/nope", headers=DEMO).status_code == 404
    t = api.get("/api/data/templates/orders.csv", headers=DEMO)
    assert t.status_code == 200


def test_openapi(api):
    spec = api.get("/api/openapi.json").json()
    assert "/api/control-tower/overview" in spec["paths"]


def test_workbench_cache_invalidates_on_upload(fresh):
    c, s = fresh
    assert c.get("/api/me", headers=MINE).json()["has_ops_data"] is False
    u = c.post("/api/data/uploads", headers=MINE, data={"entity": "warehouses"},
               files={"file": ("wh.csv", _csv("DEMO_warehouses.csv"), "text/csv")}).json()
    c.post(f"/api/data/uploads/{u['upload_id']}/validate", headers=MINE, json={"mapping": u["auto_mapping"]})
    c.post(f"/api/data/uploads/{u['upload_id']}/commit", headers=MINE, json={})
    assert c.get("/api/me", headers=MINE).json()["has_ops_data"] is True
    wb = Workbench.load(s, s.context_for("local", "default"), deps.get_external())
    assert "warehouses" in wb.frames
