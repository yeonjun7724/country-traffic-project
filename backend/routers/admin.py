"""07 AI Copilot · 09 Reports & Alerts · 10 Settings API."""
from __future__ import annotations

from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field

from logisrisk.analytics.alerts import DEFAULT_RULES
from logisrisk.analytics.kpi import Filters
from logisrisk.config import AI_MAX_CALLS_PER_SESSION, OPENAI_MODEL, openai_api_key
from logisrisk.copilot import agent
from logisrisk.copilot.tools import TOOLS
from logisrisk.security import PermissionDenied, UserContext
from logisrisk.services import DEFAULT_TARGETS, Workbench
from logisrisk.views import admin as AD
from logisrisk.views.serialize import jsonable, records

from ..deps import get_filters, get_store, get_workbench, permission

router = APIRouter()
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ── 07 AI Copilot ─────────────────────────────────────────────────────
@router.get("/copilot/meta")
def copilot_meta(request: Request, _: UserContext = Depends(permission("ai.use"))):
    return {"llm": bool(openai_api_key()), "model": OPENAI_MODEL if openai_api_key() else None,
            "calls_used": int(request.session.get("ai_calls", 0)), "calls_max": AI_MAX_CALLS_PER_SESSION,
            "tools": [{"name": k, "description": d} for k, (_, d, _) in TOOLS.items()]}


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=20)


@router.post("/copilot/chat")
async def copilot_chat(body: ChatIn, request: Request, ctx: UserContext = Depends(permission("ai.use")),
                       wb: Workbench = Depends(get_workbench)):
    used = int(request.session.get("ai_calls", 0))
    r = await run_in_threadpool(agent.run, wb, body.message, [t.model_dump() for t in body.history[-10:]],
                                calls_used=used, max_calls=AI_MAX_CALLS_PER_SESSION)
    request.session["ai_calls"] = used + r.llm_calls
    return jsonable({"answer": r.answer, "mode": r.mode, "notice": r.notice, "steps": r.steps,
                     "results": r.tool_results, "calls_used": used + r.llm_calls, "calls_max": AI_MAX_CALLS_PER_SESSION})


# ── 09 Reports ────────────────────────────────────────────────────────
def _sections(sections: list[str]) -> list[str]:
    bad = [s for s in sections if s not in AD.REPORT_SECTIONS]
    if bad:
        raise HTTPException(status_code=422, detail=f"알 수 없는 섹션: {', '.join(bad)}")
    return sections or AD.DEFAULT_SECTIONS


@router.get("/reports/meta")
def report_meta(_: UserContext = Depends(permission("data.read"))):
    return {"sections": AD.REPORT_SECTIONS, "default": AD.DEFAULT_SECTIONS}


@router.get("/reports/preview")
def report_preview(sections: list[str] = Query(default=[]), wb: Workbench = Depends(get_workbench),
                   flt: Filters = Depends(get_filters)):
    return AD.report_preview(wb, flt, _sections(sections))


@router.get("/reports/excel")
def report_excel(sections: list[str] = Query(default=[]), ctx: UserContext = Depends(permission("data.export")),
                 wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    data = AD.report_excel(wb, flt, _sections(sections))
    get_store().log(ctx, "export.xlsx", "report", {"filters": flt.describe()})
    return Response(data, media_type=XLSX, headers={
        "Content-Disposition": f'attachment; filename="logisrisk_report_{pd.Timestamp.now():%Y%m%d_%H%M}.xlsx"'})


@router.get("/reports/summary.html")
def report_html(sections: list[str] = Query(default=[]), ctx: UserContext = Depends(permission("data.export")),
                wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    h = AD.report_html(wb, flt, _sections(sections))
    get_store().log(ctx, "export.html", "executive_summary", {"filters": flt.describe()})
    return Response(h.encode("utf-8"), media_type="text/html; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="executive_summary.html"'})


# ── Alerts & Actions ──────────────────────────────────────────────────
@router.get("/alerts")
def alerts_now(wb: Workbench = Depends(get_workbench), flt: Filters = Depends(get_filters)):
    return {"rules": jsonable(wb.rules), "alerts": jsonable(AD.current_alerts(wb, flt)), "period": flt.describe()}


class RulesIn(BaseModel):
    otif_min: float | None = Field(None, ge=0, le=1)
    late_rate_max: float | None = Field(None, ge=0, le=1)
    monthly_cost_budget: float | None = Field(None, ge=0)
    stockout_max: int | None = Field(None, ge=0)
    data_stale_days: int | None = Field(None, ge=1, le=365)
    risk_vh_max: int | None = Field(None, ge=0)


@router.put("/alerts/rules")
def alerts_rules(body: RulesIn, ctx: UserContext = Depends(permission("settings.manage"))):
    rules = {**DEFAULT_RULES, **body.model_dump()}
    get_store().set_setting(ctx, "alert_rules", rules)
    return rules


@router.get("/actions")
def actions_list(ctx: UserContext = Depends(permission("data.read"))):
    return records(get_store().list_actions(ctx))


class ActionIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    source: str = Field("", max_length=200)
    detail: str = Field("", max_length=2000)


@router.post("/actions")
def actions_create(body: ActionIn, ctx: UserContext = Depends(permission("scenario.save"))):
    return {"id": get_store().create_action(ctx, body.title, body.source, body.detail)}


class ActionStatusIn(BaseModel):
    status: Literal["open", "in_progress", "done", "dismissed"]
    owner: str | None = Field(None, max_length=100)


@router.patch("/actions/{aid}")
def actions_status(aid: int, body: ActionStatusIn, ctx: UserContext = Depends(permission("action.manage"))):
    try:
        get_store().set_action_status(ctx, aid, body.status, body.owner)
    except PermissionDenied as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"id": aid, "status": body.status}


# ── 10 Settings ───────────────────────────────────────────────────────
@router.get("/settings")
def settings_get(wb: Workbench = Depends(get_workbench)):
    return {"targets": jsonable(wb.targets), "default_targets": jsonable(DEFAULT_TARGETS), "rules": jsonable(wb.rules),
            "system": AD.system_status(wb), "permissions": AD.permissions_table()}


class TargetsIn(BaseModel):
    otif: float | None = Field(None, ge=0, le=1)
    late_rate: float | None = Field(None, ge=0, le=1)
    load_factor: float | None = Field(None, ge=0, le=1)
    cost_per_order: float | None = Field(None, ge=0)
    max_cost_per_shipment: float | None = Field(None, ge=0)


@router.put("/settings/targets")
def settings_targets(body: TargetsIn, ctx: UserContext = Depends(permission("settings.manage"))):
    t = {k: (v if v else None) if k in ("cost_per_order", "max_cost_per_shipment") else v for k, v in body.model_dump().items()}
    get_store().set_setting(ctx, "targets", t)
    return t


@router.get("/audit")
def audit(limit: int = Query(300, ge=1, le=2000), ctx: UserContext = Depends(permission("audit.read"))):
    return records(get_store().audit_log(ctx, limit))
