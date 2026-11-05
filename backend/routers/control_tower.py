"""01 Control Tower API."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from logisrisk.analytics.kpi import Filters
from logisrisk.reports.export import csv_bytes
from logisrisk.security import UserContext
from logisrisk.services import Workbench
from logisrisk.views import control_tower as V

from ..deps import get_filters, get_store, get_workbench, permission
from ..models import CtsRow, DailyPoint, ExternalSummary, LedgerOut, NetworkOut, OverviewOut

router = APIRouter(prefix="/control-tower")
LedgerKind = Literal["late", "cost", "all"]


@router.get("/overview", response_model=OverviewOut)
def overview(wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    return V.overview(wb, flt)


@router.get("/daily", response_model=list[DailyPoint])
def daily(wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    return V.daily(wb, flt)


@router.get("/network", response_model=NetworkOut)
def network(wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    return V.network(wb, flt)


@router.get("/cost-to-serve", response_model=list[CtsRow])
def cost_to_serve(dim: Literal["carrier", "warehouse_id", "region", "customer_group"] = "carrier",
                  wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    return V.cost_to_serve(wb, flt, dim)


@router.get("/ledger", response_model=LedgerOut)
def ledger(kind: LedgerKind = "late", selected: list[str] = Query(default=[]),
           limit: int = Query(default=2000, ge=1, le=20000),
           wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    return V.ledger(wb, flt, kind, selected or None, limit)


@router.get("/ledger.csv")
def ledger_csv(kind: LedgerKind = "late", selected: list[str] = Query(default=[]),
               ctx: UserContext = Depends(permission("data.export")),
               wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    if ctx.workspace_id != wb.ctx.workspace_id:
        raise HTTPException(status_code=409, detail="워크스페이스 불일치")
    df = V.ledger_frame(wb, flt, kind, selected or None)
    get_store().log(ctx, "export.csv", f"ledger_{kind}", {"rows": len(df), "filters": flt.describe()})
    return Response(csv_bytes(df), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="ledger_{kind}.csv"'})


@router.get("/external", response_model=ExternalSummary)
def external(wb: Workbench = Depends(get_workbench)):
    return V.external_summary(wb)
