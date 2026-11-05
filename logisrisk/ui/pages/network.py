"""02 Network Intelligence — GIS 레이어 · 영업소 위험(외부) · 기업 거점 · 가중치 재계산."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ...analytics import kpi, risk
from ...analytics.routing import haversine_km
from ...reports.export import csv_bytes
from .. import common as C
from .. import theme

LAYERS = ["고속도로 영업소 위험(외부)", "물류센터", "배송지", "배송 밀도"]


def render():
    wb = C.workbench()
    flt = C.global_filters(wb)
    u = wb.ext.units
    C.header("02 · Network Intelligence", "물류 네트워크 · GIS",
             "고속도로 영업소(외부 위험)와 기업 거점·배송지를 별도 엔터티로 중첩", wb)
    if u is None:
        C.callout("외부 영업소 데이터 파일이 없습니다: " + C.E(", ".join(wb.ext.missing)), "bad")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        layers = st.multiselect("지도 레이어", LAYERS, default=[l for l in LAYERS if l != "배송 밀도"] if wb.has_ops_data
                                else [LAYERS[0]], key="nw_layers")
    with c2:
        color_by = st.selectbox("영업소 색상", ["취약성 점수", "LISA 클러스터", "취약성 4분위 등급"], key="nw_color")
    with c3:
        routes = st.multiselect("노선", sorted(u["routeName"].unique()) if u is not None else [], key="nw_routes")

    # ── 가중치 재계산 (시뮬레이션) ─────────────────────────────────────
    sim = None
    if u is not None:
        with st.expander("취약성 가중치 재계산 (시뮬레이션) — 기본값은 기존 산출물에서 역산·검증된 0.3/0.3/0.2/0.2", expanded=False):
            cols = st.columns(4)
            w = {}
            for col, (k, (_, lab)) in zip(cols, risk.VULN_COMPONENTS.items()):
                with col:
                    w[k] = st.slider(lab, 0.0, 1.0, float(risk.DEFAULT_WEIGHTS[k]), 0.05, key=f"nw_w_{k}")
            try:
                nw = risk.normalize_weights(w)
                params = {"weights": {k: round(v, 4) for k, v in nw.items()}, "method": "minmax-weighted-sum",
                          "population": len(u)}
                sid = risk.scenario_id(params)
                sim = risk.recompute_units(u, nw)
                is_base = all(abs(nw[k] - risk.DEFAULT_WEIGHTS[k]) < 1e-9 for k in nw)
                st.markdown(C.badge(f"시나리오 ID {sid}", "info") + " "
                            + (C.badge("기본 가중치 = 기존 결과 재현", "ok") if is_base else C.badge("시뮬레이션 결과", "warn"))
                            + " " + C.badge("정규화 후 합=1", "neutral"), unsafe_allow_html=True)
                moved = sim[sim["rank_change"] != 0]
                st.caption(f"순위 변동 영업소 {len(moved)}개 · 4분위 등급 변경 {int((sim['sim_grade'] != u['vulnerability_grade']).sum())}개")
                top = sim.sort_values("sim_vulnerability", ascending=False).head(15)[
                    ["unitName", "routeName", "vulnerability_score", "sim_vulnerability", "rank_base", "rank_sim", "rank_change"]]
                st.dataframe(top, hide_index=True, use_container_width=True)
                if not is_base and C.can("scenario.save") and st.button("이 가중치 시나리오 저장", key="nw_save"):
                    C.get_store().save_scenario(wb.ctx, f"위험 가중치 {sid}", "risk_weights", params,
                                                {"top15": top.to_dict(orient="records"), "rank_changed": len(moved)},
                                                ["외부 고속도로 영업소 지표의 가중치 민감도 시뮬레이션", "기업 실적과 무관"])
                    st.success("저장되었습니다 (Scenario Lab 에서 확인).")
            except ValueError as e:
                st.error(str(e))

    units = (sim if sim is not None else u)
    if units is not None and routes:
        units = units[units["routeName"].isin(routes)]
    score_col = "sim_vulnerability" if sim is not None else "vulnerability_score"

    # ── 지도 ──────────────────────────────────────────────────────────
    sel_tab = st.session_state.get("nw_sel_table", [])
    fig = go.Figure()
    if units is not None and LAYERS[0] in layers:
        hov = units["unitName"] + " (" + units["routeName"] + ")<br>취약성 " + units[score_col].round(3).astype(str) \
            + "<br>LISA " + units["lisa_cluster"]
        if color_by == "취약성 점수":
            fig.add_trace(go.Scattermap(lat=units["yValue"], lon=units["xValue"], mode="markers", name="영업소(외부)",
                                        marker=dict(size=7, color=units[score_col], colorscale="YlOrRd",
                                                    colorbar=dict(title="취약성", thickness=10, len=0.5, x=1.0)),
                                        text=hov, hoverinfo="text", customdata=units[["unitCode"]].to_numpy()))
        else:
            key = "lisa_cluster" if color_by == "LISA 클러스터" else ("sim_grade" if sim is not None else "vulnerability_grade")
            cmap = theme.LISA_COLOR if key == "lisa_cluster" else theme.GRADE_COLOR
            for cat, g in units.groupby(key):
                fig.add_trace(go.Scattermap(lat=g["yValue"], lon=g["xValue"], mode="markers", name=f"영업소·{cat}",
                                            marker=dict(size=7 if cat in ("Not significant", "Low") else 9,
                                                        color=cmap.get(cat, "#94a3b8")),
                                            text=hov.loc[g.index], hoverinfo="text", customdata=g[["unitCode"]].to_numpy()))
        if sel_tab:
            h = units[units["unitCode"].isin(sel_tab)]
            fig.add_trace(go.Scattermap(lat=h["yValue"], lon=h["xValue"], mode="markers", name="표 선택",
                                        marker=dict(size=20, color="rgba(37,99,235,.35)"), hoverinfo="skip"))
    smap = kpi.store_map_frame(wb.fact, wb.frames, flt) if wb.has_ops_data else pd.DataFrame()
    if "배송 밀도" in layers and len(smap):
        fig.add_trace(go.Densitymap(lat=smap["lat"], lon=smap["lon"], z=smap["shipments"].fillna(0), radius=28,
                                    colorscale="Blues", showscale=False, name="배송 밀도", opacity=0.6))
    if "배송지" in layers and len(smap):
        fig.add_trace(go.Scattermap(lat=smap["lat"], lon=smap["lon"], mode="markers", name="배송지",
                                    marker=dict(size=8, color="#0891b2"), text=smap["name"], hoverinfo="text"))
    wh = wb.frames.get("warehouses")
    if "물류센터" in layers and wh is not None:
        fig.add_trace(go.Scattermap(lat=wh["lat"], lon=wh["lon"], mode="markers+text", name="물류센터",
                                    marker=dict(size=17, color="#1e3a8a"), text=wh["name"], textposition="top right"))
    fig.update_layout(**theme.plotly_layout(C.mode(), 560),
                      map=dict(style=theme.map_style(C.mode()), zoom=5.7, center=dict(lat=36.3, lon=127.8)))
    ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode=("points", "box", "lasso"), key="nw_map")
    sel_map = [p["customdata"][0] for p in (ev.selection.points if ev and ev.selection else [])
               if p.get("customdata") is not None and len(p["customdata"])]
    st.caption("영업소 점은 고속도로 TCS 영업소이며 기업 물류센터·배송지와 별개 엔터티입니다. 이 화면은 클러스터 간 연결선을 그리지 않습니다 "
               "(직선 연결은 실제 물류 흐름이 아님). 배송 밀도는 배송 건수 가중 커널 밀도입니다.")

    if units is None:
        return
    # ── 표 (지도 선택 → 필터 / 행 선택 → 지도 강조) ─────────────────
    C.section("영업소 위험 테이블", f"외부 지표 · {len(units):,}개" + (f" · 지도 선택 {len(sel_map)}개" if sel_map else ""))
    tab = units if not sel_map else units[units["unitCode"].isin(sel_map)]
    tab = tab.sort_values(score_col, ascending=False).reset_index(drop=True)
    grade_col = "sim_grade" if sim is not None else "vulnerability_grade"
    show = ["unitCode", "unitName", "routeName", score_col, grade_col, "lisa_cluster", "local_p_value",
            "mean_freight_345_share", "mean_freight_345_traffic", "traffic_volatility", "abs_imbalance_ratio"]
    tev = st.dataframe(tab[show], hide_index=True, use_container_width=True, height=300, on_select="rerun",
                       selection_mode="multi-row", key="nw_table")
    rows = [r for r in (tev.selection.rows if tev and tev.selection else []) if r < len(tab)]
    new = tab.loc[rows, "unitCode"].tolist() if rows else []
    if new != sel_tab:
        st.session_state["nw_sel_table"] = new
        st.rerun()
    C.download_button("영업소 위험 CSV", csv_bytes(tab[show]), "units_risk.csv", "text/csv", "nw_dl")

    c1, c2 = st.columns(2)
    with c1:
        rs = risk.route_summary(units.assign(_s=units[score_col]), "_s").head(15)
        f = go.Figure(go.Bar(x=rs["mean_score"], y=rs["routeName"], orientation="h", marker_color="#2563eb",
                             text=rs["units"].astype(str) + "개", textposition="outside"))
        f.update_layout(**theme.plotly_layout(C.mode(), 420, "노선별 평균 취약성 (상위 15)"))
        f.update_yaxes(autorange="reversed")
        st.plotly_chart(f, use_container_width=True)
    with c2:
        vc = units["lisa_cluster"].value_counts()
        f = go.Figure(go.Pie(labels=vc.index, values=vc.values, hole=0.6,
                             marker=dict(colors=[theme.LISA_COLOR.get(k, "#999") for k in vc.index])))
        f.update_layout(**theme.plotly_layout(C.mode(), 420, "LISA 클러스터 (p<0.05)"))
        st.plotly_chart(f, use_container_width=True)

    # ── 기업 거점 ↔ 고위험 영업소 근접성 ──────────────────────────────
    if wh is not None:
        C.section("센터 주변 고위험 영업소", "직선거리 근접성 지표 · 실제 이용 경로 아님")
        radius = st.slider("반경(km)", 5, 50, 20, 5, key="nw_rad")
        rows = []
        vh = units[(units[grade_col] == "Very High")]
        for w in wh.itertuples():
            d = haversine_km(w.lat, w.lon, units["yValue"].values, units["xValue"].values)
            near = units[d <= radius]
            dv = haversine_km(w.lat, w.lon, vh["yValue"].values, vh["xValue"].values) if len(vh) else np.array([])
            rows.append({"센터": w.name, "반경 내 영업소": len(near), "그 중 Very High": int((dv <= radius).sum()),
                         "그 중 LISA High-High": int((near["lisa_cluster"] == "High-High").sum()),
                         "반경 내 평균 취약성": float(near[score_col].mean()) if len(near) else None,
                         "최근접 영업소": units.iloc[int(np.argmin(d))]["unitName"], "최근접 거리(km)": float(d.min())})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
