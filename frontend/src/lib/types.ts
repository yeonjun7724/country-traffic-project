/** P1/P2 화면 API 응답 타입 (백엔드 logisrisk/views 의 반환 구조와 1:1) */

export type Opt = { value: string; label: string };

// ── Network ──
export type Unit = {
  unitCode: string;
  unitName: string;
  routeName: string;
  lat: number;
  lon: number;
  score: number;
  grade: string;
  lisa_cluster: string;
  local_p_value: number | null;
  mean_freight_345_share: number | null;
  mean_freight_345_traffic: number | null;
  traffic_volatility: number | null;
  abs_imbalance_ratio: number | null;
  rank_base: number;
  rank_sim: number;
  rank_change: number;
};
export type UnitsView = {
  available: boolean;
  reason: string | null;
  units: Unit[];
  routes: string[];
  scenario: { id: string; params: { weights: Record<string, number> }; is_base: boolean; rank_changed: number; grade_changed: number } | null;
  route_summary: { routeName: string; units: number; mean_score: number; max_score: number; hh: number }[];
  lisa_counts: Record<string, number>;
};
export type Component = { key: string; column: string; label: string; default: number };
export type Proximity = {
  warehouse_id: string;
  name: string;
  units_in_radius: number;
  very_high: number;
  high_high: number;
  mean_score: number | null;
  nearest_unit: string;
  nearest_km: number;
};

// ── Transportation ──
export type CtsRow = {
  key: string | null;
  name?: string | null;
  shipments: number;
  orders: number;
  cost: number | null;
  cost_per_order: number | null;
  cost_per_kg: number | null;
  cost_per_km: number | null;
  distance_km: number | null;
  late_rate: number | null;
};
export type Fuel = {
  available: boolean;
  fuel_cost?: number | null;
  fuel_l?: number | null;
  fuel_share?: number | null;
  fuel_l_sources?: Record<string, number>;
  price_sources?: Record<string, number>;
  uses_external_price?: boolean;
  vehicles?: {
    vehicle_id: string | null;
    carrier: string | null;
    vehicle_type: string | null;
    shipments: number;
    distance_km: number | null;
    fuel_l: number | null;
    fuel_cost: number | null;
    km_per_l_spec: number | null;
    km_per_l_actual: number | null;
    eff_gap_pct: number | null;
    total_cost: number | null;
  }[];
};
export type PlanningMeta = { missing: string[]; warehouses: Opt[]; days: { orders: string[]; shipments: string[] } };
export type PlanSummary = {
  vehicles_used?: number;
  stops_planned?: number;
  stops_unassigned?: number;
  distance_km?: number;
  duration_h?: number;
  est_cost?: number | null;
  cost_complete?: boolean;
  avg_load_factor?: number | null;
  method?: string;
  distance_basis?: string;
  recorded_distance_km?: number | null;
};
export type Plan = {
  status: "ok" | "empty";
  reason?: string;
  source: "orders" | "shipments";
  day: string;
  warehouse_id: string;
  params: Record<string, number | null>;
  depot: { name: string; lat: number; lon: number };
  inputs: { stops: number; orders: number; vehicles: number; demand_kg: number; unknown_weight_stops: number };
  proposed: {
    summary: PlanSummary;
    routes: Record<string, unknown>[];
    stops: { route: number; vehicle_id: string; seq: number; stop_id: string; name: string; lat: number; lon: number; demand_kg: number | null }[];
    unassigned: Record<string, unknown>[];
    violations: string[];
    warnings: string[];
  };
  baseline: { summary: PlanSummary; violations: string[]; warnings: string[] } | null;
  comparison: Record<string, number | string | null>[] | null;
};

// ── Inventory ──
export type InvRow = {
  sku_id: string;
  sku_name?: string;
  warehouse_id: string;
  on_hand?: number;
  available: number;
  inbound_qty?: number;
  std_daily_demand?: number | null;
  avg_daily_demand: number | null;
  days_of_supply: number | null;
  safety_stock: number | null;
  reorder_point: number | null;
  recommended_qty: number | null;
  stockout_risk: string;
  basis: string | null;
  lead_time_days?: number | null;
};
export type InventoryView =
  | { status: "missing" | "not_computable"; reason: string; missing?: string[] }
  | {
      status: "ok";
      snapshot_date: string;
      demand_window: string;
      z: number;
      service_level: number;
      summary: { sku_locations: number; stockout: number; high_risk: number; stockout_rate: number | null; recommended_total: number };
      assumptions: string[];
      rows: InvRow[];
    };
export type Forecast =
  | { status: "missing" | "not_computable"; reason: string }
  | {
      status: "ok";
      series: { date: string; qty: number }[];
      backtest: { model: string; WAPE: number | null; MAE: number | null; Bias: number | null; "MAPE(0제외)": number | null; "MAPE 제외건"?: number }[];
      best: string;
      horizon: number;
    };

// ── Fuel & Risk ──
export type Diesel =
  | { status: "missing"; reason: string }
  | {
      status: "ok";
      n_total: number;
      n_computable: number;
      coverage: number;
      fuel_l_sources: Record<string, number>;
      price_sources: Record<string, number>;
      base_fuel_cost: number;
      base_total_cost: number | null;
      rows: { diesel_pct: number; fuel_cost_delta: number; total_cost_delta_pct: number | null }[];
      assumptions: string[];
      by: Record<string, number | string | null>[];
    };
