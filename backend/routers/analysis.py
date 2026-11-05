"""02 Network · 03 Transportation · 04 Inventory · 05 Fuel & Risk · 06 Scenario Lab API."""
from __future__ import annotations

from typing import Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from logisrisk.analytics import cost, routing
from logisrisk.analytics.kpi import Filters
from logisrisk.reports.export import csv_bytes, excel_report
from logisrisk.security import PermissionDenied, UserContext
from logisrisk.services import Workbench
from logisrisk.views import analysis as A
from logisrisk.views import network as N
from logisrisk.views import transportation as T
from logisrisk.views.serialize import jsonable, records

from ..deps import get_filters, get_store, get_workbench, permission

router = APIRouter()
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _file(data: bytes, name: str, media: str) -> Response:
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ── 02 Network ────────────────────────────────────────────────────────
class Weights(BaseModel):
    freight_share: float = Field(0.3, ge=0, le=1)
    freight_volume: float = Field(0.3, ge=0, le=1)
    volatility: float = Field(0.2, ge=0, le=1)
    imbalance: float = Field(0.2, ge=0, le=1)


def _weights(freight_share: float | None = None, freight_volume: float | None = None, volatility: float | None = None,
             imbalance: float | None = None) -> dict | None:
    vals = {"freight_share": freight_share, "freight_volume": freight_volume, "volatility": volatility, "imbalance": imbalance}
    if all(v is None for v in vals.values()):
        return None
    w = Weights(**{k: v for k, v in vals.items() if v is not None}).model_dump()
    if sum(w.values()) <= 0:
        raise HTTPException(status_code=422, detail="가중치 합이 0 보다 커야 합니다.")
    return w


@router.get("/network/meta")
def network_meta(_: UserContext = Depends(permission("data.read"))):
    return {"components": N.components()}


@router.get("/network/units")
def network_units(routes: list[str] = Query(default=[]), w: dict | None = Depends(_weights),
                  wb: Workbench = Depends(get_workbench)):
    return N.units_view(wb, w, routes or None)


@router.get("/network/proximity")
def network_proximity(radius_km: float = Query(20, ge=1, le=100), w: dict | None = Depends(_weights),
                      wb: Workbench = Depends(get_workbench)):
    return N.proximity(wb, w, radius_km)


@router.get("/network/units.csv")
def network_csv(routes: list[str] = Query(default=[]), w: dict | None = Depends(_weights),
                ctx: UserContext = Depends(permission("data.export")), wb: Workbench = Depends(get_workbench)):
    df = N.risk_frame(wb, w, routes or None)
    get_store().log(ctx, "export.csv", "units_risk", {"rows": len(df)})
    return _file(csv_bytes(df), "units_risk.csv", "text/csv; charset=utf-8")


@router.post("/network/scenarios")
def network_save(body: Weights, ctx: UserContext = Depends(permission("scenario.save")),
                 wb: Workbench = Depends(get_workbench)):
    v = N.units_view(wb, body.model_dump(), None)
    if not v["available"]:
        raise HTTPException(status_code=409, detail=v["reason"])
    if v["scenario"]["is_base"]:
        raise HTTPException(status_code=422, detail="기본 가중치와 같아 저장할 시나리오가 아닙니다.")
    top = sorted(v["units"], key=lambda u: -u["score"])[:15]
    sid = get_store().save_scenario(ctx, f"위험 가중치 {v['scenario']['id']}", "risk_weights", v["scenario"]["params"],
                                    {"top15": top, "rank_changed": v["scenario"]["rank_changed"]},
                                    ["외부 고속도로 영업소 지표의 가중치 민감도 시뮬레이션", "기업 실적과 무관"], wb.versions)
    return {"id": sid}


