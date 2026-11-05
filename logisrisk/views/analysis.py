"""04 Inventory · 05 Fuel & Risk · 06 Scenario Lab 뷰 모델."""
from __future__ import annotations

import pandas as pd

from ..analytics import cost, inventory, kpi, risk
from ..config import REFERENCE_EVENT_DATE, REFERENCE_EVENT_LABEL
from ..provenance import KIND_LABEL
from ..services import Workbench
from .serialize import jsonable, records


# ── 04 Demand & Inventory ─────────────────────────────────────────────
def inventory_view(wb: Workbench, service_level: float, window_days: int, review_days: float) -> dict:
    need = [e for e in ("inventory", "orders", "order_lines") if e not in wb.frames]
    if need:
        return {"status": "missing", "reason": f"필요한 데이터: {', '.join(need)}", "missing": need}
    r = inventory.replenishment(wb.frames, service_level=service_level, window_days=window_days, review_days=review_days)
    if r["status"] != "ok":
        return {"status": r["status"], "reason": r.get("reason")}
    t = r["table"]
    if "skus" in wb.frames and "name" in wb.frames["skus"].columns and "sku_name" not in t.columns:
        t = t.merge(wb.frames["skus"][["sku_id", "name"]].rename(columns={"name": "sku_name"}), on="sku_id", how="left")
    return {"status": "ok", "snapshot_date": r["snapshot_date"], "demand_window": r["demand_window"], "z": r["z"],
            "service_level": r["service_level"], "summary": {**jsonable(r["summary"]),
                                                             "recommended_total": jsonable(t["recommended_qty"].sum())},
            "assumptions": r["assumptions"], "rows": records(t)}


def sku_options(wb: Workbench) -> list[dict]:
    if "skus" in wb.frames:
        s = wb.frames["skus"]
        return [{"value": r.sku_id, "label": f"{getattr(r, 'name', r.sku_id)}"} for r in s.itertuples()]
    if "order_lines" in wb.frames:
        return [{"value": v, "label": v} for v in sorted(wb.frames["order_lines"]["sku_id"].unique())]
    return []


def forecast_view(wb: Workbench, sku: str, warehouse_id: str | None) -> dict:
    if "order_lines" not in wb.frames:
        return {"status": "missing", "reason": "주문상세 데이터가 없습니다."}
    fr = inventory.forecast_sku(wb.frames, sku, warehouse_id)
    if fr["status"] != "ok":
        return {"status": fr["status"], "reason": fr.get("reason")}
    s = fr["series"]
    return {"status": "ok", "series": [{"date": jsonable(d), "qty": jsonable(v)} for d, v in s.items()],
            "backtest": records(fr["backtest"]), "best": fr["best"], "horizon": fr["horizon"]}


# ── 05 Fuel & Risk ────────────────────────────────────────────────────
def diesel_view(wb: Workbench, flt: kpi.Filters, pcts: list[float], by: str) -> dict:
    if wb.fact is None:
        return {"status": "missing", "reason": "배송 데이터가 없습니다."}
    r = cost.diesel_sensitivity(wb.fact, flt, sorted(pcts), wb.frames.get("fuel_prices"), wb.external_diesel(), by=by)
    by_df = r.pop("by", None)
    return {"status": "ok", **jsonable(r), "by": records(by_df.head(200)) if by_df is not None else []}


def fuel_market(wb: Workbench, prophet_weight: float | None) -> dict:
    ext = wb.ext
    h, f = ext.fuel_history, ext.forecast
    if h is None:
        return {"available": False}
    w0 = risk.infer_ensemble_weight(f) if f is not None else None
    pw = w0 if prophet_weight is None else prophet_weight
    hist = h[["date", "diesel_price", "gasoline_price"]]
    out = {"available": True, "event_date": REFERENCE_EVENT_DATE, "event_label": REFERENCE_EVENT_LABEL,
           "history": records(hist), "inferred_weight": jsonable(w0), "weight": jsonable(pw),
           "warnings": list(ext.provenance["forecast"].warnings) if "forecast" in ext.provenance else []}
    if f is not None:
        ff = f.assign(reweighted=risk.reweight_ensemble(f, pw if pw is not None else 0.4))
        out["forecast"] = records(ff, ["date", "diesel_price_prophet", "diesel_price_lstm", "diesel_price_ensemble",
                                       "diesel_price_prophet_lower", "diesel_price_prophet_upper", "reweighted",
                                       "diesel_change_rate", "diesel_shock_index", "risk_level"])
        out["change_range"] = [jsonable(f["diesel_change_rate"].min()), jsonable(f["diesel_change_rate"].max())]
    return out