export type Market = {
  available: boolean;
  event_date?: string;
  event_label?: string;
  history?: { date: string; diesel_price: number; gasoline_price: number }[];
  inferred_weight?: number | null;
  weight?: number | null;
  warnings?: string[];
  forecast?: {
    date: string;
    diesel_price_prophet: number;
    diesel_price_lstm: number;
    diesel_price_ensemble: number;
    diesel_price_prophet_lower: number;
    diesel_price_prophet_upper: number;
    reweighted: number;
    diesel_change_rate: number;
    diesel_shock_index: number;
    risk_level: string;
  }[];
  change_range?: [number, number];
};
export type Traffic = {
  available: boolean;
  event_label?: string;
  comparison?: {
    pre_days: number;
    post_days: number;
    pre_period: string;
    post_period: string;
    pre_mean?: number;
    post_mean?: number;
    change_pct?: number;
    change_pct_dow_adj?: number;
    yoy_pct?: number | null;
    caveat?: string;
    status?: string;
  };
  weekly?: { date: string; freight_345_traffic: number; passenger_126_traffic: number }[];
};
export type Finding = { level: "ok" | "info" | "warn" | "error"; title: string; detail: string };
export type Audit = {
  findings: Finding[];
  provenance: { key: string; source: string; kind: string; kind_label: string; period_start: string | null; period_end: string | null; n: number | null; method: string | null; warnings: string[] }[];
  missing: string[];
};

// ── Scenario Lab ──
export type ScenarioInput = {
  name: string;
  diesel_pct: number;
  demand_pct: number;
  rate_pct: number;
  fleet_change: number;
  trips_per_vehicle_day: number;
};
export type EngineResult = {
  status: string;
  baseline: Record<string, number | null>;
  scenario: Record<string, number | null>;
  delta_total: number;
  delta_pct: number;
  contribution: Record<string, number>;
  assumptions: string[];
  data_quality: { fuel_cost_sources: Record<string, number>; trips_with_capacity: number; trips_total: number; shipments_without_vehicle: number };
  params: ScenarioInput;
};
export type Compare =
  | { status: "missing" | "not_computable"; reason: string }
  | {
      status: "ok";
      rows: { key: string; label: string; unit: string; baseline: number | null; a: number | null; b: number | null; a_delta: number | null; b_delta: number | null }[];
      a: EngineResult;
      b: EngineResult;
    };
export type Sens = { factor: string; change_pct: number; delta_total: number; delta_pct: number };
export type Outage =
  | { status: "not_computable" | "infeasible"; reason: string }
  | {
      status: "ok";
      stores: { store_id: string; store_name: string; region: string; orders: number; dist_from_closed_km: number; alt_warehouse: string; dist_from_alt_km: number; dist_change_km: number }[];
      capacity: { warehouse_id: string; current_orders_per_day: number; added_orders_per_day: number; daily_capacity_orders: number | null; utilization_after: number | null }[];
      assumptions: string[];
    };
export type ScenarioRow = {
  id: number;
  name: string;
  kind: string;
  status: "draft" | "proposed" | "approved" | "rejected" | "archived";
  calc_version: string;
  created_by: string;
  created_at: string;
  updated_at: string | null;
};
export type ScenarioDetail = ScenarioRow & {
  params: Record<string, unknown>;
  result: Record<string, unknown> | null;
  assumptions: string[] | null;
  data_versions: Record<string, { version: number; uploaded_at: string }> | null;
};

// ── Copilot ──
export type CopilotMeta = { llm: boolean; model: string | null; calls_used: number; calls_max: number; tools: { name: string; description: string }[] };
export type ChatReply = {
  answer: string;
  mode: "llm" | "fallback" | "unsupported" | "error";
  notice: string;
  steps: { tool: string; args?: Record<string, unknown> }[];
  results: unknown[];
  calls_used: number;
  calls_max: number;
};

// ── Reports / Alerts / Settings ──
export type Alert = { severity: "high" | "medium" | "low"; rule: string; message: string; source: string };
export type Rules = {
  otif_min: number | null;
  late_rate_max: number | null;
  monthly_cost_budget: number | null;
  stockout_max: number | null;
  data_stale_days: number | null;
  risk_vh_max: number | null;
};
export type Action = {
  id: number;
  title: string;
  source: string;
  detail: string;
  status: "open" | "in_progress" | "done" | "dismissed";
  owner: string | null;
  created_by: string;
  created_at: string;
  updated_at: string | null;
};
export type Targets = { otif: number | null; late_rate: number | null; load_factor: number | null; cost_per_order: number | null; max_cost_per_shipment: number | null };
export type SettingsView = {
  targets: Targets;
  default_targets: Targets;
  rules: Rules;
  system: { item: string; value: string }[];
  permissions: { permission: string; min_role: string; min_role_label: string }[];
};
export type AuditRow = { id: number; at: string; user_id: string; action: string; target: string; detail_json: string | null };
