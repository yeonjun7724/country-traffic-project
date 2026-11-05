"""FastAPI 앱 진입점.

실행 (개발):  uvicorn backend.main:app --reload --port 8000
운영(Railway): Dockerfile.web — Next.js 정적 빌드(frontend/out)를 같은 서비스에서 함께 서빙 (도메인 1개).
"""
from __future__ import annotations

import logging
import mimetypes
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from logisrisk import __version__
from logisrisk.config import ROOT, auto_seed_demo
from logisrisk.security import PermissionDenied

from .deps import get_external, get_store
from .routers import admin, analysis, control_tower, core, data_hub

log = logging.getLogger("logisrisk.api")
mimetypes.add_type("text/javascript", ".mjs")  # 모듈 워커(MapLibre)는 JS MIME 이 아니면 로드 거부됨
FRONTEND_DIR = Path(os.environ.get("LOGISRISK_FRONTEND_DIR", ROOT / "frontend" / "out"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    store, ext = get_store(), get_external()
    if auto_seed_demo():
        from logisrisk.data.seed import ensure_demo_seeded
        try:
            ensure_demo_seeded(store, ext)
        except Exception:  # 시드 실패가 기동을 막지 않도록 (Data Hub 에서 수동 적재 가능)
            log.exception("DEMO seed failed")
    yield


def create_app(seed: bool = True) -> FastAPI:
    app = FastAPI(title="LogisRisk Enterprise API", version=__version__, lifespan=lifespan if seed else None,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

    secret = os.environ.get("LOGISRISK_SESSION_SECRET") or secrets.token_urlsafe(32)
    on_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT"))
    app.add_middleware(SessionMiddleware, secret_key=secret, session_cookie="lr_session", max_age=60 * 60 * 12,
                       same_site="lax", https_only=on_railway)
    origins = [o.strip() for o in os.environ.get("LOGISRISK_CORS_ORIGINS", "").split(",") if o.strip()]
    if origins:  # 개발 시 Next dev 서버(예: http://localhost:3000)
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                           allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.url.path.startswith("/api/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @app.exception_handler(PermissionDenied)
    async def _denied(_: Request, exc: PermissionDenied):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    for r in (core.router, control_tower.router, data_hub.router, analysis.router, admin.router):
        app.include_router(r, prefix="/api")

    if FRONTEND_DIR.is_dir():
        app.mount("/_next", StaticFiles(directory=FRONTEND_DIR / "_next"), name="next-assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            # Next.js 정적 export (trailingSlash) — /control-tower/ → control-tower/index.html
            if path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            base = FRONTEND_DIR.resolve()
            for cand in (base / path, base / path / "index.html", base / f"{path}.html"):
                try:
                    c = cand.resolve()
                except OSError:
                    continue
                if c.is_file() and base in c.parents:  # 경로 이탈(../) 차단
                    return FileResponse(c)
            nf = base / "404.html"
            return FileResponse(nf, status_code=404) if nf.is_file() else JSONResponse(status_code=404, content={})
    return app


app = create_app()
