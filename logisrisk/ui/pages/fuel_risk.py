"""05 Fuel & Risk — 외부 유가·교통량 · 저장된 예측(재가중) · 데이터 감사 · 기업 연료비 충격."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ...analytics import cost, risk
from ...config import REFERENCE_EVENT_DATE, REFERENCE_EVENT_LABEL
from .. import common as C
from .. import theme

TONE = {"ok": "ok", "info": "info", "warn": "warn", "error": "bad"}


def render():
    wb = C.workbench()
    flt = C.global_filters(wb)
    ext = wb.ext
    C.header("05 · Fuel & Risk", "유류비 · 외부 위험", "외부 지표(전국 유가·고속도로 교통량)와 기업 연료비 영향을 구분해 표시", wb)
    t1, t2, t3, t4 = st.tabs(["기업 연료비 충격", "유가 · 예측(외부)", f"교통량 · {REFERENCE_EVENT_LABEL}", "데이터 감사"])

    with t1:
        if wb.fact is None:
            C.empty("기업 배송 데이터가 없습니다", "운행거리·연료량·연비 데이터가 있어야 경유가 변화의 비용 영향을 계산합니다.")
        else:
            c1, c2 = st.columns([1, 3])
            pcts = c1.multiselect("경유가 변화율(%)", [-10, -5, 5, 10, 15, 20, 30], default=[5, 10, 20], key="fr_p")
            by = c1.selectbox("분해 기준", ["vehicle_id", "carrier", "store_id", "warehouse_id"],
                              format_func={"vehicle_id": "차량", "carrier": "운송사", "store_id": "배송지", "warehouse_id": "센터"}.get,
                              key="fr_by")
            r = cost.diesel_sensitivity(wb.fact, flt, sorted(pcts), wb.frames.get("fuel_prices"), wb.external_diesel(), by=by)
            with c2:
                m = st.columns(3)
                m[0].metric("기준 연료비", C.fmt_value(r["base_fuel_cost"], "원"))
                m[1].metric("기간 총 운송비", C.fmt_value(r["base_total_cost"], "원"))
                m[2].metric("계산 커버리지", f"{r['coverage']:.0%}", f"{r['n_computable']:,}/{r['n_total']:,}건", delta_color="off")
                st.dataframe([{"경유가 변화": f"{x['diesel_pct']:+g}%", "연료비 변화(원)": f"{x['fuel_cost_delta']:,.0f}",
                               "총 운송비 대비": "—" if x["total_cost_delta_pct"] is None else f"{x['total_cost_delta_pct']:+.2f}%"}
                              for x in r["rows"]], hide_index=True, use_container_width=True)
            st.caption("연료량 출처: " + ", ".join(f"{k} {v}건" for k, v in r["fuel_l_sources"].items())
                       + " · 경유가 출처: " + ", ".join(f"{k} {v}건" for k, v in r["price_sources"].items()))
            for a in r["assumptions"]:
                st.caption("• " + a)
            if "by" in r:
                st.dataframe(r["by"].head(50), hide_index=True, use_container_width=True, height=300)
                C.download_button("CSV", r["by"].to_csv(index=False).encode("utf-8-sig"), "diesel_sensitivity.csv",
                                  "text/csv", "fr_dl")
            st.caption("복합 시나리오(운송단가·물동량·차량 수)는 Scenario Lab 에서 비교·저장할 수 있습니다.")

    with t2:
        h, f = ext.fuel_history, ext.forecast
        st.markdown(C.badge("외부 위험 지표", "info") + " " + C.badge("전국 평균 — 기업 구매가 아님", "neutral"), unsafe_allow_html=True)
        if h is None:
            st.warning("유가 이력 파일 없음")
        else:
            p = ext.provenance.get("forecast")
            if p and p.warnings:
                for w in p.warnings:
                    C.callout("<b>예측 최신성</b> — " + C.E(w), "warn")
            c1, c2 = st.columns([3, 1])
            with c2:
                w0 = risk.infer_ensemble_weight(f) if f is not None else None
                pw = st.slider("Prophet 가중치 (재가중)", 0.0, 1.0, round(w0 or 0.4, 2), 0.05, key="fr_pw",
                               help="저장된 Prophet·LSTM 예측값을 다시 가중합합니다. 모델을 재학습하지 않습니다.")
                st.caption(f"저장된 앙상블 가중치(역산): Prophet {w0:.2f} / LSTM {1 - w0:.2f}" if w0 is not None else "")
                show_comp = st.checkbox("구성 모델 표시", True, key="fr_comp")
            with c1:
                fig = go.Figure()
                fig.add_scatter(x=h["date"], y=h["diesel_price"], name="경유(관측)", line=dict(color="#0f172a", width=2))
                fig.add_scatter(x=h["date"], y=h["gasoline_price"], name="휘발유(관측)", line=dict(color="#94a3b8", width=1))
                if f is not None:
                    fig.add_scatter(x=f["date"], y=f["diesel_price_prophet_upper"], line=dict(width=0), showlegend=False, hoverinfo="skip")
                    fig.add_scatter(x=f["date"], y=f["diesel_price_prophet_lower"], fill="tonexty", line=dict(width=0),
                                    fillcolor="rgba(37,99,235,.12)", name="Prophet 구간")
                    fig.add_scatter(x=f["date"], y=risk.reweight_ensemble(f, pw), name=f"앙상블(재가중 {pw:.2f})",
                                    line=dict(color="#2563eb", width=2, dash="dash"))
                    if show_comp:
                        fig.add_scatter(x=f["date"], y=f["diesel_price_prophet"], name="Prophet", line=dict(color="#7c3aed", width=1))
                        fig.add_scatter(x=f["date"], y=f["diesel_price_lstm"], name="LSTM", line=dict(color="#f59e0b", width=1))
                fig.add_vline(x=REFERENCE_EVENT_DATE, line=dict(color="#dc2626", dash="dot", width=1))
                fig.add_annotation(x=REFERENCE_EVENT_DATE, y=1, yref="paper", text=REFERENCE_EVENT_LABEL, showarrow=False,
                                   font=dict(size=10, color="#dc2626"), xanchor="left")
                fig.update_layout(**theme.plotly_layout(C.mode(), 400, "경유가 관측 · 저장된 예측 (원/L)"))
                st.plotly_chart(fig, use_container_width=True)
            if f is not None:
                C.callout("Shock Index·위험등급은 예측 구간 30일 내 변화율의 <b>min-max 상대값</b>입니다. "
                          f"이 예측의 변화율은 전 구간 {f['diesel_change_rate'].min():.1f}%~{f['diesel_change_rate'].max():.1f}% (마지막 관측가 대비 하락)이므로 "
                          "'CRITICAL' 은 절대적 가격 급등을 뜻하지 않습니다. 기존 화면의 '향후 30일 CRITICAL' 경보는 표시하지 않습니다.", "warn")
                st.dataframe(f[["date", "diesel_price_prophet", "diesel_price_lstm", "diesel_price_ensemble",
                                "diesel_change_rate", "diesel_shock_index", "risk_level"]],
                             hide_index=True, use_container_width=True, height=240)

    with t3:
        t = ext.traffic
        if t is None:
            st.warning("교통량 파일 없음")
        else:
            r = risk.period_comparison(t, REFERENCE_EVENT_DATE)
            C.callout("<b>해석 주의</b> — " + C.E(r.get("caveat", "")) + " 기준일 명칭은 원인이 검증되지 않아 중립적으로 표기합니다.", "warn")
            m = st.columns(4)
            m[0].metric(f"이전 일평균 화물 ({r['pre_days']}일)", f"{r['pre_mean']:,.0f}대")
            m[1].metric(f"이후 일평균 화물 ({r['post_days']}일)", f"{r['post_mean']:,.0f}대", f"{r['change_pct']:+.1f}%", delta_color="off")
            m[2].metric("요일 구성 보정 변화", f"{r['change_pct_dow_adj']:+.1f}%")
            m[3].metric("전년 동기간 대비", f"{r['yoy_pct']:+.1f}%" if r.get("yoy_pct") is not None else "비교 불가")
            w = t.set_index("date")[["freight_345_traffic", "passenger_126_traffic"]].resample("W").mean()
            fig = go.Figure()
            fig.add_scatter(x=w.index, y=w["freight_345_traffic"], name="화물(3·4·5종) 주평균", line=dict(color="#2563eb"))
            fig.add_scatter(x=w.index, y=w["passenger_126_traffic"], name="승용(1·2·6종) 주평균", yaxis="y2", line=dict(color="#94a3b8"))
            fig.add_vline(x=REFERENCE_EVENT_DATE, line=dict(color="#dc2626", dash="dot"))
            lay = theme.plotly_layout(C.mode(), 360, "전국 고속도로 일교통량 (주 평균)")
            lay["yaxis2"] = dict(overlaying="y", side="right", showgrid=False)
            fig.update_layout(**lay)
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"이전 {r['pre_period']} · 이후 {r['post_period']} — 기간 길이·계절 구성이 다릅니다.")

    with t4:
        st.markdown("기존 공모전 산출물을 파일에서 매번 재계산해 점검한 결과입니다.")
        for fnd in ext.findings:
            C.callout(f"{C.badge(fnd['level'].upper(), TONE[fnd['level']])} <b>{C.E(fnd['title'])}</b> — {C.E(fnd['detail'])}",
                      {"error": "bad", "warn": "warn", "ok": "ok"}.get(fnd["level"], "info"))
        C.section("데이터 출처")
        st.dataframe(C.provenance_table(ext.provenance), hide_index=True, use_container_width=True)
