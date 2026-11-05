"""08 Data Hub API: 업로드 → 매핑 → 검증 → 원자적 저장, 버전·롤백, 품질, 스키마, 연동 상태.

업로드 원본은 매핑 변경 시 재검증을 위해 서버 메모리에 임시 보관(1시간)한다. DB 에는 저장 확정 시에만 기록.
"""
from __future__ import annotations

import io
import secrets
import threading
import time
from dataclasses import dataclass, field

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from logisrisk.data import ingest
from logisrisk.data.connectors import available_statuses
from logisrisk.data.schemas import ENTITIES
from logisrisk.data.validation import ValidationResult, auto_map, read_table
from logisrisk.provenance import KIND_LABEL
from logisrisk.reports.export import csv_bytes
from logisrisk.security import PermissionDenied, UserContext
from logisrisk.services import Workbench
from logisrisk.views import data_hub as DV
from logisrisk.views.serialize import jsonable, records

from ..deps import get_store, get_workbench, permission
from ..models import (CommitIn, CommitOut, DatasetOut, DemoLoadOut, EntityStatus, IntegrationsOut, MappingIn,
                      QualityOut, SchemaOut, UploadOut, ValidationOut)

router = APIRouter(prefix="/data")

MAX_BYTES = 100 * 1024 * 1024
TTL = 3600
MAX_STAGED = 50


@dataclass
class Staged:
    id: str
    user_id: str
    workspace_id: str
    entity: str
    filename: str
    data: bytes
    sheets: list[str]
    sheet: str | None
    raw: pd.DataFrame
    created: float = field(default_factory=time.time)
    mapping: dict[str, str] | None = None   # 검증에 사용한 매핑 (field → source)
    result: ValidationResult | None = None


_staged: dict[str, Staged] = {}
_slock = threading.Lock()


def _gc():
    now = time.time()
    with _slock:
        for k in [k for k, s in _staged.items() if now - s.created > TTL]:
            _staged.pop(k, None)
        while len(_staged) > MAX_STAGED:
            _staged.pop(min(_staged, key=lambda k: _staged[k].created), None)


def _get(upload_id: str, ctx: UserContext) -> Staged:
    _gc()
    s = _staged.get(upload_id)
    if s is None or s.user_id != ctx.user_id or s.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="업로드를 찾을 수 없습니다 (만료되었거나 다른 워크스페이스).")
    return s


def _entity(entity: str) -> str:
    if entity not in ENTITIES:
        raise HTTPException(status_code=404, detail=f"알 수 없는 데이터 유형: {entity}")
    return entity


def _read(data: bytes, filename: str, sheet: str | None) -> tuple[pd.DataFrame, list[str], str | None]:
    sheets: list[str] = []
    if filename.lower().endswith((".xlsx", ".xls")):
        try:
            sheets = pd.ExcelFile(io.BytesIO(data)).sheet_names
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Excel 파일을 읽을 수 없습니다: {e}")
        sheet = sheet if sheet in sheets else sheets[0]
    try:
        raw = read_table(data, filename, sheet if sheets else 0)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    return raw, sheets, sheet if sheets else None


def _upload_out(s: Staged) -> UploadOut:
    auto = {v: k for k, v in auto_map(list(s.raw.columns), s.entity).items()}  # field → source
    return UploadOut(upload_id=s.id, entity=s.entity, filename=s.filename, sheets=s.sheets, sheet=s.sheet,
                     n_rows=len(s.raw), columns=[str(c) for c in s.raw.columns],
                     preview=records(s.raw, limit=20), auto_mapping=auto)


# ── 현황·스키마 ─────────────────────────────────────────────────────────
@router.get("/entities", response_model=list[EntityStatus])
def entities(wb: Workbench = Depends(get_workbench)):
    return DV.entity_status(wb)


@router.get("/schemas/{entity}", response_model=SchemaOut)
def schema(entity: str, _: UserContext = Depends(permission("data.read"))):
    return DV.schema(_entity(entity))


