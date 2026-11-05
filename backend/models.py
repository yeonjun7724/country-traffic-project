"""API 응답 스키마 (OpenAPI → 프런트 타입 자동 생성)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Kind = Literal["observed", "forecast", "simulated", "assumption", "derived", "demo"]


class MetricOut(BaseModel):
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
    kind_label: str = ""
    status: Literal["ok", "not_computable"] = "ok"
    reason: str = ""
    previous: float | None = None
    target: float | None = None
    higher_is_better: bool = True
    warnings: list[str] = Field(default_factory=list)
    delta_pct: float | None = None
    ok: bool


class AlertOut(BaseModel):
    severity: Literal["high", "medium", "low"]
    rule: str
    message: str
    source: str


class OverviewOut(BaseModel):
    kpis: list[MetricOut]
    alerts: list[AlertOut]
    period: str


class AuthStatus(BaseModel):
    access_code_required: bool
    authenticated: bool
    locked: bool = False


class LoginIn(BaseModel):
    code: str = Field(min_length=1, max_length=200)


class WorkspaceOut(BaseModel):
    id: str
    name: str
    is_demo: bool
    role: str


class MeOut(BaseModel):
    user_id: str
    display_name: str
    role: str
    role_label: str
    permissions: list[str]
    workspace: WorkspaceOut
    workspaces: list[WorkspaceOut]
    has_ops_data: bool
    is_demo: bool
    data_updated_at: str | None
    app_version: str
    calc_version: str
    ai_enabled: bool


class Option(BaseModel):
    value: str
    label: str


class FilterMeta(BaseModel):
    bounds: dict[str, str] | None
    default: dict[str, str] | None
    options: dict[str, list[Option]]


class DailyPoint(BaseModel):
    date: str
    cost: float | None
    shipments: int
    late_rate: float | None


class StorePoint(BaseModel):
    store_id: str
    name: str | None = None
    region: str | None = None
    lat: float
    lon: float
    shipments: int | None = None
    orders: int | None = None
    cost: float | None = None
    cost_per_order: float | None = None
    late_rate: float | None = None


class WarehousePoint(BaseModel):
    warehouse_id: str
    name: str | None = None
    lat: float | None = None
    lon: float | None = None


class NetworkOut(BaseModel):
    stores: list[StorePoint]
    idle_stores: list[StorePoint]
    warehouses: list[WarehousePoint]


class CtsRow(BaseModel):
    key: str | None
    shipments: int
    orders: int
    cost: float | None
    cost_per_order: float | None
    cost_per_kg: float | None
    late_rate: float | None


class LedgerOut(BaseModel):
    rows: list[dict[str, Any]]
    total: int
    rule: str | None
    available: bool
    reason: str | None


class DieselOut(BaseModel):
    date: str | None
    price: float
    change_30d_pct: float | None


class ExternalSummary(BaseModel):
    available: bool
    units: int | None
    lisa_hh: int | None
    diesel: DieselOut | None
    audit_warnings: int


class SearchItem(BaseModel):
    id: Any
    title: str
    subtitle: Any | None = None


class SearchGroup(BaseModel):
    entity: str
    label: str
    total: int
    items: list[SearchItem]


# ── Data Hub ────────────────────────────────────────────────────────────
class EntityStatus(BaseModel):
    order: int
    entity: str
    label: str
    loaded: bool
    version: int | None
    rows: int | None
    period: str | None
    uploaded_at: str | None
    demo: bool
    required_refs: list[str]


class FieldSpecOut(BaseModel):
    name: str
    label: str
    type: str
    required: bool
    unit: str | None = ""
    allowed: list[str] = Field(default_factory=list)
    min: float | None = None
    max: float | None = None
    aliases: list[str] = Field(default_factory=list)


class SchemaOut(BaseModel):
    entity: str
    label: str
    description: str
    primary_key: list[str]
    foreign_keys: list[dict[str, str]]
    fields: list[FieldSpecOut]


class UploadOut(BaseModel):
    upload_id: str
    entity: str
    filename: str
    sheets: list[str]
    sheet: str | None
    n_rows: int
    columns: list[str]
    preview: list[dict[str, Any]]
    auto_mapping: dict[str, str]  # field → source column


class MappingIn(BaseModel):
    mapping: dict[str, str]  # field → source column
    sheet: str | None = None


class ErrorSummary(BaseModel):
    column: str
    message: str
    count: int


class ValidationOut(BaseModel):
    upload_id: str
    entity: str
    ok: bool
    n_input: int
    n_valid: int
    n_error_rows: int
    warnings: list[str]
    fatal: list[str]
    error_summary: list[ErrorSummary]
    errors: list[dict[str, Any]]
    clean_preview: list[dict[str, Any]]
    current_version: int | None
    validated_mapping: dict[str, str]


class CommitIn(BaseModel):
    acknowledge_excluded_rows: bool = False


class CommitOut(BaseModel):
    dataset_id: int
    entity: str
    version: int | None
    rows: int


class DatasetOut(BaseModel):
    id: int
    entity: str
    label: str
    version: int
    is_active: bool
    filename: str | None
    source: str | None
    uploaded_by: str | None
    uploaded_at: str | None
    row_count: int | None
    input_rows: int | None
    rejected_rows: int | None
    is_demo: bool
    period_start: str | None
    period_end: str | None


class ColumnQuality(BaseModel):
    field: str
    missing: int
    missing_rate: float
    unique: int


class EntityQuality(BaseModel):
    entity: str
    label: str
    rows: int
    warnings: list[str]
    columns: list[ColumnQuality]


class LinkageCheck(BaseModel):
    check: str
    count: int
    total: int


class QualityOut(BaseModel):
    entities: list[EntityQuality]
    linkage: list[LinkageCheck]


class ConnectorOut(BaseModel):
    name: str
    system: str
    configured: bool
    detail: str


class ProvenanceOut(BaseModel):
    key: str
    source: str
    kind: str
    kind_label: str
    period_start: str | None
    period_end: str | None
    n: int | None
    method: str | None
    warnings: list[str]


class IntegrationsOut(BaseModel):
    connectors: list[ConnectorOut]
    external: list[ProvenanceOut]
    missing: list[str]


class DemoLoadOut(BaseModel):
    entities: dict[str, int]
