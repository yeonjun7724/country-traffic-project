"""2차 심층 검토에서 발견·수정한 결함의 회귀 테스트."""
import io
from datetime import date, datetime
from types import SimpleNamespace as NS

import pandas as pd
import pytest
from openpyxl import load_workbook

from conftest import mk
from logisrisk.analytics import alerts, cost, inventory, kpi, routing
from logisrisk.copilot import agent, tools
from logisrisk.data import ingest
from logisrisk.data.validation import auto_map, neutralize_formulas, read_table, validate
from logisrisk.provenance import Metric
from logisrisk.reports.export import csv_bytes, excel_report

F = kpi.Filters(start=date(2026, 1, 1), end=date(2026, 1, 3))


def _split_frames():
    return {
        "orders": mk("orders", [{"order_id": "O1", "order_date": "2026-01-01", "store_id": "S", "warehouse_id": "W"}]),
        "order_lines": mk("order_lines", [{"order_id": "O1", "sku_id": "K", "qty": 10}]),
        "shipments": mk("shipments", [
            {"shipment_id": "A", "order_id": "O1", "ship_date": "2026-01-01", "planned_delivery_date": "2026-01-02",
             "actual_delivery_date": "2026-01-02", "delivered_qty": 6, "carrier": "C1", "total_cost": 10},
            {"shipment_id": "B", "order_id": "O1", "ship_date": "2026-01-01", "planned_delivery_date": "2026-01-02",
             "actual_delivery_date": "2026-01-02", "delivered_qty": 4, "carrier": "C2", "total_cost": 10}]),
    }


# ── KPI ────────────────────────────────────────────────────────────────
def test_otif_split_shipment_counts_as_in_full():
    fr = _split_frames()
    m = kpi.compute(fr, kpi.build_fact(fr), F)
    assert m["otif"].value == 1.0 and m["otif"].denominator == 1  # 주문 단위
    assert any("분할배송" in w for w in m["otif"].warnings)


def test_otif_split_one_late_fails_order():
    fr = _split_frames()
    fr["shipments"].loc[1, "actual_delivery_date"] = pd.Timestamp("2026-01-05")
    m = kpi.compute(fr, kpi.build_fact(fr), F)
    assert m["otif"].value == 0.0


def test_orders_respect_carrier_filter():
    fr = _split_frames()
    fact = kpi.build_fact(fr)
    assert kpi.compute(fr, fact, kpi.Filters(start=F.start, end=F.end, carriers=["NONE"]))["orders"].value == 0
    assert kpi.compute(fr, fact, kpi.Filters(start=F.start, end=F.end, carriers=["C2"]))["orders"].value == 1


def test_filters_days():
    assert F.days == 3 and kpi.Filters().days is None


# ── 비용 ──────────────────────────────────────────────────────────────
def test_fuel_basis_handles_mixed_datetime_resolution():
    fr = _split_frames()
    fact = kpi.build_fact(fr).assign(fuel_l=1.0)
    fact["ship_date"] = fact["ship_date"].astype("datetime64[s]")
    fp = pd.DataFrame({"date": pd.to_datetime(["2026-01-01"]).astype("datetime64[ns]"), "region": ["ALL"],
                       "diesel_price": [1500.0]})
    x = cost.fuel_basis(fact, fp)
    assert (x["price_base"] == 1500).all() and (x["price_source"] == "기업 유가 테이블").all()


def test_demand_decrease_keeps_cost(mini_frames):
    fact = kpi.build_fact(mini_frames)
    r = cost.scenario_engine(fact, F, cost.ScenarioParams(demand_pct=-30), mini_frames["vehicles"])
    assert r["delta_total"] == pytest.approx(0)


def test_baseline_fleet_shortage_reported(mini_frames):
    fact = kpi.build_fact(mini_frames)
    r = cost.scenario_engine(fact, F, cost.ScenarioParams(fleet_change=-2), mini_frames["vehicles"])
    assert r["baseline"]["days_fleet_short"] == 0      # 기존 2대로는 부족 없음
    assert r["scenario"]["days_fleet_short"] == 2      # 0대 → 운행 있는 2일 모두 부족


# ── 알림 ──────────────────────────────────────────────────────────────
def test_monthly_budget_prorated():
    m = {"cost": Metric("cost", "총 운송비", 400.0, "원")}
    rules = {"monthly_cost_budget": 3000.0}
    assert alerts.evaluate(m, rules, {}, period_days=3)  # 3000×3/30.44≈296 < 400 → 알림
    assert not alerts.evaluate(m, rules, {}, period_days=30)  # ≈2957 > 400
    assert not alerts.evaluate(m, rules, {}, period_days=None)


# ── 검증·보안 ─────────────────────────────────────────────────────────
def test_na_tokens_become_missing():
    r = validate("stores", read_table(b"store_id,name,lat,lon,region\nS1,a,37.5,127,N/A\nS2,b,37.5,127,NULL\nS3,c,37.5,127,-\n", "s.csv"))
    assert r.clean["region"].isna().all()