@router.get("/templates/{entity}.csv")
def template(entity: str, _: UserContext = Depends(permission("data.read"))):
    from logisrisk.data.schemas import template_frame
    return Response(csv_bytes(template_frame(_entity(entity))), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="template_{entity}.csv"'})


# ── 업로드 흐름 ─────────────────────────────────────────────────────────
@router.post("/uploads", response_model=UploadOut)
async def upload(entity: str = Form(...), file: UploadFile = File(...), sheet: str | None = Form(default=None),
                 ctx: UserContext = Depends(permission("data.upload"))):
    _entity(entity)
    name = file.filename or "upload.csv"
    if not name.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=415, detail="CSV 또는 Excel(.xlsx) 파일만 업로드할 수 있습니다.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="파일이 100MB 를 넘습니다.")
    if not data:
        raise HTTPException(status_code=422, detail="빈 파일입니다.")
    raw, sheets, sh = _read(data, name, sheet)
    s = Staged(id=secrets.token_urlsafe(12), user_id=ctx.user_id, workspace_id=ctx.workspace_id, entity=entity,
               filename=name, data=data, sheets=sheets, sheet=sh, raw=raw)
    _gc()
    with _slock:
        _staged[s.id] = s
    return _upload_out(s)


@router.put("/uploads/{upload_id}/sheet", response_model=UploadOut)
def change_sheet(upload_id: str, body: MappingIn, ctx: UserContext = Depends(permission("data.upload"))):
    s = _get(upload_id, ctx)
    s.raw, s.sheets, s.sheet = _read(s.data, s.filename, body.sheet)
    s.mapping, s.result = None, None
    return _upload_out(s)


@router.post("/uploads/{upload_id}/validate", response_model=ValidationOut)
def validate(upload_id: str, body: MappingIn, ctx: UserContext = Depends(permission("data.upload"))):
    s = _get(upload_id, ctx)
    spec_fields = {f.name for f in ENTITIES[s.entity].fields}
    cols = {str(c) for c in s.raw.columns}
    mapping = {f: c for f, c in body.mapping.items() if c}
    bad = [f for f in mapping if f not in spec_fields] + [c for c in mapping.values() if c not in cols]
    if bad:
        raise HTTPException(status_code=422, detail=f"알 수 없는 필드·컬럼: {', '.join(bad[:5])}")
    if len(set(mapping.values())) != len(mapping):
        raise HTTPException(status_code=422, detail="하나의 원본 컬럼을 여러 필드에 매핑할 수 없습니다.")
    src_map = {c: f for f, c in mapping.items()}  # ingest 는 source → field
    try:
        res = ingest.validate_upload(get_store(), ctx, s.entity, s.raw, src_map)
    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    s.mapping, s.result = mapping, res
    summ = (res.errors.groupby(["column", "message"]).size().reset_index(name="count")
            .sort_values("count", ascending=False)) if len(res.errors) else pd.DataFrame()
    prev = get_store().data_versions(ctx).get(s.entity)
    return ValidationOut(upload_id=s.id, entity=s.entity, ok=res.ok, n_input=res.n_input, n_valid=res.n_valid,
                         n_error_rows=res.n_error_rows, warnings=res.warnings, fatal=res.fatal,
                         error_summary=records(summ), errors=records(res.errors, limit=500),
                         clean_preview=records(res.clean, limit=10),
                         current_version=prev["version"] if prev else None, validated_mapping=mapping)


@router.get("/uploads/{upload_id}/errors.csv")
def error_rows(upload_id: str, ctx: UserContext = Depends(permission("data.upload"))):
    s = _get(upload_id, ctx)
    if s.result is None:
        raise HTTPException(status_code=409, detail="먼저 검증을 실행하세요.")
    return Response(csv_bytes(s.result.error_rows(s.raw)), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="errors_{s.entity}.csv"'})


@router.post("/uploads/{upload_id}/commit", response_model=CommitOut)
def commit(upload_id: str, body: CommitIn, ctx: UserContext = Depends(permission("data.upload"))):
    s = _get(upload_id, ctx)
    res = s.result
    if res is None or s.mapping is None:
        raise HTTPException(status_code=409, detail="검증 결과가 없습니다. 검증을 먼저 실행하세요.")
    if not res.ok:
        raise HTTPException(status_code=422, detail="치명 오류가 있어 저장할 수 없습니다: " + "; ".join(res.fatal))
    if not res.n_valid:
        raise HTTPException(status_code=422, detail="저장할 유효 행이 없습니다.")
    if res.n_error_rows and not body.acknowledge_excluded_rows:
        raise HTTPException(status_code=409, detail=f"오류 행 {res.n_error_rows}건 제외 저장에 동의가 필요합니다.")
    try:
        ds = ingest.commit(get_store(), ctx, res, filename=s.filename, mapping={c: f for f, c in s.mapping.items()},
                           is_demo=ctx.is_demo_workspace)
    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # 단일 트랜잭션 → 전체 롤백됨
        raise HTTPException(status_code=500, detail=f"저장 실패 — 전체 롤백됨: {type(e).__name__}")
    with _slock:
        _staged.pop(upload_id, None)
    v = get_store().data_versions(ctx).get(s.entity)
    return CommitOut(dataset_id=ds, entity=s.entity, version=v["version"] if v else None, rows=res.n_valid)


@router.delete("/uploads/{upload_id}", status_code=204)
def discard(upload_id: str, ctx: UserContext = Depends(permission("data.upload"))):
    _get(upload_id, ctx)
    with _slock:
        _staged.pop(upload_id, None)


@router.post("/demo", response_model=DemoLoadOut)
def load_demo(ctx: UserContext = Depends(permission("data.upload"))):
    if not ctx.is_demo_workspace:
        raise HTTPException(status_code=403, detail="샘플 데이터는 DEMO 워크스페이스에서만 불러올 수 있습니다.")
    rep = ingest.load_demo(get_store(), ctx)
    return DemoLoadOut(entities={k: v["rows"] for k, v in rep.items()})


# ── 버전·롤백 ───────────────────────────────────────────────────────────
@router.get("/datasets", response_model=list[DatasetOut])
def datasets(ctx: UserContext = Depends(permission("data.read"))):
    df = get_store().list_datasets(ctx)
    out = []
    for r in records(df):
        r["label"] = ENTITIES[r["entity"]].label if r["entity"] in ENTITIES else r["entity"]
        out.append(r)
    return out


@router.post("/datasets/{dataset_id}/activate", status_code=204)
def activate(dataset_id: int, ctx: UserContext = Depends(permission("dataset.activate"))):
    try:
        get_store().activate_dataset(ctx, dataset_id)
    except PermissionDenied as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/entities/{entity}/deactivate", status_code=204)
def deactivate(entity: str, ctx: UserContext = Depends(permission("dataset.activate"))):
    get_store().deactivate_entity(ctx, _entity(entity))


# ── 품질·연동 ───────────────────────────────────────────────────────────
@router.get("/quality", response_model=QualityOut)
def quality(wb: Workbench = Depends(get_workbench)):
    return QualityOut(entities=DV.quality(wb, get_store().list_datasets(wb.ctx)), linkage=DV.linkage_quality(wb.fact))


@router.get("/integrations", response_model=IntegrationsOut)
def integrations(wb: Workbench = Depends(get_workbench)):
    ext = [{"key": k, "source": p.source, "kind": p.kind, "kind_label": KIND_LABEL.get(p.kind, p.kind),
            "period_start": p.period_start, "period_end": p.period_end, "n": p.n, "method": p.method,
            "warnings": list(p.warnings)} for k, p in wb.ext.provenance.items()]
    return IntegrationsOut(connectors=[s.__dict__ for s in available_statuses()], external=jsonable(ext),
                           missing=list(wb.ext.missing))
