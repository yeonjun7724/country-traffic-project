"""09 Reports & Alerts — Excel/HTML(PDF 인쇄) 리포트 · 알림 규칙 · 조치(Action) 워크플로."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ...analytics import alerts, cost, inventory, kpi
from ...reports.export import excel_report, html_summary, metrics_frame
from ...security import PermissionDenied
from .. import common as C


def _report_tab(wb, flt):
    if not wb.has_ops_data:
        C.empty("리포트할 운영 데이터가 없습니다", "외부 위험 데이터만 포함한 리포트를 만들 수 있습니다.")
    ms = kpi.compute_with_comparison(wb.frames, wb.fact, flt, wb.targets)
    inc = st.multiselect("포함 섹션", ["KPI", "Cost-to-Serve(운송사)", "Cost-to-Serve(배송지)", "지연 배송", "경유가 민감도",
                                    "재고 보충", "외부 위험(영업소)", "외부 데이터 감사"],
                         default=["KPI", "Cost-to-Serve(운송사)", "지연 배송", "경유가 민감도", "외부 데이터 감사"], key="rp_inc")
    sheets: dict[str, pd.DataFrame] = {}
    if "KPI" in inc:
        sheets["KPI"] = metrics_frame(ms)
    if wb.fact is not None:
        if "Cost-to-Serve(운송사)" in inc:
            sheets["CTS_운송사"] = kpi.by_dimension(wb.fact, flt, "carrier")
        if "Cost-to-Serve(배송지)" in inc:
            sheets["CTS_배송지"] = kpi.by_dimension(wb.fact, flt, "store_id")
        if "지연 배송" in inc:
            sheets["지연배송"] = kpi.exceptions(wb.fact, flt, wb.targets).get("late")
        if "경유가 민감도" in inc:
            r = cost.diesel_sensitivity(wb.fact, flt, [5, 10, 20], wb.frames.get("fuel_prices"), wb.external_diesel(), by="carrier")
            sheets["경유가민감도"] = pd.DataFrame(r["rows"])
            sheets["경유가민감도_운송사"] = r.get("by")
            sheets["경유가민감도_가정"] = pd.DataFrame({"가정": r["assumptions"]})
    if "재고 보충" in inc and "inventory" in wb.frames:
        rr = inventory.replenishment(wb.frames)
        if rr["status"] == "ok":
            sheets["재고보충"] = rr["table"]
    if "외부 위험(영업소)" in inc and wb.ext.units is not None:
        sheets["외부_영업소위험"] = wb.ext.units[["unitCode", "unitName", "routeName", "vulnerability_score",
                                              "vulnerability_grade", "lisa_cluster", "local_p_value"]]
    if "외부 데이터 감사" in inc:
        sheets["외부_데이터감사"] = pd.DataFrame(wb.ext.findings)
        sheets["외부_출처"] = C.provenance_table(wb.ext.provenance)
    sheets["데이터버전"] = pd.DataFrame([{"entity": k, **v} for k, v in wb.versions.items()])
    missing = [f"{m.label}: {m.reason}" for m in ms.values() if not m.ok]
    meta = {"워크스페이스": wb.ctx.workspace_id, "생성자": wb.ctx.user_id, "필터": flt.describe(),
            "DEMO(가상) 데이터": "예 — 실제 성과 아님" if wb.is_demo else "아니오",
            "데이터 버전": ", ".join(f"{k} v{v['version']}({v['uploaded_at'][:10]})" for k, v in wb.versions.items()) or "없음",
            "계산 불가 지표": " / ".join(missing) or "없음",
            "외부 데이터 주의": "고속도로·전국 유가 지표는 기업 실적이 아님. 유가 예측은 과거 기간이며 재학습하지 않음."}
    st.dataframe(pd.DataFrame([{"시트": k, "행": 0 if v is None else len(v)} for k, v in sheets.items()]),
                 hide_index=True, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        C.download_button("Excel 리포트 (.xlsx)", excel_report(meta, sheets), f"logisrisk_report_{pd.Timestamp.now():%Y%m%d_%H%M}.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "rp_xl")
    with c2:
        secs = [("범위", flt.describe())]
        if wb.fact is not None and "경유가민감도" in sheets:
            rows = sheets["경유가민감도"].to_dict(orient="records")
            secs.append(("경유가 민감도 (단순 가정 기반 추정)", "\n".join(
                f"경유가 {r['diesel_pct']:+g}% → 연료비 {r['fuel_cost_delta']:,.0f}원"
                + (f" (총 운송비 대비 {r['total_cost_delta_pct']:+.2f}%)" if r.get("total_cost_delta_pct") is not None else "")
                for r in rows)))
        warn = [f["title"] + ": " + f["detail"] for f in wb.ext.findings if f["level"] in ("warn", "error")]
        if warn:
            secs.append(("외부 위험 데이터 주의사항", "\n".join(warn)))
        h = html_summary("경영진 요약 리포트", meta, ms, secs,
                         {"운송사별 Cost-to-Serve": sheets.get("CTS_운송사")}, demo=wb.is_demo)
        C.download_button("경영진 요약 (HTML → 인쇄하여 PDF)", h.encode("utf-8"), "executive_summary.html", "text/html", "rp_html")
        st.caption("PDF: 내려받은 HTML 을 브라우저로 열고 인쇄 → 'PDF로 저장'. 서버측 PDF 직접 생성은 한글 폰트 번들이 필요해 아직 미구현입니다.")


def _alerts_tab(wb, flt):
    rules = dict(wb.rules)
    st.markdown("**알림 규칙** — 앱 내 표시 전용입니다. 이메일·메신저 등 외부 발송 기능은 구현되어 있지 않으며, 추가 시 명시적 설정·승인이 필요합니다.")
    can_edit = C.can("settings.manage")
    c = st.columns(3)
    rules["otif_min"] = c[0].number_input("OTIF 하한", 0.0, 1.0, float(rules.get("otif_min") or 0.95), 0.01, disabled=not can_edit)
    rules["late_rate_max"] = c[1].number_input("지연율 상한", 0.0, 1.0, float(rules.get("late_rate_max") or 0.05), 0.01, disabled=not can_edit)
    rules["monthly_cost_budget"] = c[2].number_input("월 운송비 예산(원, 0=미설정)", 0.0, 1e13,
                                                     float(rules.get("monthly_cost_budget") or 0), 1e6, disabled=not can_edit,
                                                     help="선택 기간 일수로 일할 환산해 비교합니다.") or None
    c = st.columns(3)
    rules["stockout_max"] = int(c[0].number_input("결품 허용 건수", 0, 10000, int(rules.get("stockout_max") or 0), 1, disabled=not can_edit))
    rules["data_stale_days"] = int(c[1].number_input("데이터 갱신 허용 일수", 1, 365, int(rules.get("data_stale_days") or 7), 1,
                                                     disabled=not can_edit))
    if can_edit and st.button("규칙 저장", key="al_save"):
        C.get_store().set_setting(wb.ctx, "alert_rules", rules)
        st.session_state["settings_rev"] = st.session_state.get("settings_rev", 0) + 1
        st.success("저장되었습니다.")
    ms = kpi.compute_with_comparison(wb.frames, wb.fact, flt, wb.targets)
    inv = inventory.replenishment(wb.frames) if "inventory" in wb.frames else None
    al = alerts.evaluate(ms, rules, wb.versions, inv, period_days=flt.days)
    C.section("현재 발생 알림", flt.describe())
    if not al:
        st.caption("발생한 알림이 없습니다." if wb.has_ops_data else "운영 데이터가 없어 평가할 규칙이 없습니다.")
    for i, a in enumerate(al):
        cc = st.columns([5, 1])
        cc[0].markdown(C.badge(a["severity"].upper(), {"high": "bad", "medium": "warn", "low": "info"}[a["severity"]])
                       + f" <b>{C.E(a['rule'])}</b> — {C.E(a['message'])}", unsafe_allow_html=True)
        if C.can("scenario.save") and cc[1].button("조치 생성", key=f"al_act_{i}"):
            C.get_store().create_action(wb.ctx, f"[{a['rule']}] {a['message']}", f"알림:{a['source']}", flt.describe())
            st.toast("조치 항목이 생성되었습니다.")


def _actions_tab(wb):
    store = C.get_store()
    if C.can("scenario.save"):
        with st.form("new_action", clear_on_submit=True):
            t = st.text_input("새 조치 후보")
            src = st.text_input("근거(분석 화면·시나리오 ID 등)")
            if st.form_submit_button("생성") and t:
                store.create_action(wb.ctx, t, src)
    df = store.list_actions(wb.ctx)
    if df.empty:
        st.caption("조치 항목이 없습니다.")
        return
    st.dataframe(df[["id", "title", "source", "status", "owner", "created_by", "created_at", "updated_at"]],
                 hide_index=True, use_container_width=True)
    if C.can("action.manage"):
        c = st.columns(3)
        aid = c[0].selectbox("조치", df["id"].tolist(), key="ac_id")
        stt = c[1].selectbox("상태", ["open", "in_progress", "done", "dismissed"], key="ac_st")
        own = c[2].text_input("담당자", key="ac_own")
        if st.button("상태 변경", key="ac_upd"):
            try:
                store.set_action_status(wb.ctx, int(aid), stt, own or None)
                st.rerun()
            except PermissionDenied as e:
                st.error(str(e))
    else:
        st.caption("상태 변경은 운영 관리자 이상 권한이 필요합니다.")


def render():
    wb = C.workbench()
    flt = C.global_filters(wb)
    C.header("09 · Reports & Alerts", "보고서 · 알림 · 조치", "현재 필터가 그대로 적용된 리포트", wb)
    t1, t2, t3 = st.tabs(["리포트", "알림 규칙", "조치 워크플로"])
    with t1:
        _report_tab(wb, flt)
    with t2:
        _alerts_tab(wb, flt)
    with t3:
        _actions_tab(wb)