def test_swapped_coordinates_explicit_error():
    r = validate("stores", pd.DataFrame([{"store_id": "S", "name": "a", "lat": "127.0", "lon": "37.5"}]))
    assert "coord_swapped" in set(r.errors["code"])


def test_formula_injection_neutralized():
    df = pd.DataFrame({"name": ['=HYPERLINK("http://x","y")', "+1", "@SUM(A1)", "정상"], "v": [-1.0, 2.0, 3.0, 4.0]})
    x = neutralize_formulas(df)
    assert x["name"].tolist()[:3] == ["'" + s for s in df["name"][:3]] and x["name"][3] == "정상"
    assert x["v"].tolist() == [-1.0, 2.0, 3.0, 4.0]  # 숫자는 그대로
    cell = load_workbook(io.BytesIO(excel_report({}, {"t": df})))["t"]["A2"].value
    assert cell.startswith("'=")
    assert csv_bytes(df).decode("utf-8-sig").splitlines()[1].startswith("\"'=")


def test_dangling_reference_warning(store):
    ctx = store.context_for("local", "default")
    st_ = validate("stores", pd.DataFrame([{"store_id": "S1", "name": "a", "lat": "37.5", "lon": "127"},
                                           {"store_id": "S2", "name": "b", "lat": "37.4", "lon": "127"}]))
    wh = validate("warehouses", pd.DataFrame([{"warehouse_id": "W", "name": "w", "lat": "37.5", "lon": "127"}]))
    store.commit_dataset(ctx, "stores", st_.clean)
    store.commit_dataset(ctx, "warehouses", wh.clean)
    od = pd.DataFrame([{"order_id": "O1", "order_date": "2026-01-01", "store_id": "S2", "warehouse_id": "W"}])
    res = ingest.validate_upload(store, ctx, "orders", od, auto_map(list(od.columns), "orders"))
    ingest.commit(store, ctx, res, filename="o.csv", mapping={})
    new = pd.DataFrame([{"store_id": "S1", "name": "a", "lat": "37.5", "lon": "127"}])  # S2 누락
    r = ingest.validate_upload(store, ctx, "stores", new, auto_map(list(new.columns), "stores"))
    assert any("주문 1건" in w and "S2" in w for w in r.warnings)


def test_settings_revision_changes(store):
    ctx = store.context_for("local", "default")
    a = store.settings_revision(ctx)
    store.set_setting(ctx, "targets", {"otif": 0.9})
    assert store.settings_revision(ctx) != a


# ── 경로 계획 ─────────────────────────────────────────────────────────
def test_open_orders_planning(demo_wb):
    days = routing.planning_days(demo_wb.frames, demo_wb.fact, "orders")
    assert days == [pd.Timestamp("2026-11-01")]
    total = 0
    for w in demo_wb.options("warehouse_id"):
        depot, stops, assign, veh = routing.build_day_inputs(demo_wb.frames, demo_wb.fact, days[0], w, source="orders")
        assert assign.empty and stops["demand_kg"].notna().all()
        total += int(stops["orders"].sum())
    assert total == 32  # DEMO 미출고 주문 수
    # 출고 완료 주문은 대상이 아님
    assert routing.due_orders(demo_wb.frames, demo_wb.fact, "2026-10-31", "WH-A").empty


def test_baseline_reports_violations():
    depot = {"id": "W", "name": "c", "lat": 37.5, "lon": 127.0}
    a = pd.DataFrame({"vehicle_id": ["V"], "stop_id": ["S"], "name": ["s"], "lat": [35.1], "lon": [129.0],
                      "demand_kg": [500.0]})
    v = pd.DataFrame({"vehicle_id": ["V"], "capacity_kg": [100.0], "fuel_efficiency_km_per_l": [5.0], "max_hours": [2.0]})
    b = routing.baseline_plan(depot, a, v, routing.RoutingParams())
    assert any("운행시간" in x for x in b.violations) and any("용량" in x for x in b.violations)


# ── 재고 ──────────────────────────────────────────────────────────────
def test_stockout_with_inbound_basis():
    days = pd.date_range("2026-01-01", periods=30)
    fr = {"orders": pd.DataFrame({"order_id": [f"O{i}" for i in range(30)], "order_date": days, "warehouse_id": "W",
                                  "store_id": "S", "requested_date": pd.NaT, "status": "delivered"}),
          "order_lines": pd.DataFrame({"order_id": [f"O{i}" for i in range(30)], "sku_id": "K", "qty": 1.0}),
          "inventory": pd.DataFrame({"snapshot_date": [days[-1]], "warehouse_id": ["W"], "sku_id": ["K"], "on_hand": [0.0],
                                     "allocated": [2.0], "inbound_qty": [100.0], "lead_time_days": [2.0]})}
    row = inventory.replenishment(fr)["table"].iloc[0]
    assert row["stockout_risk"] == "결품" and row["recommended_qty"] == 0 and "입고 일정" in row["basis"]
    with pytest.raises(ValueError):
        inventory.replenishment(fr, service_level=1.0)


