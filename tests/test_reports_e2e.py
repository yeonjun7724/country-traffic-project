"""실무 인수 시나리오 E2E (UI 제외): 업로드 → 검증 → KPI → 시나리오 → 계획 → AI → 내보내기 → 재오픈."""
import io

import pandas as pd
from openpyxl import load_workbook

from logisrisk.analytics import cost, kpi, routing
from logisrisk.config import FIXTURE_DIR
from logisrisk.copilot import agent
from logisrisk.data import ingest
from logisrisk.data.external import load_external
from logisrisk.data.schemas import UPLOAD_ORDER
from logisrisk.data.store import Store
from logisrisk.data.validation import auto_map, read_table
from logisrisk.reports.export import excel_report, html_summary, metrics_frame
from logisrisk.services import Workbench


def test_acceptance_flow(tmp_path):
    url = f"sqlite:///{(tmp_path / 'e2e.db').as_posix()}"
    s = Store(url)
    ctx = s.context_for("local", "default")
    # 1-2. 업로드(일반 워크스페이스, 사용자 데이터로 가정) + 검증 + 오류 행 안내
    pending = {}
    for ent in UPLOAD_ORDER:
        p = FIXTURE_DIR / f"DEMO_{ent}.csv"
        if not p.exists():
            continue
        raw = read_table(p.read_bytes(), p.name)
        mp = auto_map(list(raw.columns), ent)
        res = ingest.validate_upload(s, ctx, ent, raw, mp, pending)
        assert res.ok and res.n_error_rows == 0, (ent, res.errors.head())
        pending[ent] = res.clean
        ingest.commit(s, ctx, res, filename=p.name, mapping=mp)
    bad = read_table((FIXTURE_DIR / "DEMO_invalid_orders_for_validation.csv").read_bytes(), "bad.csv")
    vr = ingest.validate_upload(s, ctx, "orders", bad, auto_map(list(bad.columns), "orders"))
    assert vr.n_error_rows == 6 and len(vr.error_rows(bad)) == 6

    # 3. KPI
    ext = load_external()
    wb = Workbench.load(s, ctx, ext)
    b = wb.date_bounds()
    flt = kpi.Filters(start=(b[1] - pd.Timedelta(days=29)).date(), end=b[1].date(), regions=["수도권"])
    ms = kpi.compute_with_comparison(wb.frames, wb.fact, flt, wb.targets)
    assert all(ms[k].ok for k in ("orders", "cost", "otif", "load_factor", "cost_per_km"))
    # 4. 지도 프레임이 필터와 동기화
    sm = kpi.store_map_frame(wb.fact, wb.frames, flt)
    assert set(sm["region"]) == {"수도권"}
    # 5. 경유가 시나리오
    sc = cost.scenario_engine(wb.fact, flt, cost.ScenarioParams(name="A", diesel_pct=10), wb.frames["vehicles"],
                              wb.frames["fuel_prices"])
    assert sc["status"] == "ok" and sc["delta_total"] > 0
    # 6-7. 배송 계획 대안 + Baseline 비교
    day = wb.fact["ship_date"].max()
    depot, stops, assign, veh = routing.build_day_inputs(wb.frames, wb.fact, day, "WH-A")
    p = routing.RoutingParams(diesel_price=1700)
    prop, base = routing.plan_routes(depot, stops, veh, p), routing.baseline_plan(depot, assign, wb.frames["vehicles"], p)
    cmp = routing.compare_plans(base, prop)
    assert prop.summary["stops_planned"] + prop.summary["stops_unassigned"] == len(stops)
    # 8. AI 가 계산 결과를 인용
    r = agent.run(wb, "경유가격이 10% 오르면 운송사별 비용은?", api_key="")
    assert r.tool_results and f"{r.tool_results[0]['result']['rows'][0]['fuel_cost_delta']:,.0f}" in r.answer
    # 9. Excel / HTML(PDF 인쇄) 내보내기
    x = excel_report({"필터": flt.describe()}, {"KPI": metrics_frame(ms), "비교": cmp})
    wbk = load_workbook(io.BytesIO(x))
    assert wbk.sheetnames == ["00_정보", "KPI", "비교"]
    h = html_summary("요약", {"필터": flt.describe()}, ms, [("범위", flt.describe())])
    assert "<html" in h and "OTIF" in h
    # 10. 저장 후 재오픈
    sid = s.save_scenario(ctx, "A", "cost_scenario", sc["params"], {k: v for k, v in sc.items() if k != "assumptions"},
                          sc["assumptions"], wb.versions)
    s.set_setting(ctx, "targets", {"otif": 0.97})
    s2 = Store(url)
    c2 = s2.context_for("local", "default")
    again = s2.get_scenario(c2, sid)
    assert again["result"]["delta_total"] == sc["delta_total"]
    assert again["data_versions"]["shipments"]["version"] == 1
    assert Workbench.load(s2, c2, ext).targets["otif"] == 0.97


def test_metrics_frame_marks_not_computable(mini_frames):
    fr = {k: v for k, v in mini_frames.items() if k != "shipments"}
    df = metrics_frame(kpi.compute(fr, None, kpi.Filters()))
    assert (df.set_index("지표").loc["OTIF", "상태"]) == "계산 불가"
