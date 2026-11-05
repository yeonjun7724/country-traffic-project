"""JSON 직렬화 도우미: NaN/Inf → None, numpy·pandas 스칼라 → 파이썬 기본형, 날짜 → ISO 문자열."""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from ..provenance import KIND_LABEL, Metric, Provenance


def jsonable(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [jsonable(x) for x in v]
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else (v.date().isoformat() if v == v.normalize() else v.isoformat())
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if v is pd.NaT:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (Metric, Provenance)):
        return jsonable(v.to_dict())
    return v


def records(df: pd.DataFrame | None, cols: list[str] | None = None, limit: int | None = None) -> list[dict]:
    if df is None or len(df) == 0:
        return []
    d = df[[c for c in cols if c in df.columns]] if cols else df
    if limit is not None:
        d = d.head(limit)
    return [{k: jsonable(v) for k, v in row.items()} for row in d.to_dict(orient="records")]


def metric(m: Metric) -> dict:
    d = jsonable(m.to_dict())
    d["ok"] = m.ok
    d["kind_label"] = KIND_LABEL.get(m.kind, m.kind)
    return d
