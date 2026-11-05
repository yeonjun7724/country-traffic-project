"""01 Control Tower — 통합 운영 KPI · 예외 · 지도/표 연동 · 드릴다운."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ...analytics import alerts, inventory, kpi
from ...reports.export import csv_bytes
from .. import common as C
from .. import nav, theme

KPI_KEYS = ["orders", "shipments", "volume_kg", "cost", "cost_per_order", "late_rate", "otif", "load_factor", "cost_per_km"]
LEDGER_COLS = ["shipment_id", "order_id", "ship_date", "planned_delivery_date", "actual_delivery_date", "delay_days",
               "store_id", "store_name", "region", "warehouse_id", "carrier", "vehicle_id", "ordered_qty",
               "delivered_qty", "load_kg_eff", "distance_km", "cost", "cost_source"]


def _external_panel(wb):
    u, ext = wb.ext.units, wb.ext
    with st.container(border=True):
        st.markdown(C.badge("외부 위험 지표", "info") + " " + C.badge("기업 실적 아님", "neutral"), unsafe_allow_html=True)
        if u is None:
            st.caption("외부 위험 데이터 파일이 없습니다.")
            return
        c1, c2, c3 = st.columns(3)
        c1.metric("분석 영업소(좌표 보유)", f"{len(u):,}")
        c2.metric("LISA High-High", f"{int((u['lisa_cluster'] == 'High-High').sum())}")
        if ext.fuel_history is not None:
            h = ext.fuel_history
            c3.metric(f"전국평균 경유 ({h['date'].max():%m-%d})", f"{h['diesel_price'].iloc[-1]:,.0f}원/L",
                      f"{(h['diesel_price'].iloc[-1] / h['diesel_price'].iloc[-31] - 1) * 100:+.1f}% (30일)" if len(h) > 31 else None,
                      delta_color="inverse")
        stale = [f for f in ext.findings if f["level"] == "warn"]
        st.caption(f"외부 데이터 감사 경고 {len(stale)}건 — 상세는 Fuel & Risk 화면")
        st.page_link(nav.page("fuel_risk"), label="Fuel & Risk 열기", icon=":material/arrow_forward:")


def render():
    wb = C.workbench()
    flt = C.global_filters(wb)
    C.header("01 · Control Tower", "통합 운영 현황", flt.describe() if wb.has_ops_data else "운영 데이터 업로드 대기", wb)

    if not wb.has_ops_data:
        c1, c2 = st.columns([3, 2])
        with c1:
            C.empty("운영 데이터가 아직 없습니다",
                    "주문·배송·차량·거점 데이터를 업로드하면 OTIF, 운송비, 적재율 등 KPI 가 실제 데이터로 계산됩니다. "
                    "가상의 성과 수치는 표시하지 않습니다. 체험하려면 사이드바에서 DEMO 워크스페이스로 전환하세요.",
                    nav.page("data_hub"))
        with c2:
            _external_panel(wb)
        return

    ms = kpi.compute_with_comparison(wb.frames, wb.fact, flt, wb.targets)
    C.kpi_grid(ms, KPI_KEYS[:5], cols=5, prefix="ct")
    st.write("")
    C.kpi_grid(ms, KPI_KEYS[5:], cols=5, prefix="ct2")
    st.caption("▲▼: 같은 길이의 직전 기간 대비. 각 카드의 '정의·산식'에서 분자·분모·표본·경고를 확인하세요.")

    inv = inventory.replenishment(wb.frames) if "inventory" in wb.frames else None
    al = alerts.evaluate(ms, wb.rules, wb.versions, inv, period_days=flt.days)
    if al:
        tone = {"high": "bad", "medium": "warn", "low": "info"}
        st.markdown(" ".join(C.badge(f"{a['rule']}: {a['message']}", tone[a["severity"]]) for a in al),
                    unsafe_allow_html=True)

    # ── 지도 ↔ 표 연동 ────────────────────────────────────────────────
    C.section("배송 네트워크", "지도에서 점을 클릭/박스·올가미 선택 → 아래 원장 필터 · 표에서 행 선택 → 지도 강조")
    smap_all = kpi.store_map_frame(wb.fact, wb.frames, flt)
    has = smap_all["shipments"].fillna(0) > 0 if len(smap_all) else pd.Series(dtype=bool)
    smap, nodata = (smap_all[has], smap_all[~has]) if len(smap_all) else (smap_all, smap_all)
    wh = wb.frames.get("warehouses")
    sel_table = st.session_state.get("ct_sel_table", [])
    left, right = st.columns([3, 2])
    with left:
        fig = go.Figure()
        if len(nodata):  # 실적 없는 배송지는 '지연율 0%'로 오인되지 않도록 회색으로 별도 표시
            fig.add_trace(go.Scattermap(lat=nodata["lat"], lon=nodata["lon"], mode="markers", name="기간 내 배송 없음",
                                        marker=dict(size=6, color="#cbd5e1"), text=nodata["name"], hoverinfo="text"))
        if len(smap):
            lr = smap["late_rate"]
            fig.add_trace(go.Scattermap(
                lat=smap["lat"], lon=smap["lon"], mode="markers", name="배송지",
                marker=dict(size=(6 + (smap["shipments"].fillna(0) ** 0.5) * 1.6).clip(upper=26), color=lr,
                            colorscale=[[0, "#16a34a"], [0.1, "#facc15"], [0.25, "#dc2626"]], cmin=0, cmax=0.25,
                            colorbar=dict(title="지연율", tickformat=".0%", thickness=10, len=0.6), opacity=0.85),
                customdata=smap[["store_id"]].to_numpy(),
                text=smap["name"] + "<br>" + smap["region"].fillna("") + "<br>배송 " + smap["shipments"].fillna(0).astype(int).astype(str)
                + "건 · 지연율 " + lr.map(lambda v: "판정 불가" if pd.isna(v) else f"{v:.1%}"),
                hoverinfo="text"))
            if sel_table:
                hs = smap[smap["store_id"].isin(sel_table)]
                fig.add_trace(go.Scattermap(lat=hs["lat"], lon=hs["lon"], mode="markers", name="표 선택",
                                            marker=dict(size=22, color="rgba(37,99,235,0.35)"), hoverinfo="skip"))
        if wh is not None:
            fig.add_trace(go.Scattermap(lat=wh["lat"], lon=wh["lon"], mode="markers+text", name="센터",
                                        marker=dict(size=16, color="#1e3a8a", symbol="circle"), text=wh["name"],
                                        textposition="top right", hoverinfo="text"))
        fig.update_layout(**theme.plotly_layout(C.mode(), 460),
                          map=dict(style=theme.map_style(C.mode()), zoom=5.6,
                                   center=dict(lat=float(smap["lat"].mean()) if len(smap) else 36.4,
                                               lon=float(smap["lon"].mean()) if len(smap) else 127.8)))
        ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode=("points", "box", "lasso"),
                             key="ct_map")
        sel_map = [p["customdata"][0] for p in (ev.selection.points if ev and ev.selection else [])
                   if p.get("customdata") is not None and len(p["customdata"])]
    with right:
        daily = kpi.apply_filters(wb.fact, flt).groupby("ship_date").agg(
            cost=("cost", "sum"), shipments=("shipment_id", "count"),
            late=("on_time", lambda s: float((s == 0).sum()) / s.notna().sum() if s.notna().any() else float("nan")))
        f2 = go.Figure()
        f2.add_bar(x=daily.index, y=daily["cost"], name="운송비(원)", marker_color="#93c5fd")
        f2.add_scatter(x=daily.index, y=daily["late"], name="지연율", yaxis="y2", line=dict(color="#dc2626", width=2))
        lay = theme.plotly_layout(C.mode(), 230, "일별 운송비 · 지연율")
        lay["yaxis2"] = dict(overlaying="y", side="right", tickformat=".0%", showgrid=False)
        f2.update_layout(**lay)
        st.plotly_chart(f2, use_container_width=True)
        dim = st.segmented_control("Cost-to-Serve 기준", ["carrier", "warehouse_id", "region", "customer_group"],
                                   format_func={"carrier": "운송사", "warehouse_id": "센터", "region": "권역",
                                                "customer_group": "거래처군"}.get, default="carrier", key="ct_dim")
        t = kpi.by_dimension(wb.fact, flt, dim or "carrier")
        if len(t):
            st.dataframe(C.format_df(t[[dim or "carrier", "shipments", "cost", "cost_per_order", "cost_per_kg", "late_rate"]],
                                     pct_cols=["late_rate"], money_cols=["cost", "cost_per_order"], num_cols=["cost_per_kg"]),
                         hide_index=True, use_container_width=True, height=200)

    # 배송지 표 (행 선택 → 지도 강조)
    stab = smap[["store_id", "name", "region", "shipments", "cost", "cost_per_order", "late_rate"]].sort_values(
        "late_rate", ascending=False, na_position="last").reset_index(drop=True) if len(smap) else pd.DataFrame()
    if len(stab):
        tev = st.dataframe(C.format_df(stab, pct_cols=["late_rate"], money_cols=["cost", "cost_per_order"]),
                           hide_index=True, use_container_width=True, height=230, on_select="rerun",
                           selection_mode="multi-row", key="ct_table")
        rows = [r for r in (tev.selection.rows if tev and tev.selection else []) if r < len(stab)]  # 필터 변경 후 잔존 선택 방어
        new_sel = stab.loc[rows, "store_id"].tolist() if rows else []
        if new_sel != sel_table:
            st.session_state["ct_sel_table"] = new_sel
            st.rerun()
    selected = sel_map or sel_table
    if selected:
        st.markdown(C.badge(f"선택 배송지 {len(selected)}곳 → 원장 필터 적용", "info"), unsafe_allow_html=True)

    # ── 드릴다운 원장 ───────────────────────────────────────────────
    C.section("예외 · 드릴다운 원장", "KPI → 배송 원장까지 추적")
    ex = kpi.exceptions(wb.fact, flt, wb.targets)
    base = kpi.apply_filters(wb.fact, flt)
    tabs = st.tabs([f"지연 배송 {len(ex.get('late', [])):,}", f"비용 초과 {len(ex.get('cost_over', [])):,}", f"전체 원장 {len(base):,}"])
    for tab, (key, df) in zip(tabs, [("late", ex.get("late")), ("cost", ex.get("cost_over")), ("all", base)]):
        with tab:
            if df is None or df.empty:
                st.caption("해당 건 없음" if df is not None else "판정 기준 데이터 부족 (목표 미설정이고 비용 표본 20건 미만)")
                continue
            d = df[df["store_id"].isin(selected)] if selected else df
            if key == "cost":
                st.caption("판정 규칙: " + ex.get("cost_over_rule", ""))
            st.dataframe(d[[c for c in LEDGER_COLS if c in d]].head(1000), hide_index=True, use_container_width=True, height=280)
            C.download_button("CSV 내보내기", csv_bytes(d[[c for c in LEDGER_COLS if c in d]]),
                              f"ledger_{key}.csv", "text/csv", key=f"dl_{key}")

    C.section("외부 위험 요약")
    _external_panel(wb)
