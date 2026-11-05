"""업로드 파이프라인: 읽기 → 매핑 → 검증(참조 무결성 포함) → 원자적 저장."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import FIXTURE_DIR
from ..security import UserContext, require
from .schemas import ENTITIES, UPLOAD_ORDER
from .store import Store
from .validation import (ValidationResult, apply_mapping, auto_map, dangling_references, key_set, read_table,
                         validate)


def reference_keys(store: Store, ctx: UserContext, entity: str, pending: dict[str, pd.DataFrame] | None = None) -> dict[str, set[str]]:
    """외래키 검증용 참조 키 (업로드 대기 중인 동일 배치 데이터 우선)."""
    refs = {}
    for fk in ENTITIES[entity].foreign_keys:
        df = (pending or {}).get(fk.ref_entity)
        if df is None:
            df = store.active_frame(ctx, fk.ref_entity)
        if df is not None:
            refs[fk.ref_entity] = key_set(df, fk.ref_column)
    return refs


def validate_upload(store: Store, ctx: UserContext, entity: str, raw: pd.DataFrame, mapping: dict[str, str],
                    pending: dict[str, pd.DataFrame] | None = None) -> ValidationResult:
    require(ctx, "data.upload")
    res = validate(entity, apply_mapping(raw, mapping), reference_keys(store, ctx, entity, pending))
    if res.ok and len(res.clean):
        # 교체로 인해 기존 데이터의 참조가 끊기는지 (예: 새 배송지 목록에서 빠진 점포를 기존 주문이 참조)
        dependents = {n: store.active_frame(ctx, n) for n, s in ENTITIES.items()
                      if any(fk.ref_entity == entity for fk in s.foreign_keys)}
        dependents = {k: v for k, v in dependents.items() if v is not None}
        if dependents:
            pk = ENTITIES[entity].primary_key[0]
            res.warnings.extend(dangling_references(entity, key_set(res.clean, pk), dependents))
    return res


def commit(store: Store, ctx: UserContext, res: ValidationResult, *, filename: str, mapping: dict,
           is_demo: bool = False, source: str = "upload") -> int:
    if not res.ok:
        raise ValueError("치명 오류가 있어 저장할 수 없습니다: " + "; ".join(res.fatal))
    return store.commit_dataset(ctx, res.entity, res.clean, filename=filename, source=source, mapping=mapping,
                                warnings=res.warnings, input_rows=res.n_input, rejected_rows=res.n_error_rows,
                                is_demo=is_demo)


def load_demo(store: Store, ctx: UserContext, folder: Path = FIXTURE_DIR) -> dict[str, dict]:
    """DEMO 워크스페이스에 가상 데이터 적재 (의존 순서대로)."""
    if not ctx.is_demo_workspace:
        raise PermissionError("DEMO 데이터는 DEMO 워크스페이스에서만 불러올 수 있습니다.")
    report, pending = {}, {}
    for ent in UPLOAD_ORDER:
        p = Path(folder) / f"DEMO_{ent}.csv"
        if not p.exists():
            continue
        raw = read_table(p.read_bytes(), p.name)
        mp = auto_map(list(raw.columns), ent)
        res = validate_upload(store, ctx, ent, raw, mp, pending)
        pending[ent] = res.clean
        ds = commit(store, ctx, res, filename=p.name, mapping=mp, is_demo=True, source="demo_fixture")
        report[ent] = {"dataset_id": ds, "rows": res.n_valid, "errors": res.n_error_rows, "warnings": res.warnings}
    return report
