"""04 Demand & Inventory — 재고 위험 · 안전재고/재주문점 · 보충 추천 · 수요예측 백테스트."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ...analytics import inventory
from ...reports.export import csv_bytes
from .. import common as C
from .. import nav, theme


def render():
    wb = C.workbench()
    C.header("04 · Demand & Inventory", "수요 · 재고 · 보충", "기업 재고·주문 이력이 있을 때만 계산", wb)
    if "inventory" not in wb.frames or "order_lines" not in wb.frames:
        need = [e for e in ("inventory", "orders", "order_lines") if e not in wb.frames]
        C.empty("재고 분석에 필요한 데이터가 없습니다",
                f"필요: {', '.join(need)}. 기업 재고 데이터 없이 재고 위험을 추정하거나 표시하지 않습니다.", nav.page("data_hub"))
        return
    c1, c2, c3 = st.columns(3)
    sl = c1.select_slider("목표 서비스 수준", [0.90, 0.95, 0.975, 0.99], value=0.95, format_func=lambda v: f"{v:.1%}", key="iv_sl")
    win = c2.select_slider("수요 산정 기간(일)", [14, 28, 56, 84], value=28, key="iv_win")
    rev = c3.number_input("검토 주기(일)", 1.0, 30.0, 7.0, 1.0, key="iv_rev")
    r = inventory.replenishment(wb.frames, service_level=sl, window_days=win, review_days=rev)
    if r["status"] != "ok":
        C.callout(C.E(r["reason"]), "warn")
        return
    s, t = r["summary"], r["table"]
    m = st.columns(4)
    m[0].metric("SKU×센터", f"{s['sku_locations']:,}")
    m[1].metric("결품(가용 ≤ 0)", f"{s['stockout']:,}", f"{s['stockout_rate']:.1%}", delta_color="off")
    m[2].metric("재주문점 이하", f"{s['high_risk']:,}")
    m[3].metric("보충 추천 합계", f"{t['recommended_qty'].sum():,.0f} EA")
    st.caption(f"재고 기준일 {r['snapshot_date']} · 수요 기간 {r['demand_window']} · z={r['z']:.3f}")
    for a in r["assumptions"]:
        st.caption("• " + a)
    risk_f = st.multiselect("위험 구분", ["결품", "높음", "낮음", "판정 불가"], default=["결품", "높음"], key="iv_rf")
    view = t[t["stockout_risk"].isin(risk_f)] if risk_f else t
    st.dataframe(view, hide_index=True, use_container_width=True, height=360,
                 column_config={"days_of_supply": st.column_config.NumberColumn("재고일수", format="%.1f"),
                                "avg_daily_demand": st.column_config.NumberColumn("일평균 수요", format="%.2f"),
                                "safety_stock": st.column_config.NumberColumn("안전재고", format="%.0f"),
                                "reorder_point": st.column_config.NumberColumn("재주문점", format="%.0f"),
                                "basis": st.column_config.TextColumn("추천 근거", width="large")})
    C.download_button("보충 추천 CSV", csv_bytes(view), "replenishment.csv", "text/csv", "iv_dl")
    st.caption("보충 추천은 발주 확정이 아닙니다. 발주는 ERP 에서 담당자 승인 후 진행하세요.")

    C.section("수요예측 모델 비교", "holdout 14일 백테스트 · WAPE 순")
    c1, c2 = st.columns([1, 3])
    sku_opts = sorted(wb.frames["skus"]["sku_id"]) if "skus" in wb.frames else sorted(wb.frames["order_lines"]["sku_id"].unique())
    sku = c1.selectbox("SKU", sku_opts, key="iv_sku")
    whs = c1.selectbox("센터", ["(전체)"] + wb.options("warehouse_id"), key="iv_wh")
    fr = inventory.forecast_sku(wb.frames, sku, None if whs == "(전체)" else whs)
    with c2:
        if fr["status"] != "ok":
            st.info(fr["reason"])
        else:
            f = go.Figure(go.Scatter(x=fr["series"].index, y=fr["series"].values, mode="lines", name="일별 주문수량"))
            f.update_layout(**theme.plotly_layout(C.mode(), 240, f"{sku} 일별 수요"))
            st.plotly_chart(f, use_container_width=True)
            st.dataframe(fr["backtest"], hide_index=True, use_container_width=True)
            st.caption(f"최저 WAPE 모델: {fr['best']}. MAPE 는 실적 0인 날을 제외해 계산(제외 건수 표기). "
                       "통계/ML 모델(ETS·Prophet 등) 비교는 P1 확장 범위입니다.")