# ── 03 Transportation ─────────────────────────────────────────────────
@router.get("/transportation/cts")
def tr_cts(dim: Literal["carrier", "vehicle_id", "store_id", "region", "warehouse_id", "customer_group"] = "carrier",
           wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    return T.cts(wb, flt, dim)


@router.get("/transportation/cts.csv")
def tr_cts_csv(dim: Literal["carrier", "vehicle_id", "store_id", "region", "warehouse_id", "customer_group"] = "carrier",
               ctx: UserContext = Depends(permission("data.export")), wb: Workbench = Depends(get_workbench),
               flt: Filters = Depends(get_filters)):
    df = pd.DataFrame(T.cts(wb, flt, dim)["rows"])
    get_store().log(ctx, "export.csv", f"cts_{dim}", {"rows": len(df)})
    return _file(csv_bytes(df), f"cost_to_serve_{dim}.csv", "text/csv; charset=utf-8")


@router.get("/transportation/fuel")
def tr_fuel(wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    return T.fuel(wb, flt)


@router.get("/transportation/planning")
def tr_planning(wb: Workbench = Depends(get_workbench)):
    return T.planning_meta(wb)


class PlanIn(BaseModel):
    source: Literal["orders", "shipments"] = "orders"
    day: str
    warehouse_id: str
    road_factor: float = Field(1.0, ge=1.0, le=2.0)
    avg_speed_kmh: float = Field(40.0, ge=10, le=90)
    default_service_min: float = Field(15.0, ge=0, le=120)
    default_max_hours: float = Field(10.0, ge=1, le=16)
    diesel_price: float | None = Field(None, ge=0, le=10000)


def _plan(body: PlanIn, wb: Workbench) -> dict:
    meta = T.planning_meta(wb)
    if meta["missing"]:
        raise HTTPException(status_code=409, detail="필요한 데이터: " + ", ".join(meta["missing"]))
    if body.day not in meta["days"][body.source]:
        raise HTTPException(status_code=422, detail="계획 가능한 일자가 아닙니다.")
    if body.warehouse_id not in {w["value"] for w in meta["warehouses"]}:
        raise HTTPException(status_code=422, detail="알 수 없는 센터입니다.")
    price = body.diesel_price if body.diesel_price is not None else T.default_diesel(wb, body.day)
    params = routing.RoutingParams(road_factor=body.road_factor, avg_speed_kmh=body.avg_speed_kmh,
                                   default_service_min=body.default_service_min, default_max_hours=body.default_max_hours,
                                   diesel_price=price or None)
    return T.plan(wb, body.source, body.day, body.warehouse_id, params)


@router.post("/transportation/plan")
def tr_plan(body: PlanIn, wb: Workbench = Depends(get_workbench)):
    return _plan(body, wb)


class PlanSaveIn(PlanIn):
    name: str = Field(min_length=1, max_length=200)


@router.post("/transportation/plan/save")
def tr_plan_save(body: PlanSaveIn, ctx: UserContext = Depends(permission("scenario.save")),
                 wb: Workbench = Depends(get_workbench)):
    r = _plan(body, wb)
    if r.get("status") != "ok":
        raise HTTPException(status_code=409, detail=r.get("reason"))
    p = r["proposed"]
    sid = get_store().save_scenario(
        ctx, body.name, "route_plan", {"date": body.day, "warehouse_id": body.warehouse_id, **r["params"]},
        {"summary_proposed": p["summary"], "summary_baseline": (r["baseline"] or {}).get("summary"), "source": body.source,
         "comparison": r["comparison"] or [p["summary"]], "routes": p["routes"], "stops": p["stops"],
         "unassigned": p["unassigned"], "violations": p["violations"]},
        p["warnings"] + ((r["baseline"] or {}).get("warnings") or []), wb.versions, status="proposed")
    return {"id": sid}


# ── 04 Inventory ──────────────────────────────────────────────────────
@router.get("/inventory/replenishment")
def inv_repl(service_level: float = Query(0.95, ge=0.5, lt=1), window_days: int = Query(28, ge=7, le=180),
             review_days: float = Query(7, ge=1, le=60), wb: Workbench = Depends(get_workbench)):
    return A.inventory_view(wb, service_level, window_days, review_days)


@router.get("/inventory/replenishment.csv")
def inv_csv(service_level: float = Query(0.95, ge=0.5, lt=1), window_days: int = Query(28, ge=7, le=180),
            review_days: float = Query(7, ge=1, le=60), ctx: UserContext = Depends(permission("data.export")),
            wb: Workbench = Depends(get_workbench)):
    v = A.inventory_view(wb, service_level, window_days, review_days)
    if v["status"] != "ok":
        raise HTTPException(status_code=409, detail=v.get("reason"))
    df = pd.DataFrame(v["rows"])
    get_store().log(ctx, "export.csv", "replenishment", {"rows": len(df)})
    return _file(csv_bytes(df), "replenishment.csv", "text/csv; charset=utf-8")


@router.get("/inventory/skus")
def inv_skus(wb: Workbench = Depends(get_workbench)):
    return A.sku_options(wb)


@router.get("/inventory/forecast")
def inv_forecast(sku: str, warehouse_id: str | None = None, wb: Workbench = Depends(get_workbench)):
    return A.forecast_view(wb, sku, warehouse_id or None)


# ── 05 Fuel & Risk ────────────────────────────────────────────────────
@router.get("/fuel/diesel")
def fuel_diesel(pcts: list[float] = Query(default=[5, 10, 20]),
                by: Literal["vehicle_id", "carrier", "store_id", "warehouse_id"] = "carrier",
                wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    if not pcts or any(p < -50 or p > 200 for p in pcts):
        raise HTTPException(status_code=422, detail="변화율은 -50~200% 범위로 1개 이상")
    return A.diesel_view(wb, flt, pcts[:8], by)


@router.get("/fuel/market")
def fuel_market(prophet_weight: float | None = Query(None, ge=0, le=1), wb: Workbench = Depends(get_workbench)):
    return A.fuel_market(wb, prophet_weight)


@router.get("/fuel/traffic")
def fuel_traffic(wb: Workbench = Depends(get_workbench)):
    return A.traffic_view(wb)


@router.get("/fuel/audit")
def fuel_audit(wb: Workbench = Depends(get_workbench)):
    return A.audit_view(wb)


# ── 06 Scenario Lab ───────────────────────────────────────────────────
class ScenarioIn(BaseModel):
    name: str = Field("Scenario", min_length=1, max_length=100)
    diesel_pct: float = Field(0, ge=-50, le=200)
    demand_pct: float = Field(0, ge=-50, le=300)
    rate_pct: float = Field(0, ge=-50, le=200)
    fleet_change: int = Field(0, ge=-100, le=100)
    trips_per_vehicle_day: int = Field(1, ge=1, le=5)

    def params(self) -> cost.ScenarioParams:
        return cost.ScenarioParams(**self.model_dump())


class CompareIn(BaseModel):
    a: ScenarioIn
    b: ScenarioIn


@router.post("/scenarios/compare")
def sc_compare(body: CompareIn, wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    return A.scenario_compare(wb, flt, body.a.params(), body.b.params())


@router.get("/scenarios/sensitivity")
def sc_sensitivity(wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    return A.sensitivity_view(wb, flt)


@router.post("/scenarios/compare/save")
def sc_save(body: CompareIn, ctx: UserContext = Depends(permission("scenario.save")),
            wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    ids = []
    for s in (body.a, body.b):
        r = cost.scenario_engine(wb.fact, flt, s.params(), wb.frames.get("vehicles"), wb.frames.get("fuel_prices"),
                                 wb.external_diesel()) if wb.fact is not None else {"status": "missing"}
        if r.get("status") != "ok":
            raise HTTPException(status_code=409, detail=r.get("reason", "Baseline 배송 실적이 없습니다."))
        ids.append(get_store().save_scenario(ctx, s.name, "cost_scenario", {**s.model_dump(), "filters": flt.describe()},
                                             jsonable({k: v for k, v in r.items() if k != "assumptions"}),
                                             r["assumptions"], wb.versions))
    return {"ids": ids}


@router.get("/scenarios/outage")
def sc_outage(warehouse_id: str, wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    return A.outage_view(wb, flt, warehouse_id)


@router.post("/scenarios/outage/save")
def sc_outage_save(warehouse_id: str, ctx: UserContext = Depends(permission("scenario.save")),
                   wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    r = A.outage_view(wb, flt, warehouse_id)
    if r["status"] != "ok":
        raise HTTPException(status_code=409, detail=r.get("reason"))
    sid = get_store().save_scenario(ctx, f"센터 중단 {warehouse_id}", "warehouse_outage", {"warehouse_id": warehouse_id},
                                    {"stores": r["stores"], "capacity": r["capacity"]}, r["assumptions"], wb.versions)
    return {"id": sid}


@router.get("/scenarios")
def sc_list(ctx: UserContext = Depends(permission("data.read"))):
    return records(get_store().list_scenarios(ctx))


def _get(ctx: UserContext, sid: int) -> dict:
    s = get_store().get_scenario(ctx, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="시나리오를 찾을 수 없습니다.")
    return s


@router.get("/scenarios/{sid}")
def sc_get(sid: int, ctx: UserContext = Depends(permission("data.read"))) -> Any:
    return jsonable(_get(ctx, sid))


class DupIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@router.post("/scenarios/{sid}/duplicate")
def sc_dup(sid: int, body: DupIn, ctx: UserContext = Depends(permission("scenario.save"))):
    _get(ctx, sid)
    return {"id": get_store().duplicate_scenario(ctx, sid, body.name)}


class StatusIn(BaseModel):
    status: Literal["draft", "proposed", "approved", "rejected", "archived"]
    note: str = Field("", max_length=500)


@router.post("/scenarios/{sid}/status")
def sc_status(sid: int, body: StatusIn, ctx: UserContext = Depends(permission("data.read"))):
    _get(ctx, sid)
    try:
        get_store().set_scenario_status(ctx, sid, body.status, body.note)
    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"id": sid, "status": body.status}


@router.get("/scenarios/{sid}/excel")
def sc_excel(sid: int, ctx: UserContext = Depends(permission("data.export"))):
    s = _get(ctx, sid)
    data = excel_report({"시나리오": f"#{sid} {s['name']}", "종류": s["kind"], "상태": s["status"],
                         "계산 버전": s["calc_version"], "데이터 버전": str(s["data_versions"]),
                         "DEMO": "예" if ctx.is_demo_workspace else "아니오"}, A.scenario_sheets(s))
    get_store().log(ctx, "export.xlsx", f"scenario_{sid}")
    return _file(data, f"scenario_{sid}.xlsx", XLSX)
