import math
from datetime import date

import pytest

from logisrisk.analytics import cost, kpi
from logisrisk.provenance import safe_div

FLT = kpi.Filters(start=date(2026, 1, 1), end=date(2026, 1, 3))


def test_kpis_hand_computed(mini_frames):
    fact = kpi.build_fact(mini_frames)
    m = kpi.compute(mini_frames, fact, FLT)
    assert m["orders"].value == 3
    assert m["shipments"].value == 3
    assert m["volume_kg"].value == pytest.approx(10 * 2 + 5 * 2 + 2 * 10)  # 50 kg
    assert m["cost"].value == 600
    assert m["late_rate"].value == pytest.approx(1 / 3) and m["late_rate"].denominator == 3
    # OTIF: H1 정시·완납 / H2 지연 / H3 부족(1<2)
    assert m["otif"].value == pytest.approx(1 / 3)
    # 적재율: (V1,1/1) 20+10=30/100, (V2,1/3) 20/50 → 50/150
    assert m["load_factor"].value == pytest.approx(50 / 150)
    assert any("주문중량" in w for w in m["load_factor"].warnings)
    assert m["cost_per_km"].value == pytest.approx(600 / 60)
    assert m["cost_per_order"].value == pytest.approx(200)


def test_not_computable_when_data_missing(mini_frames):
    fr = {k: v for k, v in mini_frames.items() if k != "shipments"}
    m = kpi.compute(fr, kpi.build_fact(fr), FLT)
    assert m["orders"].ok
    for k in ("otif", "cost", "load_factor", "late_rate"):
        assert m[k].status == "not_computable" and m[k].value is None
    fr2 = dict(mini_frames)
    fr2["shipments"] = mini_frames["shipments"].assign(actual_delivery_date=None)
    m2 = kpi.compute(fr2, kpi.build_fact(fr2), FLT)
    assert not m2["otif"].ok and not m2["late_rate"].ok


def test_missing_unit_weight_makes_volume_not_computable(mini_frames):
    fr = dict(mini_frames)
    fr["skus"] = mini_frames["skus"].assign(unit_weight_kg=[2.0, float("nan")])
    m = kpi.compute(fr, kpi.build_fact(fr), FLT)
    assert m["volume_kg"].status == "not_computable"


def test_filters_and_previous_period(mini_frames):
    fact = kpi.build_fact(mini_frames)
    f = kpi.Filters(start=date(2026, 1, 3), end=date(2026, 1, 3), carriers=["C2"])
    m = kpi.compute(mini_frames, fact, f)
    assert m["shipments"].value == 1 and m["cost"].value == 300
    s = kpi.Filters(start=date(2026, 1, 3), end=date(2026, 1, 4)).shifted()
    assert (s.start, s.end) == (date(2026, 1, 1), date(2026, 1, 2))
    cm = kpi.compute_with_comparison(mini_frames, fact, kpi.Filters(start=date(2026, 1, 3), end=date(2026, 1, 4)))
    assert cm["cost"].previous == 300 and cm["cost"].delta_pct == pytest.approx(0)
    cat = kpi.compute(mini_frames, fact, kpi.Filters(start=FLT.start, end=FLT.end, categories=["B"]))
    assert cat["shipments"].value == 1


def test_safe_div():
    assert safe_div(1, 0) is None and safe_div(1, float("nan")) is None and safe_div(4, 2) == 2


def test_diesel_sensitivity_and_sources(mini_frames):
    fact = kpi.build_fact(mini_frames)
    r = cost.diesel_sensitivity(fact, FLT, [10])
    # H1,H2 실측(40+120=160) · H3 연료량 = 20km/10 = 2L 이지만 단가 없음 → 제외
    assert r["n_computable"] == 2 and r["base_fuel_cost"] == pytest.approx(160)
    assert r["rows"][0]["fuel_cost_delta"] == pytest.approx(16)
    import pandas as pd
    prices = pd.DataFrame({"date": pd.to_datetime(["2026-01-01"]), "region": ["ALL"], "diesel_price": [1500.0]})
    r2 = cost.diesel_sensitivity(fact, FLT, [10], fuel_prices=prices)
    assert r2["n_computable"] == 3 and r2["price_sources"].get("기업 유가 테이블") == 1
    assert r2["base_fuel_cost"] == pytest.approx(160 + 2 * 1500)


def test_scenario_engine_contribution_sums(mini_frames):
    fact = kpi.build_fact(mini_frames)
    p = cost.ScenarioParams(diesel_pct=10, rate_pct=5, demand_pct=0)
    r = cost.scenario_engine(fact, FLT, p, mini_frames["vehicles"])
    assert r["status"] == "ok"
    assert sum(r["contribution"].values()) == pytest.approx(r["delta_total"])
    # 연료 160×10% + 비연료 (600-160)×5% (H3 연료비 미상 → 비연료로 간주)
    assert r["delta_total"] == pytest.approx(16 + 440 * 0.05)
    zero = cost.scenario_engine(fact, FLT, cost.ScenarioParams(), mini_frames["vehicles"])
    assert zero["delta_total"] == pytest.approx(0)


def test_scenario_demand_adds_trips_when_capacity_exceeded(mini_frames):
    fact = kpi.build_fact(mini_frames)
    # (V2, 1/3) 적재 20/50 → +200% = 60 > 50 → 2회 운행
    r = cost.scenario_engine(fact, FLT, cost.ScenarioParams(demand_pct=200, fleet_change=-1), mini_frames["vehicles"])
    assert r["scenario"]["trips"] == 2 + 1  # (V1,1/1) 30→90 ≤100 → 1회, V2 2회
    assert r["scenario"]["fleet"] == 1 and r["scenario"]["days_fleet_short"] >= 1


def test_scenario_no_cost_data(mini_frames):
    fr = dict(mini_frames)
    fr["shipments"] = mini_frames["shipments"].assign(total_cost=float("nan"), fuel_cost=float("nan"))
    r = cost.scenario_engine(kpi.build_fact(fr), FLT, cost.ScenarioParams(diesel_pct=10), None)
    assert r["status"] == "not_computable"


def test_warehouse_outage(mini_frames):
    r = cost.warehouse_outage(mini_frames, "W1")
    assert r["status"] == "ok"
    assert set(r["stores"]["alt_warehouse_id"]) == {"W2"}
    assert (r["stores"]["dist_change_km"] > 0).all()
    assert not math.isnan(r["capacity"].iloc[0]["utilization_after"])
    assert cost.warehouse_outage(mini_frames, "WX")["status"] == "not_computable"
