"""Control Tower 뷰 모델: KPI·알림·배송 네트워크·일별 추이·Cost-to-Serve·예외 원장·외부 위험 요약."""
from __future__ import annotations

import pandas as pd

from ..analytics import alerts, inventory, kpi
from ..services import Workbench
from .serialize import jsonable, metric, records

KPI_KEYS = ["orders", "shipments", "volume_kg", "cost", "cost_per_order", "late_rate", "otif", "load_factor",
            "cost_per_km"]
LEDGER_COLS = ["shipment_id", "order_id", "ship_date", "planned_delivery_date", "actual_delivery_date", "delay_days",
               "store_id", "store_name", "region", "warehouse_id", "carrier", "vehicle_id", "ordered_qty",
               "delivered_qty", "load_kg_eff", "distance_km", "cost", "cost_source"]
CTS_DIMS = {"carrier": "운송사", "warehouse_id": "센터", "region": "권역", "customer_group": "거래처군"}


def default_filters(wb: Workbench) -> kpi.Filters:
    """기본 기간: 데이터 최신일 기준 최근 30일 (Streamlit 글로벌 필터와 동일 규칙)."""
    b = wb.date_bounds()
    if b is None:
        return kpi.Filters()
    lo, hi = b[0].date(), b[1].date()
    return kpi.Filters(start=max(lo, (b[1] - pd.Timedelta(days=29)).date()), end=hi)


def overview(wb: Workbench, flt: kpi.Filters) -> dict:
    ms = kpi.compute_with_comparison(wb.frames, wb.fact, flt, wb.targets)
    inv = inventory.replenishment(wb.frames) if "inventory" in wb.frames else None
    al = alerts.evaluate(ms, wb.rules, wb.versions, inv, period_days=flt.days)
    return {"kpis": [metric(ms[k]) for k in KPI_KEYS if k in ms], "alerts": jsonable(al),
            "period": flt.describe()}


def daily(wb: Workbench, flt: kpi.Filters) -> list[dict]:
    """일별 운송비·배송 건수·지연율 (지연 판정 가능한 배송만 분모)."""
    if wb.fact is None:
        return []
    x = kpi.apply_filters(wb.fact, flt)
    if x.empty:
        return []
    g = x.assign(_late=(x["on_time"] == 0).astype(float), _known=x["on_time"].notna().astype(float)) \
        .groupby("ship_date").agg(cost=("cost", lambda s: s.sum(min_count=1)), shipments=("shipment_id", "count"),
                                  late=("_late", "sum"), known=("_known", "sum"))
    g["late_rate"] = g["late"] / g["known"].where(g["known"] > 0)
    g = g.reset_index().rename(columns={"ship_date": "date"})
    return records(g, ["date", "cost", "shipments", "late_rate"])


def network(wb: Workbench, flt: kpi.Filters) -> dict:
    """지도: 배송 실적이 있는 배송지 / 기간 내 배송 없는 배송지(회색) / 센터."""
    sm = kpi.store_map_frame(wb.fact, wb.frames, flt)
    cols = ["store_id", "name", "region", "lat", "lon", "shipments", "orders", "cost", "cost_per_order", "late_rate"]
    if len(sm):
        has = sm["shipments"].fillna(0) > 0
        active, idle = sm[has], sm[~has]
    else:
        active = idle = sm
    wh = wb.frames.get("warehouses")
    return {"stores": records(active, cols),
            "idle_stores": records(idle, ["store_id", "name", "region", "lat", "lon"]),
            "warehouses": records(wh, ["warehouse_id", "name", "lat", "lon", "capacity_orders_per_day"])}


def cost_to_serve(wb: Workbench, flt: kpi.Filters, dim: str) -> list[dict]:
    if dim not in CTS_DIMS:
        raise ValueError(f"지원하지 않는 기준: {dim}")
    t = kpi.by_dimension(wb.fact, flt, dim)
    return records(t.rename(columns={dim: "key"}),
                   ["key", "shipments", "orders", "cost", "cost_per_order", "cost_per_kg", "late_rate"])


def ledger(wb: Workbench, flt: kpi.Filters, kind: str, stores: list[str] | None = None,
           limit: int | None = 5000) -> dict:
    """예외·전체 원장. kind = late | cost | all. stores 지정 시 해당 배송지로 제한 (지도·표 선택)."""
    if wb.fact is None:
        return {"rows": [], "total": 0, "rule": None, "available": False, "reason": "배송 데이터가 없습니다."}
    ex = kpi.exceptions(wb.fact, flt, wb.targets)
    if kind == "late":
        df = ex.get("late")
    elif kind == "cost":
        df = ex.get("cost_over")
        if df is None:
            return {"rows": [], "total": 0, "rule": None, "available": False,
                    "reason": "판정 기준 데이터 부족 (배송당 비용 목표 미설정이고 비용 표본 20건 미만)"}
    elif kind == "all":
        df = kpi.apply_filters(wb.fact, flt)
    else:
        raise ValueError(kind)
    if stores:
        df = df[df["store_id"].isin(stores)]
    return {"rows": records(df, LEDGER_COLS, limit), "total": int(len(df)),
            "rule": ex.get("cost_over_rule") if kind == "cost" else None, "available": True, "reason": None}


def ledger_frame(wb: Workbench, flt: kpi.Filters, kind: str, stores: list[str] | None = None) -> pd.DataFrame:
    """CSV 내보내기용 원장 (행 제한 없음)."""
    if wb.fact is None:
        return pd.DataFrame(columns=LEDGER_COLS)
    ex = kpi.exceptions(wb.fact, flt, wb.targets)
    df = {"late": ex.get("late"), "cost": ex.get("cost_over"), "all": kpi.apply_filters(wb.fact, flt)}.get(kind)
    if df is None:
        return pd.DataFrame(columns=LEDGER_COLS)
    if stores:
        df = df[df["store_id"].isin(stores)]
    return df[[c for c in LEDGER_COLS if c in df.columns]]


def external_summary(wb: Workbench) -> dict:
    """외부 위험 지표 요약 (기업 실적 아님)."""
    ext = wb.ext
    u = ext.units
    out: dict = {"available": u is not None, "units": None, "lisa_hh": None, "diesel": None,
                 "audit_warnings": sum(1 for f in ext.findings if f.get("level") == "warn")}
    if u is None:
        return out
    out["units"] = int(len(u))
    out["lisa_hh"] = int((u["lisa_cluster"] == "High-High").sum())
    h = ext.fuel_history
    if h is not None and len(h):
        last = float(h["diesel_price"].iloc[-1])
        chg = (last / float(h["diesel_price"].iloc[-31]) - 1) * 100 if len(h) > 31 else None
        out["diesel"] = {"date": jsonable(h["date"].max()), "price": last, "change_30d_pct": jsonable(chg)}
    return out
