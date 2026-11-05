"""03 Transportation — Cost-to-Serve · 연료비 · 배송 계획 대안(CVRP 휴리스틱) · 승인 요청."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ...analytics import cost, kpi, routing
from ...reports.export import csv_bytes
from .. import common as C
from .. import nav, theme

DIMS = {"carrier": "운송사", "vehicle_id": "차량", "store_id": "배송지", "region": "권역", "warehouse_id": "센터",
        "customer_group": "거래처군"}


def _cts(wb, flt):
    dim = st.segmented_control("기준", list(DIMS), format_func=DIMS.get, default="carrier", key="tr_dim") or "carrier"
    t = kpi.by_dimension(wb.fact, flt, dim)
    if t.empty:
        C.empty("대상 배송 없음", "필터 조건을 확인하세요.")
        return
    if dim == "store_id" and "stores" in wb.frames:
        t = t.merge(wb.frames["stores"][["store_id", "name"]], on="store_id", how="left")
    c1, c2 = st.columns([3, 2])
    with c1:
        top = t.head(20)
        f = go.Figure()
        f.add_bar(x=top[dim].astype(str), y=top["cost"], name="운송비", marker_color="#2563eb")
        f.add_scatter(x=top[dim].astype(str), y=top["cost_per_order"], name="주문당 운송비", yaxis="y2",
                      mode="markers+lines", line=dict(color="#f59e0b"))
        lay = theme.plotly_layout(C.mode(), 340, f"{DIMS[dim]}별 운송비 · 주문당 운송비 (상위 20)")
        lay["yaxis2"] = dict(overlaying="y", side="right", showgrid=False)
        f.update_layout(**lay)
        st.plotly_chart(f, use_container_width=True)
    with c2:
        tot = t["cost"].sum()
        st.metric("기간 운송비 합", C.fmt_value(tot, "원"))
        st.caption("Cost-to-Serve = 배송 단위 운송비를 차원별로 합산. 주문당/kg당/km당 단가는 각 분모가 있는 건 기준.")
        st.caption("공통비(창고 운영비·관리비) 배분은 포함하지 않습니다.")
    cols = [dim] + (["name"] if "name" in t else []) + ["shipments", "orders", "cost", "cost_per_order", "cost_per_kg",
                                                         "cost_per_km", "distance_km", "late_rate"]
    st.dataframe(C.format_df(t[cols], pct_cols=["late_rate"], money_cols=["cost", "cost_per_order", "cost_per_km"],
                             num_cols=["cost_per_kg", "distance_km"]), hide_index=True, use_container_width=True, height=300)
    C.download_button("Cost-to-Serve CSV", csv_bytes(t[cols]), f"cost_to_serve_{dim}.csv",
                      "text/csv", "tr_dl_cts")


def _fuel(wb, flt):
    x = cost.fuel_basis(kpi.apply_filters(wb.fact, flt), wb.frames.get("fuel_prices"), wb.external_diesel())
    if x.empty:
        C.empty("대상 배송 없음", "")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("연료비(실제+추정)", C.fmt_value(x["fuel_cost_eff"].sum(min_count=1), "원"))
    c2.metric("연료량", C.fmt_value(x["fuel_l_eff"].sum(min_count=1), "L"))
    share = x["fuel_cost_eff"].sum() / x["cost"].sum() if x["cost"].sum() else None
    c3.metric("운송비 중 연료비 비중", C.fmt_value(share, "%"))
    s1, s2 = st.columns(2)
    s1.dataframe(x["fuel_l_source"].value_counts().rename_axis("연료량 출처").reset_index(name="건수"), hide_index=True)
    s2.dataframe(x["price_source"].value_counts().rename_axis("경유가 출처").reset_index(name="건수"), hide_index=True)
    if (x["price_source"] == "외부 전국평균 경유가(참고)").any():
        C.callout("일부 건은 기업 구매 단가가 없어 <b>외부 전국평균 경유가</b>를 참고값으로 사용했습니다. 실제 구매 단가와 다를 수 있습니다.", "warn")
    g = x.groupby("vehicle_id", dropna=False).agg(
        carrier=("carrier", "first"), vehicle_type=("vehicle_type", "first"), shipments=("shipment_id", "count"),
        distance_km=("distance_km", "sum"), fuel_l=("fuel_l_eff", "sum"), fuel_cost=("fuel_cost_eff", "sum"),
        km_per_l_spec=("fuel_efficiency_km_per_l", "first"), total_cost=("cost", "sum")).reset_index()
    g["km_per_l_actual"] = g["distance_km"] / g["fuel_l"]
    g["eff_gap_pct"] = (g["km_per_l_actual"] / g["km_per_l_spec"] - 1) * 100
    st.markdown("**차량별 연료 효율** — 실측 연비가 제원 연비보다 크게 낮은 차량은 운행 패턴·정비 점검 후보")
    st.dataframe(C.format_df(g, money_cols=["fuel_cost", "total_cost"], num_cols=["distance_km", "fuel_l", "km_per_l_actual",
                                                                                  "eff_gap_pct"]),
                 hide_index=True, use_container_width=True, height=300)


def _route_map(depot, stops_df, title):
    f = go.Figure()
    if len(stops_df):
        for (r, vid), g in stops_df.groupby(["route", "vehicle_id"]):
            g = g.sort_values("seq")
            f.add_trace(go.Scattermap(lat=[depot["lat"], *g["lat"], depot["lat"]], lon=[depot["lon"], *g["lon"], depot["lon"]],
                                      mode="lines+markers", name=f"R{r} {vid}", line=dict(width=2), marker=dict(size=7),
                                      text=["센터", *g["name"], "센터"], hoverinfo="text+name"))
    f.add_trace(go.Scattermap(lat=[depot["lat"]], lon=[depot["lon"]], mode="markers", name=depot["name"],
                              marker=dict(size=16, color="#0f172a")))
    f.update_layout(**theme.plotly_layout(C.mode(), 460, title),
                    map=dict(style=theme.map_style(C.mode()), zoom=7.2, center=dict(lat=depot["lat"], lon=depot["lon"])))
    return f


def _planning(wb):
    need = [e for e in ("warehouses", "stores", "vehicles", "shipments", "orders") if e not in wb.frames]
    if need:
        C.empty("배송 계획에 필요한 데이터가 부족합니다", "필요: " + ", ".join(need), nav.page("data_hub"))
        return
    C.callout("<b>휴리스틱 계획 대안</b> — Clarke-Wright Savings + 2-opt. 중량·용적·운행시간·차량 수 제약을 검토하며 "
              "<b>시간창은 강제하지 않습니다</b>. 거리는 직선거리 근사(우회계수 조정 가능)이며 실도로 주행거리가 아닙니다. "
              "결과는 '제안'이며 배차 확정은 운영 관리자 승인 후 기존 TMS 에서 수행해야 합니다.", "info")
    src = st.segmented_control("계획 대상", ["orders", "shipments"], default="orders", key="rp_src",
                               format_func={"orders": "미출고 주문 (납기일 기준)", "shipments": "과거 출고 실적 재계획 (현행 비교)"}.get) or "orders"
    dates = routing.planning_days(wb.frames, wb.fact, src)
    if not dates:
        C.callout("납기일이 지정된 미출고 주문이 없습니다. 미래 주문을 업로드하거나 '과거 출고 실적 재계획'을 선택하세요."
                  if src == "orders" else "출고 실적이 없습니다.", "warn")
        return
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        day = st.selectbox("납기일" if src == "orders" else "출고일", dates[::-1] if src == "shipments" else dates,
                           format_func=lambda d: str(pd.Timestamp(d).date()), key=f"rp_day_{src}")
    with c2:
        wid = st.selectbox("센터", wb.options("warehouse_id"), key="rp_wh")
    fp = wb.frames.get("fuel_prices")
    dflt_price = None
    if fp is not None:
        x = fp[fp["date"] <= pd.Timestamp(day)]
        dflt_price = float(x["diesel_price"].iloc[-1]) if len(x) else None
    with c3:
        price = st.number_input("경유가(원/L)", value=float(dflt_price or 0.0), step=10.0, key="rp_price",
                                help="기업 유가 테이블의 해당일 값이 기본값. 없으면 직접 입력 (0 = 연료비 미산정)")
    with c4:
        rf = st.number_input("우회계수 (가정)", 1.0, 2.0, 1.0, 0.05, key="rp_rf", help="1.0 = 직선거리. 실도로 보정은 사용자 가정")
    c5, c6, c7 = st.columns(3)
    speed = c5.number_input("평균 속도(km/h, 가정)", 10.0, 90.0, 40.0, 5.0, key="rp_speed")
    svc = c6.number_input("기본 하역시간(분)", 0.0, 120.0, 15.0, 5.0, key="rp_svc")
    mh = c7.number_input("기본 최대 운행시간(h)", 1.0, 16.0, 10.0, 0.5, key="rp_mh")
    depot, stops, assign, veh = routing.build_day_inputs(wb.frames, wb.fact, day, wid, source=src)
    if stops.empty:
        st.info("해당 일자·센터에 계획 대상이 없습니다.")
        return
    st.caption(f"대상: 배송지 {len(stops)}곳 · 주문 {int(stops['orders'].sum())}건 · 가용 차량 {len(veh)}대 · "
               f"총 수요 {stops['demand_kg'].sum():,.0f}kg"
               + (f" (중량 미상 배송지 {int(stops['demand_kg'].isna().sum())}곳)" if stops["demand_kg"].isna().any() else ""))
    params = routing.RoutingParams(road_factor=rf, avg_speed_kmh=speed, default_service_min=svc, default_max_hours=mh,
                                   diesel_price=price or None)
    if st.button("계획 대안 생성", type="primary", icon=":material/route:", key="rp_run"):
        with st.spinner("경로 계산 중…"):
            prop = routing.plan_routes(depot, stops, veh, params)
            base = routing.baseline_plan(depot, assign, wb.frames["vehicles"], params) if len(assign) else None
        st.session_state["rp_res"] = {"key": (src, str(day), wid, params.to_dict()), "prop": prop, "base": base, "depot": depot}
    r = st.session_state.get("rp_res")
    if not r or r["key"] != (src, str(day), wid, params.to_dict()):
        return
    prop, base = r["prop"], r["base"]
    for v in prop.violations:
        C.callout(f"<b>제안 계획 제약 위반</b> — {C.E(v)}", "bad")
    for w in prop.warnings + (base.warnings if base else []):
        C.callout(f"⚠ {C.E(w)}", "warn")
    if base is not None:
        for v in base.violations:
            C.callout(f"현행(재구성) 제약 위반 — {C.E(v)}", "info")
        cmp = routing.compare_plans(base, prop)
        st.markdown("**현행(재구성) vs 제안** — 동일 거리 기준으로 비교한 추정치이며 실측 절감액이 아닙니다.")
        st.dataframe(cmp, hide_index=True, use_container_width=True,
                     column_config={"현행(재구성)": st.column_config.NumberColumn(format="%.1f"),
                                    "제안": st.column_config.NumberColumn(format="%.1f"),
                                    "차이": st.column_config.NumberColumn(format="%.1f"),
                                    "차이(%)": st.column_config.NumberColumn(format="%.1f%%")})
    else:
        cmp = pd.DataFrame([prop.summary])
        st.markdown("**제안 계획 요약** — 미출고 주문이라 비교할 현행 배차가 없습니다.")
        st.dataframe(cmp.drop(columns=["method", "distance_basis"], errors="ignore"), hide_index=True, use_container_width=True)
    if base is not None and base.summary.get("recorded_distance_km"):
        st.caption(f"참고: 현행 배송 실적에 기록된 운행거리 합 {base.summary['recorded_distance_km']:,.0f}km "
                   "(기록 기준이 달라 직접 비교하지 않음)")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(_route_map(r["depot"], prop.stops, "제안 경로 (방문 순서 · 직선 연결)"), use_container_width=True)
    with c2:
        st.dataframe(C.format_df(prop.routes[["route", "vehicle_id", "stops", "load_kg", "capacity_kg", "load_factor",
                                              "distance_km", "duration_h", "est_cost"]],
                                 pct_cols=["load_factor"], money_cols=["est_cost"], num_cols=["load_kg", "distance_km", "duration_h"]),
                     hide_index=True, use_container_width=True)
        if len(prop.unassigned):
            st.markdown("**미배정 배송지와 사유**")
            st.dataframe(prop.unassigned, hide_index=True, use_container_width=True)
            st.caption("대안: 차량 추가 · 2회전 운행 · 납기 조정 · 분할 배송")
    if C.can("scenario.save"):
        name = st.text_input("제안명", f"배송계획 {pd.Timestamp(day).date()} {wid}", key="rp_name")
        if st.button("승인 요청으로 저장 (배차 확정 아님)", icon=":material/approval:", key="rp_save"):
            sid = C.get_store().save_scenario(
                wb.ctx, name, "route_plan", {"date": str(pd.Timestamp(day).date()), "warehouse_id": wid, **params.to_dict()},
                {"summary_proposed": prop.summary, "summary_baseline": base.summary if base else None, "source": src, "comparison": cmp.to_dict(orient="records"),
                 "routes": prop.routes.to_dict(orient="records"), "stops": prop.stops.to_dict(orient="records"),
                 "unassigned": prop.unassigned.to_dict(orient="records"), "violations": prop.violations},
                prop.warnings + (base.warnings if base else []), wb.versions, status="proposed")
            st.success(f"제안 #{sid} 저장 — Scenario Lab 의 '승인 대기'에서 운영 관리자가 승인/반려할 수 있습니다. "
                       "승인해도 외부 시스템 배차는 자동 실행되지 않습니다.")


def render():
    wb = C.workbench()
    flt = C.global_filters(wb)
    C.header("03 · Transportation", "배송 · 배차 · 운송비", flt.describe() if wb.has_ops_data else "", wb)
    if wb.fact is None:
        C.empty("배송(shipments) 데이터가 없습니다", "운송장 단위 배송 실적을 업로드하면 Cost-to-Serve·연료비·배차 대안을 분석합니다.",
                nav.page("data_hub"))
        return
    t1, t2, t3 = st.tabs(["Cost-to-Serve", "연료비 · 연비", "배송 계획 대안"])
    with t1:
        _cts(wb, flt)
    with t2:
        _fuel(wb, flt)
    with t3:
        _planning(wb)
