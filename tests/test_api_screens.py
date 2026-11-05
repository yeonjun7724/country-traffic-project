"""P1/P2 화면 API: Network·Transportation·Inventory·Fuel·Scenario·Copilot·Reports·Settings."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")
from fastapi.testclient import TestClient  # noqa: E402

from backend import deps  # noqa: E402
from backend.main import create_app  # noqa: E402
from logisrisk.data.store import Store  # noqa: E402

DEMO = {"X-Workspace": "demo"}
MINE = {"X-Workspace": "default"}


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    from logisrisk.data.external import load_external
    from logisrisk.data.seed import ensure_demo_seeded
    p = tmp_path_factory.mktemp("db2") / "s.db"
    s = Store(f"sqlite:///{p.as_posix()}")
    ensure_demo_seeded(s, load_external())
    deps.reset_singletons(s)
    with TestClient(create_app(seed=False)) as c:
        yield c
    deps.reset_singletons(None)


def test_network(api):
    u = api.get("/api/network/units", headers=DEMO).json()
    assert u["available"] and len(u["units"]) == 374 and u["scenario"]["is_base"]
    w = api.get("/api/network/units", headers=DEMO, params={"freight_share": 1, "freight_volume": 0, "volatility": 0,
                                                             "imbalance": 0}).json()
    assert not w["scenario"]["is_base"] and w["scenario"]["rank_changed"] > 0
    assert api.get("/api/network/units", headers=DEMO, params={"freight_share": 0, "freight_volume": 0, "volatility": 0,
                                                                "imbalance": 0}).status_code == 422
    assert api.get("/api/network/proximity", headers=DEMO).json()[0]["units_in_radius"] >= 0
    assert api.post("/api/network/scenarios", headers=DEMO, json={}).status_code == 422  # 기본 가중치는 저장 안 함
    assert api.post("/api/network/scenarios", headers=DEMO, json={"freight_share": 1, "freight_volume": 0,
                                                                  "volatility": 0, "imbalance": 0}).status_code == 200
    assert api.get("/api/network/units.csv", headers=DEMO).status_code == 200


def test_transportation(api):
    assert api.get("/api/transportation/cts", headers=DEMO, params={"dim": "store_id"}).json()["rows"][0]["name"]
    f = api.get("/api/transportation/fuel", headers=DEMO).json()
    assert f["available"] and f["vehicles"]
    meta = api.get("/api/transportation/planning", headers=DEMO).json()
    day = meta["days"]["orders"][0]
    p = api.post("/api/transportation/plan", headers=DEMO, json={"source": "orders", "day": day, "warehouse_id": "WH-A"}).json()
    assert p["status"] == "ok" and p["proposed"]["routes"] and p["baseline"] is None
    p2 = api.post("/api/transportation/plan", headers=DEMO,
                  json={"source": "shipments", "day": meta["days"]["shipments"][-1], "warehouse_id": "WH-A"}).json()
    assert p2["comparison"]
    assert api.post("/api/transportation/plan", headers=DEMO,
                    json={"source": "orders", "day": "1999-01-01", "warehouse_id": "WH-A"}).status_code == 422
    s = api.post("/api/transportation/plan/save", headers=DEMO,
                 json={"source": "orders", "day": day, "warehouse_id": "WH-A", "name": "테스트 계획"}).json()
    sc = api.get(f"/api/scenarios/{s['id']}", headers=DEMO).json()
    assert sc["status"] == "proposed" and sc["kind"] == "route_plan"


def test_inventory(api):
    r = api.get("/api/inventory/replenishment", headers=DEMO).json()
    assert r["status"] == "ok" and r["rows"] and r["summary"]["sku_locations"] > 0
    assert api.get("/api/inventory/replenishment", headers=DEMO, params={"service_level": 1.0}).status_code == 422
    sku = api.get("/api/inventory/skus", headers=DEMO).json()[0]["value"]
    fc = api.get("/api/inventory/forecast", headers=DEMO, params={"sku": sku}).json()
    assert fc["status"] == "ok" and fc["backtest"]
    assert api.get("/api/inventory/replenishment", headers=MINE).json()["status"] == "missing"


def test_fuel(api):
    d = api.get("/api/fuel/diesel", headers=DEMO, params={"pcts": [5, 10]}).json()
    assert d["status"] == "ok" and len(d["rows"]) == 2
    m = api.get("/api/fuel/market", headers=DEMO, params={"prophet_weight": 1.0}).json()
    assert m["available"] and m["forecast"][0]["reweighted"] == pytest.approx(m["forecast"][0]["diesel_price_prophet"])
    assert api.get("/api/fuel/traffic", headers=DEMO).json()["comparison"]["pre_days"] > 0
    assert api.get("/api/fuel/audit", headers=DEMO).json()["findings"]
    assert api.get("/api/fuel/diesel", headers=MINE).json()["status"] == "missing"


def test_scenarios(api):
    body = {"a": {"name": "A", "diesel_pct": 10}, "b": {"name": "B", "demand_pct": 30}}
    c = api.post("/api/scenarios/compare", headers=DEMO, json=body).json()
    assert c["status"] == "ok" and c["rows"][0]["key"] == "total" and c["a"]["delta_pct"] > 0
    assert api.get("/api/scenarios/sensitivity", headers=DEMO).json()
    o = api.get("/api/scenarios/outage", headers=DEMO, params={"warehouse_id": "WH-A"}).json()
    assert o["status"] == "ok" and o["stores"]
    ids = api.post("/api/scenarios/compare/save", headers=DEMO, json=body).json()["ids"]
    lst = api.get("/api/scenarios", headers=DEMO).json()
    assert {i for i in ids} <= {s["id"] for s in lst}
    dup = api.post(f"/api/scenarios/{ids[0]}/duplicate", headers=DEMO, json={"name": "복제본"}).json()["id"]
    assert api.post(f"/api/scenarios/{dup}/status", headers=DEMO, json={"status": "approved"}).json()["status"] == "approved"
    x = api.get(f"/api/scenarios/{ids[0]}/excel", headers=DEMO)
    assert x.status_code == 200 and x.content[:2] == b"PK"
    assert api.get(f"/api/scenarios/{ids[0]}", headers=MINE).status_code == 404  # 워크스페이스 격리


def test_copilot_fallback(api):
    meta = api.get("/api/copilot/meta", headers=DEMO).json()
    assert len(meta["tools"]) >= 10
    r = api.post("/api/copilot/chat", headers=DEMO, json={"message": "배송 지연이 잦은 권역을 보여줘"}).json()
    assert r["mode"] in ("fallback", "llm") and "지연" in r["answer"] and r["results"]


def test_reports_alerts_actions_settings(api):
    assert api.get("/api/reports/preview", headers=DEMO).json()[0]["sheet"] == "KPI"
    assert api.get("/api/reports/preview", headers=DEMO, params={"sections": ["없는섹션"]}).status_code == 422
    assert api.get("/api/reports/excel", headers=DEMO).content[:2] == b"PK"
    h = api.get("/api/reports/summary.html", headers=DEMO)
    assert h.status_code == 200 and "경영진 요약" in h.text
    al = api.get("/api/alerts", headers=DEMO).json()
    assert al["alerts"] and "otif_min" in al["rules"]
    a = api.post("/api/actions", headers=DEMO, json={"title": "테스트 조치"}).json()["id"]
    assert api.patch(f"/api/actions/{a}", headers=DEMO, json={"status": "done", "owner": "운영팀"}).status_code == 200
    assert api.patch("/api/actions/99999", headers=DEMO, json={"status": "done"}).status_code == 404
    st = api.get("/api/settings", headers=DEMO).json()
    assert st["targets"]["otif"] == 0.95 and st["permissions"]
    t = api.put("/api/settings/targets", headers=MINE, json={"otif": 0.9, "late_rate": 0.05, "load_factor": 0.8}).json()
    assert t["otif"] == 0.9
    assert api.get("/api/settings", headers=MINE).json()["targets"]["otif"] == 0.9
    assert api.get("/api/settings", headers=DEMO).json()["targets"]["otif"] == 0.95  # 워크스페이스별 설정
    r = api.put("/api/alerts/rules", headers=DEMO, json={"otif_min": 0.8, "late_rate_max": 0.2})
    assert r.status_code == 200
    assert api.get("/api/audit", headers=DEMO).json()


def test_viewer_restrictions(api):
    s = deps.get_store()
    s.add_user("v2")
    s.grant("v2", "demo", "viewer")
    app = create_app(seed=False)
    app.dependency_overrides[deps.require_auth] = lambda: "v2"
    with TestClient(app) as v:
        assert v.get("/api/network/units", headers=DEMO).status_code == 200
        assert v.post("/api/scenarios/compare/save", headers=DEMO, json={"a": {}, "b": {}}).status_code == 403
        assert v.post("/api/copilot/chat", headers=DEMO, json={"message": "x"}).status_code == 403
        assert v.put("/api/settings/targets", headers=DEMO, json={"otif": 0.5}).status_code == 403
        assert v.get("/api/audit", headers=DEMO).status_code == 403
        assert v.get("/api/reports/excel", headers=DEMO).status_code == 403
