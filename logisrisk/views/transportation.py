"""03 Transportation 뷰 모델: Cost-to-Serve · 연료비/연비 · 배송 계획 대안(CVRP 휴리스틱)."""
from __future__ import annotations

import pandas as pd

from ..analytics import cost, kpi, routing
from ..services import Workbench
from .serialize import jsonable, records

CTS_DIMS = {"carrier": "운송사", "vehicle_id": "차량", "store_id": "배송지", "region": "권역", "warehouse_id": "센터",
            "customer_group": "거래처군"}


def cts(wb: Workbench, flt: kpi.Filters, dim: str) -> dict:
    if dim not in CTS_DIMS:
        raise ValueError(dim)
    t = kpi.by_dimension(wb.fact, flt, dim)
    if len(t) and dim == "store_id" and "stores" in wb.frames:
        t = t.merge(wb.frames["stores"][["store_id", "name"]], on="store_id", how="left")
    t = t.rename(columns={dim: "key"})
    return {"rows": records(t, ["key", "name", "shipments", "orders", "cost", "cost_per_order", "cost_per_kg",
                                "cost_per_km", "distance_km", "late_rate"]),
            "total_cost": jsonable(t["cost"].sum(min_count=1)) if len(t) else None}


def fuel(wb: Workbench, flt: kpi.Filters) -> dict:
    if wb.fact is None:
        return {"available": False}
    x = cost.fuel_basis(kpi.apply_filters(wb.fact, flt), wb.frames.get("fuel_prices"), wb.external_diesel())
    if x.empty:
        return {"available": False}
    tot = x["cost"].sum()
    g = x.groupby("vehicle_id", dropna=False).agg(
        carrier=("carrier", "first"), vehicle_type=("vehicle_type", "first"), shipments=("shipment_id", "count"),
        distance_km=("distance_km", "sum"), fuel_l=("fuel_l_eff", "sum"), fuel_cost=("fuel_cost_eff", "sum"),
        km_per_l_spec=("fuel_efficiency_km_per_l", "first"), total_cost=("cost", "sum")).reset_index()
    g["km_per_l_actual"] = g["distance_km"] / g["fuel_l"].where(g["fuel_l"] > 0)
    g["eff_gap_pct"] = (g["km_per_l_actual"] / g["km_per_l_spec"] - 1) * 100
    return {"available": True,
            "fuel_cost": jsonable(x["fuel_cost_eff"].sum(min_count=1)), "fuel_l": jsonable(x["fuel_l_eff"].sum(min_count=1)),
            "fuel_share": jsonable(x["fuel_cost_eff"].sum() / tot) if tot else None,
            "fuel_l_sources": {str(k): int(v) for k, v in x["fuel_l_source"].value_counts().items()},
            "price_sources": {str(k): int(v) for k, v in x["price_source"].value_counts().items()},
            "uses_external_price": bool((x["price_source"] == "외부 전국평균 경유가(참고)").any()),
            "vehicles": records(g.sort_values("eff_gap_pct"))}


def planning_meta(wb: Workbench) -> dict:
    need = [e for e in ("warehouses", "stores", "vehicles", "shipments", "orders") if e not in wb.frames]
    out = {"missing": need, "warehouses": [], "days": {"orders": [], "shipments": []}}
    if need:
        return out
    wh = wb.frames["warehouses"]
    out["warehouses"] = [{"value": r.warehouse_id, "label": r.name} for r in wh.itertuples()]
    for src in ("orders", "shipments"):
        out["days"][src] = [str(pd.Timestamp(d).date()) for d in routing.planning_days(wb.frames, wb.fact, src)]
    return out


def default_diesel(wb: Workbench, day: str) -> float | None:
    fp = wb.frames.get("fuel_prices")
    if fp is None:
        return None
    x = fp[fp["date"] <= pd.Timestamp(day)]
    return float(x["diesel_price"].iloc[-1]) if len(x) else None


def plan(wb: Workbench, source: str, day: str, warehouse_id: str, params: routing.RoutingParams) -> dict:
    depot, stops, assign, veh = routing.build_day_inputs(wb.frames, wb.fact, pd.Timestamp(day), warehouse_id, source=source)
    if stops.empty:
        return {"status": "empty", "reason": "해당 일자·센터에 계획 대상이 없습니다."}
    prop = routing.plan_routes(depot, stops, veh, params)
    base = routing.baseline_plan(depot, assign, wb.frames["vehicles"], params) if len(assign) else None
    cmp = routing.compare_plans(base, prop) if base is not None else None
    return jsonable({
        "status": "ok", "source": source, "day": day, "warehouse_id": warehouse_id, "params": params.to_dict(),
        "depot": {"name": depot["name"], "lat": float(depot["lat"]), "lon": float(depot["lon"])},
        "inputs": {"stops": int(len(stops)), "orders": int(stops["orders"].sum()), "vehicles": int(len(veh)),
                   "demand_kg": float(stops["demand_kg"].sum()), "unknown_weight_stops": int(stops["demand_kg"].isna().sum())},
        "proposed": {"summary": prop.summary, "routes": records(prop.routes), "stops": records(prop.stops),
                     "unassigned": records(prop.unassigned), "violations": prop.violations, "warnings": prop.warnings},
        "baseline": None if base is None else {"summary": base.summary, "violations": base.violations,
                                               "warnings": base.warnings},
        "comparison": records(cmp) if cmp is not None else None,
    })