def traffic_view(wb: Workbench) -> dict:
    t = wb.ext.traffic
    if t is None:
        return {"available": False}
    r = risk.period_comparison(t, REFERENCE_EVENT_DATE)
    w = t.set_index("date")[["freight_345_traffic", "passenger_126_traffic"]].resample("W").mean().reset_index()
    return {"available": True, "comparison": jsonable(r), "weekly": records(w), "event_label": REFERENCE_EVENT_LABEL}


def audit_view(wb: Workbench) -> dict:
    prov = [{"key": k, "source": p.source, "kind": p.kind, "kind_label": KIND_LABEL.get(p.kind, p.kind),
             "period_start": p.period_start, "period_end": p.period_end, "n": p.n, "method": p.method,
             "warnings": list(p.warnings)} for k, p in wb.ext.provenance.items()]
    return {"findings": jsonable(wb.ext.findings), "provenance": jsonable(prov), "missing": list(wb.ext.missing)}


# ── 06 Scenario Lab ───────────────────────────────────────────────────
COMPARE_ROWS = (("total", "총 운송비", "원"), ("fuel", "연료비", "원"), ("nonfuel", "연료 외 비용", "원"),
                ("trips", "운행 수", "회"), ("distance_km", "운행거리(기록)", "km"), ("peak_daily_trips", "최대 일 운행", "회"),
                ("fleet", "가용 차량", "대"), ("days_fleet_short", "차량 부족 일수", "일"))


def _args(wb):
    return wb.frames.get("vehicles"), wb.frames.get("fuel_prices"), wb.external_diesel()


def scenario_compare(wb: Workbench, flt: kpi.Filters, a: cost.ScenarioParams, b: cost.ScenarioParams) -> dict:
    if wb.fact is None:
        return {"status": "missing", "reason": "Baseline 이 될 배송 실적이 없습니다."}
    ra = cost.scenario_engine(wb.fact, flt, a, *_args(wb))
    rb = cost.scenario_engine(wb.fact, flt, b, *_args(wb))
    if ra.get("status") != "ok":
        return {"status": ra.get("status"), "reason": ra.get("reason")}
    rows = []
    for key, lab, unit in COMPARE_ROWS:
        base = ra["baseline"].get(key)
        va, vb = ra["scenario"].get(key), rb["scenario"].get(key)
        rows.append({"key": key, "label": lab, "unit": unit, "baseline": base, "a": va, "b": vb,
                     "a_delta": None if va is None or base is None else va - base,
                     "b_delta": None if vb is None or base is None else vb - base})
    return jsonable({"status": "ok", "rows": rows, "a": ra, "b": rb})


def sensitivity_view(wb: Workbench, flt: kpi.Filters) -> list[dict]:
    if wb.fact is None:
        return []
    return records(cost.sensitivity(wb.fact, flt, *_args(wb)))


def outage_view(wb: Workbench, flt: kpi.Filters, warehouse_id: str) -> dict:
    r = cost.warehouse_outage(wb.frames, warehouse_id, flt=flt)
    if r["status"] != "ok":
        return {"status": r["status"], "reason": r.get("reason")}
    return {"status": "ok", "stores": records(r["stores"]), "capacity": records(r["capacity"]),
            "assumptions": r["assumptions"]}


def scenario_sheets(s: dict) -> dict[str, pd.DataFrame]:
    sheets = {"입력값": pd.DataFrame([s["params"]]), "가정": pd.DataFrame({"가정": s["assumptions"] or []})}
    for k, v in (s["result"] or {}).items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            sheets[str(k)[:28]] = pd.DataFrame(v)
        elif isinstance(v, dict):
            sheets[str(k)[:28]] = pd.json_normalize(v)
    return sheets
