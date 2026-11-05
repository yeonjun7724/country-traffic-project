"""Data Hub 뷰 모델: 엔터티 적재 현황·데이터 품질·배송 원장 연결 품질·스키마."""
from __future__ import annotations

import json

import pandas as pd

from ..data.schemas import ENTITIES, UPLOAD_ORDER
from ..services import Workbench
from .serialize import jsonable


def entity_status(wb: Workbench) -> list[dict]:
    rows = []
    for i, e in enumerate(UPLOAD_ORDER, start=1):
        v = wb.versions.get(e)
        spec = ENTITIES[e]
        rows.append({"order": i, "entity": e, "label": spec.label, "loaded": bool(v),
                     "version": v["version"] if v else None, "rows": v["rows"] if v else None,
                     "period": v["period"] if v and v["period"] != "~" else None,
                     "uploaded_at": v["uploaded_at"] if v else None, "demo": bool(v and v["demo"]),
                     "required_refs": [fk.ref_entity for fk in spec.foreign_keys]})
    return rows


def linkage_quality(fact: pd.DataFrame | None) -> list[dict]:
    if fact is None:
        return []
    f = fact
    n = len(f)
    checks = [("주문 미연결 배송", f["store_id"].isna()), ("차량 미배정 배송", f["vehicle_id"].isna()),
              ("실제 배송일 없음", f["actual_delivery_date"].isna()), ("운송비 없음", f["cost"].isna()),
              ("운행거리 없음", f["distance_km"].isna()), ("주문중량 계산 불가", f["order_weight_kg"].isna())]
    return [{"check": lab, "count": int(m.sum()), "total": n} for lab, m in checks]


def quality(wb: Workbench, datasets: pd.DataFrame) -> list[dict]:
    """활성 엔터티별 컬럼 결측률·고유값 + 저장 시 경고."""
    out = []
    for ent, df in wb.frames.items():
        act = datasets[(datasets["entity"] == ent) & datasets["is_active"]] if len(datasets) else datasets
        warns = json.loads(act.iloc[0]["warnings_json"] or "[]") if len(act) else []
        cols = [{"field": c, "missing": int(df[c].isna().sum()), "missing_rate": float(df[c].isna().mean()) if len(df) else 0.0,
                 "unique": int(df[c].nunique())} for c in df.columns]
        out.append({"entity": ent, "label": ENTITIES[ent].label, "rows": int(len(df)), "warnings": warns,
                    "columns": cols})
    return out


def schema(entity: str) -> dict:
    spec = ENTITIES[entity]
    return {"entity": entity, "label": spec.label, "description": spec.description or "",
            "primary_key": list(spec.primary_key),
            "foreign_keys": [{"column": k.column, "ref_entity": k.ref_entity, "ref_column": k.ref_column}
                             for k in spec.foreign_keys],
            "fields": [jsonable({"name": f.name, "label": f.label, "type": f.type, "required": f.required,
                                 "unit": f.unit, "allowed": list(f.allowed) if f.allowed else [],
                                 "min": f.min, "max": f.max, "aliases": list(f.aliases)}) for f in spec.fields]}