def test_replenishment_scales(demo_wb):
    import time
    t = time.time()
    r = inventory.replenishment(demo_wb.frames)
    assert r["status"] == "ok" and len(r["table"]) == 120 and time.time() - t < 3


# ── Copilot ──────────────────────────────────────────────────────────
def test_period_from_text():
    b = (pd.Timestamp("2026-08-01"), pd.Timestamp("2026-10-31"))
    assert agent.period_from_text("지난달 배송비", b)[0] == {"start": "2026-09-01", "end": "2026-09-30"}
    assert agent.period_from_text("이번 달 KPI", b)[0] == {"start": "2026-10-01", "end": "2026-10-31"}
    assert agent.period_from_text("지난주 지연", b)[0] == {"start": "2026-10-19", "end": "2026-10-25"}
    assert agent.period_from_text("최근 7일 비용", b)[0] == {"start": "2026-10-25", "end": "2026-10-31"}
    assert agent.period_from_text("운송비", b) is None


def test_fallback_uses_last_month(demo_wb):
    r = agent.run(demo_wb, "지난달 배송비가 가장 많이 증가한 거래처는?", api_key="")
    res = r.tool_results[0]
    assert res["filters"].startswith("기간 2026-09-01~2026-09-30")
    assert "데이터 최신일" in res["assumptions"][0] and "2026-09-01~2026-09-30" in r.answer


def test_resolve_warehouse_by_name(demo_wb):
    assert tools.resolve_warehouse(demo_wb, "수도권") == "WH-A"
    assert tools.resolve_warehouse(demo_wb, "B") == "WH-B"
    assert tools.resolve_warehouse(demo_wb, "없는센터") is None
    r = agent.run(demo_wb, "센터 영남이 중단되면 대체 거점은?", api_key="")
    assert r.tool_results[0]["result"].get("status") != "not_computable"


def test_capacity_check_uses_open_orders(demo_wb):
    res = tools.run_tool(demo_wb, "capacity_check", {})
    assert res["result"]["date"] == "2026-11-01"
    assert any("미출고 주문" in a for a in res["assumptions"])


def test_budget_exhausted_mid_loop_no_extra_call(demo_wb):
    calls = []

    class C:
        def __init__(self):
            self.chat = NS(completions=NS(create=self.create))

        def create(self, **kw):
            calls.append(1)
            tc = NS(id="t", function=NS(name="get_kpis", arguments="{}"))
            return NS(choices=[NS(message=NS(content=None, tool_calls=[tc]))])

    r = agent.run(demo_wb, "KPI", api_key="sk", client_factory=lambda k: C(), calls_used=0, max_calls=2)
    assert len(calls) == 2 and r.llm_calls == 2 and r.mode == "fallback" and "한도" in r.notice


def test_system_prompt_includes_data_period(demo_wb):
    seen = {}

    class C:
        def __init__(self):
            self.chat = NS(completions=NS(create=self.create))

        def create(self, **kw):
            seen["sys"] = kw["messages"][0]["content"]
            return NS(choices=[NS(message=NS(content="ok", tool_calls=None))])

    agent.run(demo_wb, "질문", api_key="sk", client_factory=lambda k: C())
    assert "2026-08-01~2026-10-31" in seen["sys"] and "DEMO 여부: 예" in seen["sys"]


def test_access_gate(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("LOGISRISK_ACCESS_CODE", "s3cret")
    at = AppTest.from_file("../streamlit_app.py", default_timeout=120)
    at.run()
    assert not at.exception and at.text_input[0].label == "접근 코드"
    assert not any("Control Tower" in m.value for m in at.markdown)
    at.text_input[0].set_value("wrong")
    at.button[0].click().run()
    assert any("올바르지 않습니다" in e.value for e in at.error)
    at.text_input[0].set_value("s3cret")
    at.button[0].click().run()
    assert at.session_state["_authed"] is True
    _ = datetime


def test_build_fact_scales_to_large_volume():
    """성능 회귀: 배송 약 5만 건에서 팩트·KPI 계산이 실무 허용 시간 내 (기존 lambda 집계는 ~50초)."""
    import time

    from logisrisk.config import FIXTURE_DIR
    fr = {}
    for e in ("warehouses", "stores", "skus", "vehicles", "orders", "order_lines", "shipments"):
        raw = read_table((FIXTURE_DIR / f"DEMO_{e}.csv").read_bytes(), "x.csv")
        fr[e] = validate(e, raw).clean
    for e, cols in (("orders", ["order_id"]), ("order_lines", ["order_id"]), ("shipments", ["shipment_id", "order_id"])):
        fr[e] = pd.concat([fr[e].assign(**{c: fr[e][c].astype(str) + f"-{i}" for c in cols}) for i in range(20)],
                          ignore_index=True)
    t = time.time()
    fact = kpi.build_fact(fr)
    b = fact["ship_date"].max()
    kpi.compute_with_comparison(fr, fact, kpi.Filters(start=(b - pd.Timedelta(days=29)).date(), end=b.date()))
    assert len(fact) > 45000 and time.time() - t < 30
