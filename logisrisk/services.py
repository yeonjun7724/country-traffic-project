"""서비스 계층: 사용자 컨텍스트 + 활성 데이터 + 설정을 묶은 Workbench.

UI(Streamlit)·AI 도구·(향후) API 가 공통으로 사용한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .analytics import kpi
from .analytics.alerts import DEFAULT_RULES
from .data.external import ExternalData
from .data.store import Store
from .security import UserContext, require

DEFAULT_TARGETS = {"otif": 0.95, "late_rate": 0.05, "load_factor": 0.80, "cost_per_order": None,
                   "max_cost_per_shipment": None}


@dataclass
class Workbench:
    store: Store
    ctx: UserContext
    ext: ExternalData
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    fact: pd.DataFrame | None = None
    versions: dict[str, dict] = field(default_factory=dict)
    targets: dict = field(default_factory=dict)
    rules: dict = field(default_factory=dict)

    @classmethod
    def load(cls, store: Store, ctx: UserContext, ext: ExternalData) -> "Workbench":
        require(ctx, "data.read")
        frames = store.active_frames(ctx)
        wb = cls(store=store, ctx=ctx, ext=ext, frames=frames, fact=kpi.build_fact(frames),
                 versions=store.data_versions(ctx),
                 targets={**DEFAULT_TARGETS, **(store.get_setting(ctx, "targets", {}) or {})},
                 rules={**DEFAULT_RULES, **(store.get_setting(ctx, "alert_rules", {}) or {})})
        return wb

    @property
    def has_ops_data(self) -> bool:
        return bool(self.frames)

    @property
    def is_demo(self) -> bool:
        return self.ctx.is_demo_workspace or any(v.get("demo") for v in self.versions.values())

    def date_bounds(self) -> tuple[pd.Timestamp, pd.Timestamp] | None:
        if self.fact is not None and self.fact["ship_date"].notna().any():
            return self.fact["ship_date"].min(), self.fact["ship_date"].max()
        o = self.frames.get("orders")
        if o is not None and len(o):
            return o["order_date"].min(), o["order_date"].max()
        return None

    def options(self, col: str) -> list[str]:
        src = {"warehouse_id": ("warehouses", "warehouse_id"), "region": ("stores", "region"),
               "carrier": ("vehicles", "carrier"), "vehicle_id": ("vehicles", "vehicle_id"),
               "category": ("skus", "category"), "store_id": ("stores", "store_id")}[col]
        df = self.frames.get(src[0])
        if df is None or src[1] not in df:
            return []
        return sorted(df[src[1]].dropna().astype(str).unique().tolist())

    def external_diesel(self) -> pd.DataFrame | None:
        h = self.ext.fuel_history
        return None if h is None else h[["date", "diesel_price"]]
