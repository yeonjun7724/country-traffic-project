"""06 Scenario Lab — Baseline / A / B 비교 · 기여도 · 민감도 · 센터 중단 · 저장/복제/승인/내보내기."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ...analytics import cost
from ...reports.export import excel_report
from ...security import PermissionDenied
from .. import common as C
from .. import nav, theme

PRESETS = {"경유 +5%": {"diesel_pct": 5}, "경유 +10%": {"diesel_pct": 10}, "경유 +20%": {"diesel_pct": 20},
           "수요 +10%": {"demand_pct": 10}, "수요 +30%": {"demand_pct": 30}, "단가 +5%": {"rate_pct": 5},
           "차량 -2대": {"fleet_change": -2}}


def _editor(col, tag, defaults):
    with col:
        with st.container(border=True):
            st.markdown(f"**Scenario {tag}**")
            pre = st.selectbox("프리셋", ["(직접 입력)"] + list(PRESETS), key=f"sl_pre_{tag}")
            d = {**defaults, **(PRESETS.get(pre, {}))}
            name = st.text_input("이름", f"Scenario {tag}" if pre == "(직접 입력)" else pre, key=f"sl_name_{tag}_{pre}")
            p = cost.ScenarioParams(
                name=name,
                diesel_pct=st.number_input("경유가 변화(%)", -50.0, 200.0, float(d.get("diesel_pct", 0)), 1.0, key=f"sl_d_{tag}_{pre}"),
                rate_pct=st.number_input("연료 외 운송단가 변화(%)", -50.0, 200.0, float(d.get("rate_pct", 0)), 1.0, key=f"sl_r_{tag}_{pre}"),
                demand_pct=st.number_input("물동량 변화(%)", -50.0, 300.0, float(d.get("demand_pct", 0)), 1.0, key=f"sl_q_{tag}_{pre}"),
                fleet_change=int(st.number_input("가용 차량 증감(대)", -100, 100, int(d.get("fleet_change", 0)), 1, key=f"sl_f_{tag}_{pre}")),
                trips_per_vehicle_day=int(st.number_input("차량당 1일 운행 횟수(가정)", 1, 5, 1, 1, key=f"sl_t_{tag}_{pre}")))
    return p


def _cmp_frame(base, ra, rb) -> pd.DataFrame:
    rows = []
    for key, lab, unit in (("total", "총 운송비", "원"), ("fuel", "연료비", "원"), ("nonfuel", "연료 외 비용", "원"),
                           ("trips", "운행 수", "회"), ("distance_km", "운행거리(기록)", "km"),
                           ("peak_daily_trips", "최대 일 운행", "회"), ("fleet", "가용 차량", "대"),
                           ("days_fleet_short", "차량 부족 일수", "일")):
        b = base["baseline"].get(key)
        a, bb = ra["scenario"].get(key), rb["scenario"].get(key)
        rows.append({"지표": lab, "단위": unit, "Baseline(실적)": b, ra["params"]["name"]: a, rb["params"]["name"]: bb,
                     "A 차이": None if a is None or b is None else a - b, "B 차이": None if bb is None or b is None else bb - b})
    return pd.DataFrame(rows)


def _saved(wb):
    store = C.get_store()
    df = store.list_scenarios(wb.ctx)
    if df.empty:
        st.caption("저장된 시나리오가 없습니다.")
        return
    st.dataframe(df, hide_index=True, use_container_width=True, height=240)
    c1, c2, c3 = st.columns([2, 2, 3])
    sid = c1.selectbox("시나리오 선택", df["id"].tolist(), format_func=lambda i: f"#{i} {df.set_index('id').loc[i, 'name']}", key="sl_sel")
    s = store.get_scenario(wb.ctx, int(sid))
    if s is None:
        return
    with c2:
        if C.can("scenario.save"):
            nn = st.text_input("복제 이름", f"{s['name']} (복제)", key=f"sl_dupname_{sid}")
            if st.button("복제", key=f"sl_dup_{sid}"):
                store.duplicate_scenario(wb.ctx, int(sid), nn)
                st.rerun()
    with c3:
        if s["status"] == "proposed":
            st.markdown(C.badge("승인 대기", "warn"), unsafe_allow_html=True)
            if C.can("plan.approve"):
                note = st.text_input("검토 의견", key=f"sl_note_{sid}")
                b1, b2 = st.columns(2)
                if b1.button("승인", key=f"sl_ap_{sid}", type="primary"):
                    store.set_scenario_status(wb.ctx, int(sid), "approved", note)
                    st.success("승인 기록됨. 외부 TMS 배차는 자동 실행되지 않습니다 — 담당자가 TMS 에서 확정하세요.")
                    st.rerun()
                if b2.button("반려", key=f"sl_rj_{sid}"):
                    store.set_scenario_status(wb.ctx, int(sid), "rejected", note)
                    st.rerun()
            else:
                st.caption("승인/반려는 운영 관리자 이상 권한이 필요합니다.")
        else:
            st.markdown(C.badge(f"상태: {s['status']}", "neutral"), unsafe_allow_html=True)
    with st.expander(f"#{sid} 상세 — 입력값·가정·데이터 버전·계산 버전", expanded=False):
        st.json({"params": s["params"], "assumptions": s["assumptions"], "data_versions": s["data_versions"],
                 "calc_version": s["calc_version"], "created_by": s["created_by"], "created_at": str(s["created_at"])},
                expanded=False)
        res = s["result"] or {}
        sheets = {"입력값": pd.DataFrame([s["params"]]), "가정": pd.DataFrame({"가정": s["assumptions"] or []})}
        for k, v in res.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                sheets[k] = pd.DataFrame(v)
            elif isinstance(v, dict):
                sheets[k] = pd.json_normalize(v)
        data = excel_report({"시나리오": f"#{sid} {s['name']}", "종류": s["kind"], "상태": s["status"],
                             "계산 버전": s["calc_version"], "데이터 버전": str(s["data_versions"]),
                             "DEMO": "예" if wb.is_demo else "아니오"}, sheets)
        C.download_button("Excel 내보내기", data, f"scenario_{sid}.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"sl_xl_{sid}")


def render():
    wb = C.workbench()
    flt = C.global_filters(wb)
    C.header("06 · Scenario Lab", "시나리오 분석", "Baseline(업로드 실적) 대비 가정 기반 추정 · 저장·복제·승인", wb)
    t1, t2, t3, t4 = st.tabs(["비용·운행 시나리오", "센터 중단", "저장된 시나리오 · 승인", "지원 범위"])
    with t1:
        if wb.fact is None:
            C.empty("Baseline 이 될 배송 실적이 없습니다", "배송(shipments) 데이터를 업로드하세요.", nav.page("data_hub"))
        else:
            C.callout("결과는 <b>단순 가정 기반 추정</b>입니다 (선형 비례·운행 단위 용량 가정, 최적화 아님). "
                      "Baseline 은 선택 기간의 업로드 실적이며, 절감률을 임의로 제시하지 않습니다.", "info")
            ca, cb = st.columns(2)
            pa = _editor(ca, "A", {"diesel_pct": 10})
            pb = _editor(cb, "B", {"diesel_pct": 10, "demand_pct": 30})
            args = (wb.frames.get("vehicles"), wb.frames.get("fuel_prices"), wb.external_diesel())
            ra = cost.scenario_engine(wb.fact, flt, pa, *args)
            rb = cost.scenario_engine(wb.fact, flt, pb, *args)
            if ra.get("status") != "ok":
                st.warning(ra.get("reason"))
            else:
                m = st.columns(3)
                m[0].metric("Baseline 총 운송비 (실적)", C.fmt_value(ra["baseline"]["total"], "원"))
                m[1].metric(pa.name, C.fmt_value(ra["scenario"]["total"], "원"), f"{ra['delta_pct']:+.2f}%", delta_color="inverse")
                m[2].metric(pb.name, C.fmt_value(rb["scenario"]["total"], "원"), f"{rb['delta_pct']:+.2f}%", delta_color="inverse")
                st.markdown(C.kind_badge("observed") + " Baseline &nbsp; " + C.kind_badge("assumption") + " Scenario A/B",
                            unsafe_allow_html=True)
                cmp = _cmp_frame(ra, ra, rb)
                st.dataframe(cmp, hide_index=True, use_container_width=True,
                             column_config={c: st.column_config.NumberColumn(format="localized") for c in cmp.columns[2:]})
                c1, c2 = st.columns(2)
                for col, r in ((c1, ra), (c2, rb)):
                    with col:
                        ks = list(r["contribution"])
                        f = go.Figure(go.Waterfall(x=["Baseline"] + ks + ["Scenario"],
                                                   measure=["absolute"] + ["relative"] * len(ks) + ["total"],
                                                   y=[r["baseline"]["total"]] + [r["contribution"][k] for k in ks] + [0],
                                                   connector=dict(line=dict(color="#cbd5e1"))))
                        f.update_layout(**theme.plotly_layout(C.mode(), 300, f"{r['params']['name']} 원인 기여도"))
                        st.plotly_chart(f, use_container_width=True)
                dq = ra["data_quality"]
                st.caption(f"데이터 품질: 연료비 출처 {dq['fuel_cost_sources']} · 용량 정보 있는 운행 {dq['trips_with_capacity']}/{dq['trips_total']} · "
                           f"차량 미배정 배송 {dq['shipments_without_vehicle']}건")
                with st.expander("가정 (계산 버전 포함 저장됨)"):
                    for a in ra["assumptions"]:
                        st.markdown("- " + a)
                C.section("민감도", "요인별 단일 변화(±10%, ±20%)의 총비용 영향")
                sens = cost.sensitivity(wb.fact, flt, *args)
                if len(sens):
                    f = go.Figure()
                    for s_, color in ((-20, "#93c5fd"), (-10, "#bfdbfe"), (10, "#fca5a5"), (20, "#ef4444")):
                        d = sens[sens["change_pct"] == s_]
                        f.add_bar(y=d["factor"], x=d["delta_pct"], orientation="h", name=f"{s_:+d}%", marker_color=color)
                    f.update_layout(**theme.plotly_layout(C.mode(), 260, "총비용 변화율(%)"), barmode="overlay")
                    st.plotly_chart(f, use_container_width=True)
                if C.can("scenario.save"):
                    if st.button("A · B 저장", icon=":material/save:", key="sl_save"):
                        for p, r in ((pa, ra), (pb, rb)):
                            C.get_store().save_scenario(wb.ctx, p.name, "cost_scenario", {**p.to_dict(), "filters": flt.describe()},
                                                        {k: v for k, v in r.items() if k != "assumptions"}, r["assumptions"], wb.versions)
                        st.success("저장되었습니다. 다시 열어도 '저장된 시나리오'에서 확인할 수 있습니다.")
                    data = excel_report({"필터": flt.describe(), "데이터 버전": str(wb.versions), "DEMO": "예" if wb.is_demo else "아니오",
                                         "성격": "Baseline=관측, Scenario=단순 가정 기반 추정"},
                                        {"비교": cmp, "기여도_A": pd.DataFrame([ra["contribution"]]),
                                         "기여도_B": pd.DataFrame([rb["contribution"]]), "민감도": sens,
                                         "가정": pd.DataFrame({"가정": ra["assumptions"]})})
                    C.download_button("비교 결과 Excel", data, "scenario_compare.xlsx",
                                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "sl_xl_cmp")
    with t2:
        if "warehouses" not in wb.frames:
            C.empty("센터 데이터 없음", "", nav.page("data_hub"))
        else:
            wid = st.selectbox("중단 센터", wb.options("warehouse_id"), key="sl_out")
            r = cost.warehouse_outage(wb.frames, wid, flt=flt)
            if r["status"] != "ok":
                st.warning(r["reason"])
            else:
                for a in r["assumptions"]:
                    st.caption("• " + a)
                st.dataframe(r["capacity"], hide_index=True, use_container_width=True,
                             column_config={"utilization_after": st.column_config.ProgressColumn("중단 후 가동률", format="%.0f%%",
                                                                                                 min_value=0, max_value=1)})
                st.dataframe(r["stores"], hide_index=True, use_container_width=True, height=320)
                if C.can("scenario.save") and st.button("센터 중단 분석 저장", key="sl_out_save"):
                    C.get_store().save_scenario(wb.ctx, f"센터 중단 {wid}", "warehouse_outage", {"warehouse_id": wid},
                                                {"stores": r["stores"].to_dict(orient="records"),
                                                 "capacity": r["capacity"].to_dict(orient="records")}, r["assumptions"], wb.versions)
                    st.success("저장되었습니다.")
    with t3:
        try:
            _saved(wb)
        except PermissionDenied as e:
            st.error(str(e))
    with t4:
        st.dataframe(pd.DataFrame([
            ("경유가 +5/+10/+20%", "지원", "비용·운행 시나리오"), ("배송 수요 +10/+30%", "지원(가정 기반)", "비용·운행 시나리오"),
            ("운송 단가 상승", "지원", "비용·운행 시나리오"), ("차량 수 축소/증차", "지원(차량 부족 일수)", "비용·운행 시나리오"),
            ("특정 센터 중단", "지원(직선거리 대체·용량)", "센터 중단"), ("센터 처리용량 감소", "부분(용량 입력값 기반 가동률)", "센터 중단"),
            ("SKU 보충정책 변경", "부분(서비스수준·검토주기)", "Demand & Inventory"),
            ("배송 계획 대안", "지원(CVRP 휴리스틱)", "Transportation"),
            ("특정 노선 이용 제한", "미구현 — 실도로 네트워크 데이터 필요", "P1"),
            ("신규 센터 후보 비교", "미구현", "P1"), ("배송 SLA 강화", "미구현 — 시간창 최적화(VRPTW) 필요", "P1"),
        ], columns=["시나리오", "상태", "위치"]), hide_index=True, use_container_width=True)
