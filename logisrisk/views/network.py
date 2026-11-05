"""02 Network Intelligence 뷰 모델: 고속도로 영업소 위험(외부) · 가중치 재계산 · 노선 요약 · 센터 근접성."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..analytics import risk
from ..analytics.routing import haversine_km
from ..services import Workbench
from .serialize import jsonable, records

UNIT_COLS = ["unitCode", "unitName", "routeName", "lat", "lon", "score", "grade", "lisa_cluster", "local_p_value",
             "mean_freight_345_share", "mean_freight_345_traffic", "traffic_volatility", "abs_imbalance_ratio",
             "rank_base", "rank_sim", "rank_change"]


def components() -> list[dict]:
    return [{"key": k, "column": c, "label": lab, "default": risk.DEFAULT_WEIGHTS[k]}
            for k, (c, lab) in risk.VULN_COMPONENTS.items()]


def units_view(wb: Workbench, weights: dict[str, float] | None, routes: list[str] | None = None) -> dict:
    u = wb.ext.units
    if u is None:
        return {"available": False, "reason": "외부 영업소 데이터 파일이 없습니다: " + ", ".join(wb.ext.missing),
                "units": [], "routes": [], "scenario": None, "route_summary": [], "lisa_counts": {}}
    nw = risk.normalize_weights(weights) if weights else dict(risk.DEFAULT_WEIGHTS)
    is_base = all(abs(nw[k] - risk.DEFAULT_WEIGHTS[k]) < 1e-9 for k in nw)
    sim = risk.recompute_units(u, nw)
    params = {"weights": {k: round(v, 4) for k, v in nw.items()}, "method": "minmax-weighted-sum", "population": len(u)}
    sim = sim.assign(score=sim["sim_vulnerability"], grade=sim["sim_grade"], lat=sim["yValue"], lon=sim["xValue"])
    view = sim[sim["routeName"].isin(routes)] if routes else sim
    rs = risk.route_summary(view, "score").head(15)
    return {
        "available": True, "reason": None,
        "units": records(view.sort_values("score", ascending=False), UNIT_COLS),
        "routes": sorted(u["routeName"].dropna().unique().tolist()),
        "scenario": {"id": risk.scenario_id(params), "params": params, "is_base": is_base,
                     "rank_changed": int((sim["rank_change"] != 0).sum()),
                     "grade_changed": int((sim["sim_grade"] != u["vulnerability_grade"]).sum())},
        "route_summary": records(rs),
        "lisa_counts": {str(k): int(v) for k, v in view["lisa_cluster"].value_counts().items()},
    }


def proximity(wb: Workbench, weights: dict[str, float] | None, radius_km: float) -> list[dict]:
    """센터 반경 내 고위험 영업소 (직선거리 근접성 — 실제 이용 경로 아님)."""
    u, wh = wb.ext.units, wb.frames.get("warehouses")
    if u is None or wh is None:
        return []
    nw = risk.normalize_weights(weights) if weights else dict(risk.DEFAULT_WEIGHTS)
    sim = risk.recompute_units(u, nw)
    vh = sim[sim["sim_grade"] == "Very High"]
    out = []
    for w in wh.dropna(subset=["lat", "lon"]).itertuples():
        d = haversine_km(w.lat, w.lon, sim["yValue"].values, sim["xValue"].values)
        near = sim[d <= radius_km]
        dv = haversine_km(w.lat, w.lon, vh["yValue"].values, vh["xValue"].values) if len(vh) else np.array([])
        i = int(np.argmin(d))
        out.append(jsonable({"warehouse_id": w.warehouse_id, "name": w.name, "units_in_radius": len(near),
                             "very_high": int((dv <= radius_km).sum()),
                             "high_high": int((near["lisa_cluster"] == "High-High").sum()),
                             "mean_score": float(near["sim_vulnerability"].mean()) if len(near) else None,
                             "nearest_unit": sim.iloc[i]["unitName"], "nearest_km": float(d.min())}))
    return out


def risk_frame(wb: Workbench, weights: dict[str, float] | None, routes: list[str] | None) -> pd.DataFrame:
    v = units_view(wb, weights, routes)
    return pd.DataFrame(v["units"])
