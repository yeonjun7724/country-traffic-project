"""데이터·지표 출처(Provenance) 메타데이터.

모든 KPI/분석 결과는 Metric 으로 감싸서 원천·기간·단위·산식·분모·데이터 성격
(관측/예측/시뮬레이션/가정)·품질 경고를 함께 전달한다.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

Kind = Literal["observed", "forecast", "simulated", "assumption", "derived", "demo"]

KIND_LABEL = {
    "observed": "관측(실측)",
    "forecast": "모델 예측",
    "simulated": "시뮬레이션",
    "assumption": "단순 가정 기반 추정",
    "derived": "관측 기반 파생",
    "demo": "DEMO(가상 데이터)",
}


@dataclass
class Provenance:
    source: str
    kind: Kind = "observed"
    period_start: str | None = None
    period_end: str | None = None
    loaded_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    unit: str | None = None
    method: str | None = None
    n: int | None = None
    version: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Metric:
    key: str
    label: str
    value: float | None
    unit: str = ""
    definition: str = ""
    formula: str = ""
    numerator: float | None = None
    denominator: float | None = None
    n: int | None = None
    period: str = ""
    kind: Kind = "observed"
    status: Literal["ok", "not_computable"] = "ok"
    reason: str = ""
    previous: float | None = None
    target: float | None = None
    higher_is_better: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok" and self.value is not None and not (
            isinstance(self.value, float) and math.isnan(self.value)
        )

    @property
    def delta_pct(self) -> float | None:
        if not self.ok or self.previous in (None, 0) or (
            isinstance(self.previous, float) and math.isnan(self.previous)
        ):
            return None
        return (self.value / self.previous - 1.0) * 100.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["delta_pct"] = self.delta_pct
        return d


def not_computable(key: str, label: str, reason: str, **kw) -> Metric:
    return Metric(key=key, label=label, value=None, status="not_computable", reason=reason, **kw)


def safe_div(num: float, den: float) -> float | None:
    """0 분모·NaN 안전 나눗셈. 계산 불가면 None."""
    try:
        if den is None or num is None:
            return None
        if isinstance(den, float) and math.isnan(den):
            return None
        if den == 0:
            return None
        r = num / den
        return None if (isinstance(r, float) and math.isnan(r)) else float(r)
    except (TypeError, ZeroDivisionError):
        return None
