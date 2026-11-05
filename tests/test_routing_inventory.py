import numpy as np
import pandas as pd
import pytest

from logisrisk.analytics import inventory, routing

DEPOT = {"id": "W", "name": "센터", "lat": 37.5, "lon": 127.0}


def _stops(n=8, kg=100.0):
    rng = np.random.default_rng(1)
    return pd.DataFrame({"stop_id": [f"S{i}" for i in range(n)], "name": [f"s{i}" for i in range(n)],
                         "lat": 37.5 + rng.normal(0, 0.1, n), "lon": 127.0 + rng.normal(0, 0.1, n), "demand_kg": kg})


def _veh(caps, hours=10):
    return pd.DataFrame({"vehicle_id": [f"V{i}" for i in range(len(caps))], "capacity_kg": caps,
                         "fuel_efficiency_km_per_l": 5.0, "fixed_cost_per_day": 1000.0, "variable_cost_per_km": 100.0,
                         "max_hours": hours})


def test_haversine_known_distance():
    # 서울(37.5665,126.9780) - 부산(35.1796,129.0756) ≈ 325 km
    assert routing.haversine_km(37.5665, 126.9780, 35.1796, 129.0756) == pytest.approx(325, abs=5)


def test_plan_respects_capacity_and_covers_all():
    r = routing.plan_routes(DEPOT, _stops(8, 100), _veh([300, 300, 300]), routing.RoutingParams(diesel_price=1500))
    assert not r.violations and r.unassigned.empty
    assert (r.routes["load_kg"] <= r.routes["capacity_kg"] + 1e-9).all()
    assert r.routes["stops"].sum() == 8
    assert sorted(r.stops["stop_id"]) == sorted(_stops()["stop_id"])
    assert r.summary["cost_complete"]
    assert any("직선거리" in w for w in r.warnings)


def test_infeasible_reports_violations():
    r = routing.plan_routes(DEPOT, _stops(6, 100), _veh([150]), routing.RoutingParams())
    assert r.violations  # 총 수요 600 > 150
    assert len(r.unassigned) > 0
    assert set(r.unassigned["reason"]).issubset({"가용 차량 부족 또는 운행시간 제약 초과 (1차량 1회전 가정)"})
    big = _stops(2, 100)
    big.loc[0, "demand_kg"] = 1000
    r2 = routing.plan_routes(DEPOT, big, _veh([300]), routing.RoutingParams())
    assert "최대 차량 용량 초과" in r2.unassigned.iloc[0]["reason"]


def test_no_vehicles_and_missing_coords():
    s = _stops(3)
    s.loc[0, "lat"] = np.nan
    r = routing.plan_routes(DEPOT, s, _veh([])[:0], routing.RoutingParams())
    assert r.violations and len(r.unassigned) == 3
    assert "좌표 없음" in set(r.unassigned["reason"])


def test_duration_limit():
    far = pd.DataFrame({"stop_id": ["F"], "name": ["far"], "lat": [35.1], "lon": [129.0], "demand_kg": [10.0]})
    r = routing.plan_routes(DEPOT, far, _veh([300], hours=2), routing.RoutingParams(avg_speed_kmh=40))
    assert len(r.unassigned) == 1


def test_two_opt_not_worse():
    s = _stops(9)
    D = routing.distance_matrix([DEPOT["lat"], *s["lat"]], [DEPOT["lon"], *s["lon"]])
    seq = list(range(1, 10))
    assert routing._route_len(routing.two_opt(seq, D), D) <= routing._route_len(seq, D) + 1e-9


def test_compare_with_baseline():
    s = _stops(6, 50)
    assign = s.assign(vehicle_id=[f"V{i % 3}" for i in range(6)])
    v = _veh([300, 300, 300])
    p = routing.RoutingParams(diesel_price=1500)
    base = routing.baseline_plan(DEPOT, assign, v, p)
    prop = routing.plan_routes(DEPOT, s, v, p)
    c = routing.compare_plans(base, prop)
    assert base.summary["vehicles_used"] == 3 and prop.summary["vehicles_used"] == 1
    assert c.set_index("지표").loc["투입 차량", "차이"] == -2


def _inv_frames():
    days = pd.date_range("2026-01-01", periods=60)
    orders = pd.DataFrame({"order_id": [f"O{i}" for i in range(60)], "order_date": days, "warehouse_id": "W",
                           "store_id": "S", "requested_date": pd.NaT, "status": "delivered"})
    lines = pd.DataFrame({"order_id": orders["order_id"], "sku_id": "K", "qty": [10.0 if d.dayofweek < 5 else 0.0 for d in days]})
    inv = pd.DataFrame({"snapshot_date": [days[-1]], "warehouse_id": ["W"], "sku_id": ["K"], "on_hand": [20.0],
                        "allocated": [5.0], "inbound_qty": [0.0], "lead_time_days": [3.0]})
    return {"orders": orders, "order_lines": lines, "inventory": inv}


def test_replenishment_formula():
    r = inventory.replenishment(_inv_frames(), service_level=0.95, window_days=28, review_days=7)
    row = r["table"].iloc[0]
    from statistics import NormalDist
    s = pd.Series([10.0 if d.dayofweek < 5 else 0.0 for d in pd.date_range("2026-01-01", periods=60)][-28:])
    mu, sd = s.mean(), s.std(ddof=1)
    z = NormalDist().inv_cdf(0.95)
    assert row["avg_daily_demand"] == pytest.approx(mu)
    assert row["safety_stock"] == pytest.approx(z * sd * np.sqrt(3))
    assert row["reorder_point"] == pytest.approx(mu * 3 + z * sd * np.sqrt(3))
    assert row["available"] == 15
    assert row["recommended_qty"] == np.ceil(row["reorder_point"] + mu * 7 - 15)
    assert row["stockout_risk"] == "높음"


def test_replenishment_requires_inventory():
    fr = _inv_frames()
    del fr["inventory"]
    assert inventory.replenishment(fr)["status"] == "not_computable"


def test_wape_mape_zero_handling():
    a, f = np.array([0.0, 10.0, 10.0]), np.array([1.0, 8.0, 12.0])
    assert inventory.wape(a, f) == pytest.approx(5 / 20)
    m, excl = inventory.mape(a, f)
    assert m == pytest.approx(0.2) and excl == 1
    assert inventory.wape(np.zeros(3), f) is None


def test_backtest_prefers_seasonal_for_weekly_pattern():
    r = inventory.forecast_sku(_inv_frames(), "K")
    assert r["status"] == "ok"
    assert r["best"] in ("계절성 Naive(7일)", "요일평균(8주)")
    assert r["backtest"].iloc[0]["WAPE"] == pytest.approx(0, abs=1e-9)
