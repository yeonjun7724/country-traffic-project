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
    if v is pd.NaT:  # NaTType 은 datetime 의 하위 클래스라 아래 isoformat 분기로 가면 문자열 "NaT" 가 됨
        return None
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else (v.date().isoformat() if v == v.normalize() else v.isoformat())
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (Metric, Provenance)):
        return jsonable(v.to_dict())
    return v


def _column_values(s: pd.Series) -> list:
    """한 열을 JSON 값 목록으로 — jsonable 과 같은 규칙을 열 단위로 벡터화 (원장 수천 행에서 셀 단위 변환이 병목)."""
    dt = s.dtype
    if pd.api.types.is_bool_dtype(dt) and not isinstance(dt, pd.api.extensions.ExtensionDtype):
        return s.tolist()
    if pd.api.types.is_integer_dtype(dt) and not isinstance(dt, pd.api.extensions.ExtensionDtype):
        return s.tolist()
    if pd.api.types.is_float_dtype(dt) and not isinstance(dt, pd.api.extensions.ExtensionDtype):
        arr = s.to_numpy(dtype=float)
        out = arr.tolist()
        for i in np.flatnonzero(~np.isfinite(arr)):
            out[i] = None
        return out
    if pd.api.types.is_datetime64_any_dtype(dt):
        na = s.isna().to_numpy()
        midnight = (s == s.dt.normalize()).to_numpy()
        day = s.dt.strftime("%Y-%m-%d").tolist()
        out: list = [None] * len(s)
        for i, ts in enumerate(s.tolist()):
            if na[i]:
                continue
            out[i] = day[i] if midnight[i] else ts.isoformat()
        return out
    return [jsonable(v) for v in s.tolist()]


def records(df: pd.DataFrame | None, cols: list[str] | None = None, limit: int | None = None) -> list[dict]:
    if df is None or len(df) == 0:
        return []
    d = df[[c for c in cols if c in df.columns]] if cols else df
    if limit is not None:
        d = d.head(limit)
    keys = list(d.columns)
    values = [_column_values(d.iloc[:, j]) for j in range(len(keys))]
    return [dict(zip(keys, row)) for row in zip(*values)]


def metric(m: Metric) -> dict:
    d = jsonable(m.to_dict())
    d["ok"] = m.ok
    d["kind_label"] = KIND_LABEL.get(m.kind, m.kind)
    return d
