"""공통 의존성: 저장소·외부데이터 싱글턴, 세션 인증, 워크스페이스 컨텍스트, Workbench 캐시, 필터 파싱."""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from datetime import date

from fastapi import Depends, Header, HTTPException, Query, Request

from logisrisk.analytics.kpi import Filters
from logisrisk.config import access_code, default_workspace
from logisrisk.data.external import ExternalData, load_external
from logisrisk.data.store import Store
from logisrisk.security import PermissionDenied, UserContext, require
from logisrisk.services import Workbench
from logisrisk.views.control_tower import default_filters

LOCAL_USER = "local"  # 계정 체계 도입 전: 접근 코드 통과자 = 로컬 사용자 (Streamlit 앱과 동일 모델)

_store: Store | None = None
_ext: tuple[float, ExternalData] | None = None
_lock = threading.Lock()
EXT_TTL = 3600


def get_store() -> Store:
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                _store = Store()
    return _store


def get_external() -> ExternalData:
    global _ext
    now = time.time()
    if _ext is None or now - _ext[0] > EXT_TTL:
        with _lock:
            if _ext is None or now - _ext[0] > EXT_TTL:
                _ext = (now, load_external())
    return _ext[1]


def reset_singletons(store: Store | None = None):
    """테스트용: 저장소 교체 + 캐시 초기화."""
    global _store
    _store = store
    _wb_cache.clear()


# ── 인증 ──────────────────────────────────────────────────────────────────
def is_authenticated(request: Request) -> bool:
    return access_code() is None or bool(request.session.get("authed"))


def require_auth(request: Request) -> str:
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="접근 코드 인증이 필요합니다.")
    return request.session.get("user_id", LOCAL_USER)


# ── 워크스페이스 컨텍스트 ───────────────────────────────────────────────────
def get_ctx(user_id: str = Depends(require_auth),
            x_workspace: str | None = Header(default=None, alias="X-Workspace")) -> UserContext:
    wid = (x_workspace or default_workspace()).strip()
    try:
        return get_store().context_for(user_id, wid)
    except PermissionDenied:
        raise HTTPException(status_code=403, detail="이 워크스페이스에 접근할 권한이 없습니다.")


def permission(name: str):
    """엔드포인트별 권한 확인 의존성 (fail-closed)."""
    def dep(ctx: UserContext = Depends(get_ctx)) -> UserContext:
        try:
            require(ctx, name)
        except PermissionDenied as e:
            raise HTTPException(status_code=403, detail=str(e))
        return ctx
    return dep


# ── Workbench 캐시 (워크스페이스·역할·데이터 버전·설정 리비전) ────────────
_wb_cache: OrderedDict = OrderedDict()
_wb_locks: dict = {}
WB_CACHE_SIZE = 8


def _wb_key(store: Store, ctx: UserContext) -> tuple:
    versions = store.data_versions(ctx)
    return (ctx.workspace_id, ctx.role, tuple(sorted((k, v["dataset_id"]) for k, v in versions.items())),
            store.settings_revision(ctx))


def get_workbench(ctx: UserContext = Depends(permission("data.read"))) -> Workbench:
    store = get_store()
    key = _wb_key(store, ctx)
    hit = _wb_cache.get(key)
    if hit is not None:
        _wb_cache.move_to_end(key)
        return hit
    lock = _wb_locks.setdefault(key, threading.Lock())
    with lock:  # 같은 키의 동시 로딩 방지
        hit = _wb_cache.get(key)
        if hit is None:
            hit = Workbench.load(store, ctx, get_external())
            _wb_cache[key] = hit
            while len(_wb_cache) > WB_CACHE_SIZE:
                _wb_cache.popitem(last=False)
    _wb_locks.pop(key, None)
    return hit


# ── 필터 ──────────────────────────────────────────────────────────────────
def get_filters(wb: Workbench = Depends(get_workbench),
                start: date | None = None, end: date | None = None,
                warehouses: list[str] = Query(default=[]), regions: list[str] = Query(default=[]),
                carriers: list[str] = Query(default=[]), vehicles: list[str] = Query(default=[]),
                categories: list[str] = Query(default=[]), stores: list[str] = Query(default=[])) -> Filters:
    flt = default_filters(wb)
    b = wb.date_bounds()
    if start and end:
        if start > end:
            raise HTTPException(status_code=422, detail="시작일이 종료일보다 늦습니다.")
        if b is not None:  # 데이터 범위로 제한
            lo, hi = b[0].date(), b[1].date()
            start, end = max(start, lo), min(end, hi)
        flt.start, flt.end = start, end
    flt.warehouses, flt.regions, flt.carriers = warehouses, regions, carriers
    flt.vehicles, flt.categories, flt.stores = vehicles, categories, stores
    return flt
