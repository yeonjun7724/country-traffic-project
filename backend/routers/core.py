"""인증 · 사용자/워크스페이스 · 필터 메타 · 전역 검색."""
from __future__ import annotations

import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from logisrisk import CALC_VERSION, __version__
from logisrisk.config import access_code, openai_api_key
from logisrisk.security import PERMISSIONS, ROLE_LABEL, UserContext
from logisrisk.services import Workbench
from logisrisk.views import search as SV
from logisrisk.views.control_tower import default_filters

from ..deps import LOCAL_USER, get_ctx, get_store, get_workbench, is_authenticated
from ..models import AuthStatus, FilterMeta, LoginIn, MeOut, SearchGroup, WorkspaceOut

router = APIRouter()

MAX_FAILS = 5
_ip_fails: dict[str, list[float]] = {}  # IP 별 실패 시각 (세션을 새로 만들어 우회하는 시도 제한)
IP_WINDOW = 900


def _ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


def _locked(request: Request) -> bool:
    now = time.time()
    recent = [t for t in _ip_fails.get(_ip(request), []) if now - t < IP_WINDOW]
    _ip_fails[_ip(request)] = recent
    return request.session.get("fails", 0) >= MAX_FAILS or len(recent) >= MAX_FAILS * 4


@router.get("/auth/status", response_model=AuthStatus)
def auth_status(request: Request):
    return AuthStatus(access_code_required=access_code() is not None, authenticated=is_authenticated(request),
                      locked=_locked(request))


@router.post("/auth/login", response_model=AuthStatus)
def login(body: LoginIn, request: Request):
    code = access_code()
    if code is None:
        request.session.update(authed=True, user_id=LOCAL_USER)
        return AuthStatus(access_code_required=False, authenticated=True)
    if _locked(request):
        raise HTTPException(status_code=429, detail="시도 횟수를 초과했습니다. 잠시 후 다시 시도하세요.")
    if hmac.compare_digest(body.code.encode(), code.encode()):
        request.session.clear()
        request.session.update(authed=True, user_id=LOCAL_USER)
        return AuthStatus(access_code_required=True, authenticated=True)
    request.session["fails"] = request.session.get("fails", 0) + 1
    _ip_fails.setdefault(_ip(request), []).append(time.time())
    raise HTTPException(status_code=401, detail="접근 코드가 올바르지 않습니다.")


@router.post("/auth/logout", response_model=AuthStatus)
def logout(request: Request):
    request.session.clear()
    return AuthStatus(access_code_required=access_code() is not None, authenticated=access_code() is None)


@router.get("/me", response_model=MeOut)
def me(ctx: UserContext = Depends(get_ctx), wb: Workbench = Depends(get_workbench)):
    wss = [WorkspaceOut(id=w["id"], name=w["name"], is_demo=bool(w["is_demo"]), role=w["role"])
           for w in get_store().workspaces_for(ctx.user_id)]
    cur = next(w for w in wss if w.id == ctx.workspace_id)
    last = max((v["uploaded_at"] for v in wb.versions.values()), default=None)
    return MeOut(user_id=ctx.user_id, display_name=ctx.display_name or ctx.user_id, role=ctx.role,
                 role_label=ROLE_LABEL.get(ctx.role, ctx.role),
                 permissions=sorted(p for p in PERMISSIONS if ctx.can(p)), workspace=cur, workspaces=wss,
                 has_ops_data=wb.has_ops_data, is_demo=wb.is_demo, data_updated_at=last,
                 app_version=__version__, calc_version=CALC_VERSION, ai_enabled=bool(openai_api_key()))


@router.get("/filters", response_model=FilterMeta)
def filter_meta(wb: Workbench = Depends(get_workbench)):
    b = wb.date_bounds()
    d = default_filters(wb)
    names = {}
    for ent, key in (("warehouses", "warehouse_id"), ("stores", "store_id")):
        df = wb.frames.get(ent)
        if df is not None and "name" in df.columns:
            names[key] = dict(zip(df[key].astype(str), df["name"].astype(str)))

    def opts(col):
        return [{"value": v, "label": names.get(col, {}).get(v, v)} for v in wb.options(col)]

    return FilterMeta(
        bounds={"min": b[0].date().isoformat(), "max": b[1].date().isoformat()} if b else None,
        default={"start": d.start.isoformat(), "end": d.end.isoformat()} if d.start else None,
        options={k: opts(c) for k, c in (("warehouses", "warehouse_id"), ("regions", "region"),
                                          ("carriers", "carrier"), ("vehicles", "vehicle_id"),
                                          ("categories", "category"), ("stores", "store_id"))})


@router.get("/search", response_model=list[SearchGroup])
def search(q: str, wb: Workbench = Depends(get_workbench)):
    return SV.search(wb, q[:100])
