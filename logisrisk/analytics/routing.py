"""배송 계획 대안 생성 (CVRP 휴리스틱) 과 현행 계획 비교.

- 알고리즘: Clarke-Wright Savings + 2-opt 개선, 이종 차량 배정 (중량·용적·운행시간 제약).
- 거리: 하버사인 직선거리 × 우회계수(road_factor). 실도로 경로 API 가 아니므로 '직선거리 근사'로 표기.
- 시간창(VRPTW)은 이 휴리스틱에서 강제하지 않는다 → 경고로 표기. (OR-Tools 연동은 P1)
- 결과는 '제안(proposed)' 이며 배차 확정은 별도 승인 절차를 거친다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

EARTH_R = 6371.0088


def available_mask(vehicles: pd.DataFrame) -> pd.Series:
    """가용여부 미입력은 가용으로 간주."""
    return vehicles["available"].map(lambda v: True if v is None or pd.isna(v) else bool(v)).astype(bool)


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def distance_matrix(lats, lons) -> np.ndarray:
    la, lo = np.asarray(lats, float), np.asarray(lons, float)
    return haversine_km(la[:, None], lo[:, None], la[None, :], lo[None, :])


@dataclass
class RoutingParams:
    road_factor: float = 1.0        # 1.0 = 직선거리. 실도로 보정은 사용자 가정값
    avg_speed_kmh: float = 40.0
    default_service_min: float = 15.0
    default_max_hours: float = 10.0
    diesel_price: float | None = None  # 원/L — 비용 추정에 필요
    use_volume: bool = True

    def to_dict(self):
        return asdict(self)


@dataclass
class PlanResult:
    routes: pd.DataFrame
    stops: pd.DataFrame
    unassigned: pd.DataFrame
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def _route_len(seq: list[int], D: np.ndarray) -> float:
    if not seq:
        return 0.0
    path = [0] + seq + [0]
    return float(sum(D[path[i], path[i + 1]] for i in range(len(path) - 1)))


def two_opt(seq: list[int], D: np.ndarray, max_iter: int = 200) -> list[int]:
    best = seq[:]
    if len(best) < 3:
        return best
    improved, it = True, 0
    while improved and it < max_iter:
        improved, it = False, it + 1
        path = [0] + best + [0]
        for i in range(1, len(path) - 2):
            for j in range(i + 1, len(path) - 1):
                a, b, c, d = path[i - 1], path[i], path[j], path[j + 1]
                if D[a, c] + D[b, d] < D[a, b] + D[c, d] - 1e-9:
                    path[i:j + 1] = path[i:j + 1][::-1]
                    best = path[1:-1]
                    improved = True
                    break
            if improved:
                break
    return best


def nearest_neighbor(nodes: list[int], D: np.ndarray) -> list[int]:
    rest, cur, out = set(nodes), 0, []
    while rest:
        nxt = min(rest, key=lambda j: D[cur, j])
        out.append(nxt)
        rest.remove(nxt)
        cur = nxt
    return out


def _savings(nodes: list[int], D: np.ndarray, kg: np.ndarray, m3: np.ndarray, svc_h: np.ndarray,
             cap_kg: float, cap_m3: float, max_h: float, speed: float, rf: float) -> list[list[int]]:
    routes = {i: [i] for i in nodes}
    where = {i: i for i in nodes}
    load = {i: (kg[i], m3[i]) for i in nodes}
    sv = []
    for a in range(len(nodes)):
        for b in range(a + 1, len(nodes)):
            i, j = nodes[a], nodes[b]
            sv.append((D[0, i] + D[0, j] - D[i, j], i, j))
    sv.sort(reverse=True)

    def dur(seq):
        return _route_len(seq, D) * rf / speed + float(svc_h[seq].sum())

    for s, i, j in sv:
        if s <= 0:
            break
        ri, rj = where[i], where[j]
        if ri == rj:
            continue
        A, B = routes[ri], routes[rj]
        if A[-1] == i and B[0] == j:
            new = A + B
        elif B[-1] == j and A[0] == i:
            new = B + A
        elif A[0] == i and B[0] == j:
            new = A[::-1] + B
        elif A[-1] == i and B[-1] == j:
            new = A + B[::-1]
        else:
            continue
        lk = load[ri][0] + load[rj][0]
        lm = load[ri][1] + load[rj][1]
        if lk > cap_kg + 1e-9 or (cap_m3 and lm > cap_m3 + 1e-9) or dur(new) > max_h + 1e-9:
            continue
        routes[ri] = new
        load[ri] = (lk, lm)
        del routes[rj], load[rj]
        for n in new:
            where[n] = ri
    return list(routes.values())


def plan_routes(depot: dict, stops: pd.DataFrame, vehicles: pd.DataFrame, params: RoutingParams) -> PlanResult:
    """depot: {id,name,lat,lon}; stops: stop_id,name,lat,lon,demand_kg,[demand_m3],[service_min],[tw_start,tw_end];
    vehicles: vehicle_id, capacity_kg, [capacity_m3], [max_hours], fuel_efficiency_km_per_l, [fixed_cost_per_day],
    [variable_cost_per_km]."""
    warnings, violations = [], []
    s = stops.copy().reset_index(drop=True)
    for c, dflt in (("demand_m3", np.nan), ("service_min", np.nan), ("tw_start", None), ("tw_end", None)):
        if c not in s:
            s[c] = dflt
    v = vehicles.copy().reset_index(drop=True)
    for c, dflt in (("capacity_m3", np.nan), ("max_hours", np.nan), ("fixed_cost_per_day", np.nan),
                    ("variable_cost_per_km", np.nan)):
        if c not in v:
            v[c] = dflt
    v["max_hours"] = v["max_hours"].fillna(params.default_max_hours)
    unassigned = []

    bad = s["lat"].isna() | s["lon"].isna()
    for r in s[bad].itertuples():
        unassigned.append({"stop_id": r.stop_id, "reason": "좌표 없음"})
    bad_d = s["demand_kg"].isna()
    for r in s[bad_d & ~bad].itertuples():
        unassigned.append({"stop_id": r.stop_id, "reason": "중량(수요) 계산 불가 — SKU 단위중량 누락"})
    s = s[~bad & ~bad_d].reset_index(drop=True)
    if v.empty:
        violations.append("가용 차량이 없습니다.")
        for r in s.itertuples():
            unassigned.append({"stop_id": r.stop_id, "reason": "가용 차량 없음"})
        return PlanResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(unassigned), violations, warnings, {})

    use_m3 = params.use_volume and s["demand_m3"].notna().all() and v["capacity_m3"].notna().all() and len(s) > 0
    if params.use_volume and not use_m3:
        warnings.append("용적 제약 미적용: 배송지 수요 용적 또는 차량 적재용적이 일부 누락되어 중량만 검토했습니다.")
    if s["tw_start"].notna().any() or s["tw_end"].notna().any():
        warnings.append("배송 시간창이 있으나 이 휴리스틱은 시간창을 강제하지 않습니다 (OR-Tools VRPTW 필요, P1).")
    if params.road_factor == 1.0:
        warnings.append("거리는 직선거리(하버사인) 근사입니다. 실제 도로 주행거리가 아닙니다.")

    max_kg = float(v["capacity_kg"].max())
    max_m3 = float(v["capacity_m3"].max()) if use_m3 else 0.0
    over = (s["demand_kg"] > max_kg) | ((s["demand_m3"] > max_m3) if use_m3 else False)
    for r in s[over].itertuples():
        unassigned.append({"stop_id": r.stop_id, "reason": f"단일 배송지 수요({r.demand_kg:,.0f}kg)가 최대 차량 용량 초과 — 분할 배송 필요"})
    s = s[~over].reset_index(drop=True)

    tot_kg, fleet_kg = float(s["demand_kg"].sum()), float(v["capacity_kg"].sum())
    if tot_kg > fleet_kg:
        violations.append(f"총 수요 {tot_kg:,.0f}kg 가 가용 차량 총 용량 {fleet_kg:,.0f}kg 를 초과 (1회전 기준).")

    lats = [depot["lat"]] + s["lat"].tolist()
    lons = [depot["lon"]] + s["lon"].tolist()
    D = distance_matrix(lats, lons)
    n = len(s)
    kg = np.r_[0, s["demand_kg"].to_numpy(float)]
    m3 = np.r_[0, s["demand_m3"].fillna(0).to_numpy(float)] if use_m3 else np.zeros(n + 1)
    svc = np.r_[0, s["service_min"].fillna(params.default_service_min).to_numpy(float) / 60]
    rf, sp = params.road_factor, params.avg_speed_kmh

    remaining = list(range(1, n + 1))
    free = v.sort_values("capacity_kg").copy()
    assigned: list[tuple[pd.Series, list[int]]] = []
    for _ in range(6):  # 남은 차량 용량에 맞춰 재분할 반복
        if not remaining or free.empty:
            break
        cap_kg = float(free["capacity_kg"].max())
        cap_m3 = float(free["capacity_m3"].max()) if use_m3 else 0.0
        mh = float(free["max_hours"].max())
        rts = _savings(remaining, D, kg, m3, svc, cap_kg, cap_m3, mh, sp, rf)
        rts = [two_opt(r, D) for r in rts]
        rts.sort(key=lambda r: -kg[r].sum())
        left = []
        for r in rts:
            lk, lm = kg[r].sum(), m3[r].sum()
            du = _route_len(r, D) * rf / sp + svc[r].sum()
            ok = free[(free["capacity_kg"] >= lk - 1e-9) & (free["max_hours"] >= du - 1e-9)]
            if use_m3:
                ok = ok[ok["capacity_m3"] >= lm - 1e-9]
            if ok.empty:
                left.extend(r)
                continue
            veh = ok.iloc[0]
            assigned.append((veh, r))
            free = free[free["vehicle_id"] != veh["vehicle_id"]]
        if len(left) == len(remaining):
            break
        remaining = left
    for i in remaining:
        unassigned.append({"stop_id": s.loc[i - 1, "stop_id"],
                           "reason": "가용 차량 부족 또는 운행시간 제약 초과 (1차량 1회전 가정)"})
    if remaining:
        violations.append(f"미배정 배송지 {len(remaining)}곳 — 차량 추가, 2회전 운행, 또는 납기 조정이 필요합니다.")

    rrows, srows = [], []
    for k, (veh, r) in enumerate(assigned, 1):
        dist = _route_len(r, D) * rf
        dur = dist / sp + svc[r].sum()
        fuel_l = dist / float(veh["fuel_efficiency_km_per_l"]) if veh.get("fuel_efficiency_km_per_l") else np.nan
        fuel_c = fuel_l * params.diesel_price if params.diesel_price else np.nan
        var_c = dist * veh["variable_cost_per_km"] if pd.notna(veh["variable_cost_per_km"]) else np.nan
        fix_c = veh["fixed_cost_per_day"] if pd.notna(veh["fixed_cost_per_day"]) else np.nan
        parts = [fuel_c, var_c, fix_c]
        rrows.append({"route": k, "vehicle_id": veh["vehicle_id"], "stops": len(r), "load_kg": float(kg[r].sum()),
                      "capacity_kg": float(veh["capacity_kg"]), "load_factor": float(kg[r].sum() / veh["capacity_kg"]),
                      "distance_km": dist, "duration_h": dur, "fuel_l": fuel_l, "fuel_cost": fuel_c,
                      "variable_cost": var_c, "fixed_cost": fix_c,
                      "est_cost": float(np.nansum(parts)) if any(pd.notna(p) for p in parts) else np.nan,
                      "cost_complete": all(pd.notna(p) for p in parts)})
        for seq, i in enumerate(r, 1):
            srows.append({"route": k, "vehicle_id": veh["vehicle_id"], "seq": seq, "stop_id": s.loc[i - 1, "stop_id"],
                          "name": s.loc[i - 1, "name"], "lat": s.loc[i - 1, "lat"], "lon": s.loc[i - 1, "lon"],
                          "demand_kg": float(kg[i])})
    routes = pd.DataFrame(rrows)
    summ = {"vehicles_used": len(routes), "stops_planned": int(routes["stops"].sum()) if len(routes) else 0,
            "stops_unassigned": len(unassigned),
            "distance_km": float(routes["distance_km"].sum()) if len(routes) else 0.0,
            "duration_h": float(routes["duration_h"].sum()) if len(routes) else 0.0,
            "est_cost": float(routes["est_cost"].sum()) if len(routes) and routes["est_cost"].notna().any() else None,
            "cost_complete": bool(len(routes) and routes["cost_complete"].all()),
            "avg_load_factor": float(routes["load_kg"].sum() / routes["capacity_kg"].sum()) if len(routes) else None,
            "method": "Clarke-Wright Savings + 2-opt (휴리스틱, 최적해 보장 없음)",
            "distance_basis": f"직선거리 × 우회계수 {rf}"}
    if not summ["cost_complete"] and len(routes):
        warnings.append("일부 차량의 비용 파라미터(경유가·변동비·고정비)가 없어 추정 비용이 불완전합니다.")
    return PlanResult(routes, pd.DataFrame(srows), pd.DataFrame(unassigned), violations, warnings, summ)


def baseline_plan(depot: dict, assignments: pd.DataFrame, vehicles: pd.DataFrame, params: RoutingParams) -> PlanResult:
    """현행 배차(배송 실적의 vehicle_id)를 동일한 거리 기준으로 재평가.
    assignments: vehicle_id, stop_id, name, lat, lon, demand_kg, [recorded_distance_km]."""
    rrows, warnings = [], []
    vv = vehicles.set_index("vehicle_id")
    a = assignments.copy()
    if "recorded_distance_km" not in a:
        a["recorded_distance_km"] = np.nan
    for vid, g in a.dropna(subset=["lat", "lon"]).groupby("vehicle_id"):
        g = g.groupby("stop_id", as_index=False).agg(lat=("lat", "first"), lon=("lon", "first"),
                                                     demand_kg=("demand_kg", lambda x: x.sum(min_count=1)),
                                                     rec=("recorded_distance_km", lambda x: x.sum(min_count=1)))
        D = distance_matrix([depot["lat"]] + g["lat"].tolist(), [depot["lon"]] + g["lon"].tolist())
        seq = two_opt(nearest_neighbor(list(range(1, len(g) + 1)), D), D)
        dist = _route_len(seq, D) * params.road_factor
        veh = vv.loc[vid] if vid in vv.index else None
        cap = float(veh["capacity_kg"]) if veh is not None else np.nan
        eff = float(veh["fuel_efficiency_km_per_l"]) if veh is not None else np.nan
        fuel_c = dist / eff * params.diesel_price if params.diesel_price and eff == eff else np.nan
        var_c = dist * veh["variable_cost_per_km"] if veh is not None and pd.notna(veh.get("variable_cost_per_km")) else np.nan
        fix_c = veh["fixed_cost_per_day"] if veh is not None and pd.notna(veh.get("fixed_cost_per_day")) else np.nan
        parts = [fuel_c, var_c, fix_c]
        load = float(g["demand_kg"].sum())
        rrows.append({"vehicle_id": vid, "stops": len(g), "load_kg": load, "capacity_kg": cap,
                      "load_factor": load / cap if cap == cap and cap else np.nan, "distance_km": dist,
                      "recorded_distance_km": float(g["rec"].sum()) if g["rec"].notna().any() else np.nan,
                      "duration_h": dist / params.avg_speed_kmh + len(g) * params.default_service_min / 60,
                      "est_cost": float(np.nansum(parts)) if any(pd.notna(p) for p in parts) else np.nan,
                      "cost_complete": all(pd.notna(p) for p in parts)})
    routes = pd.DataFrame(rrows)
    summ = {"vehicles_used": len(routes), "stops_planned": int(routes["stops"].sum()) if len(routes) else 0,
            "distance_km": float(routes["distance_km"].sum()) if len(routes) else 0.0,
            "recorded_distance_km": float(routes["recorded_distance_km"].sum()) if len(routes) and routes["recorded_distance_km"].notna().any() else None,
            "duration_h": float(routes["duration_h"].sum()) if len(routes) else 0.0,
            "est_cost": float(routes["est_cost"].sum()) if len(routes) and routes["est_cost"].notna().any() else None,
            "cost_complete": bool(len(routes) and routes["cost_complete"].all()),
            "avg_load_factor": float(routes["load_kg"].sum() / routes["capacity_kg"].sum()) if len(routes) and routes["capacity_kg"].notna().all() else None,
            "method": "현행 차량 배정 유지, 방문 순서는 최근접+2-opt 로 재구성(실제 순서 미보유)",
            "distance_basis": f"직선거리 × 우회계수 {params.road_factor}"}
    warnings.append("현행 계획의 실제 방문 순서 데이터가 없어 동일 기준(직선거리·최근접+2-opt)으로 재구성해 비교합니다.")
    return PlanResult(routes, pd.DataFrame(), pd.DataFrame(), [], warnings, summ)


def compare_plans(base: PlanResult, prop: PlanResult) -> pd.DataFrame:
    rows = []
    for key, lab, unit in (("vehicles_used", "투입 차량", "대"), ("stops_planned", "배정 배송지", "곳"),
                           ("distance_km", "총 거리(직선 근사)", "km"), ("duration_h", "총 운행시간(추정)", "시간"),
                           ("est_cost", "추정 비용", "원"), ("avg_load_factor", "평균 적재율", "%")):
        b, p = base.summary.get(key), prop.summary.get(key)
        diff = (p - b) if (b is not None and p is not None) else None
        pct = (diff / b * 100) if (diff is not None and b) else None
        rows.append({"지표": lab, "단위": unit, "현행(재구성)": b, "제안": p, "차이": diff, "차이(%)": pct})
    return pd.DataFrame(rows)


def build_day_inputs(frames: dict, fact: pd.DataFrame, day, warehouse_id: str, source: str = "orders"):
    """특정 일자·센터의 배송지 수요와 현행 배정을 구성.
    source='orders': 해당일 납기(요청일 또는 주문일) 주문 / 'shipments': 해당일 출고 실적."""
    wh = frames["warehouses"].set_index("warehouse_id").loc[warehouse_id]
    depot = {"id": warehouse_id, "name": wh["name"], "lat": float(wh["lat"]), "lon": float(wh["lon"])}
    st = frames["stores"]
    day = pd.Timestamp(day)
    x = fact[(fact["ship_date"] == day) & (fact["warehouse_id"] == warehouse_id)]
    stops = (x.groupby("store_id").agg(demand_kg=("load_kg_eff", lambda s: s.sum(min_count=len(s))),
                                       demand_m3=("order_volume_m3", lambda s: s.sum(min_count=len(s))))
             .reset_index().merge(st[["store_id", "name", "lat", "lon"] + (["service_min", "tw_start", "tw_end"]
                                  if "service_min" in st else [])], on="store_id", how="left")
             .rename(columns={"store_id": "stop_id"}))
    assign = x[["vehicle_id", "store_id", "store_name", "lat", "lon", "load_kg_eff", "distance_km"]].rename(
        columns={"store_id": "stop_id", "store_name": "name", "load_kg_eff": "demand_kg",
                 "distance_km": "recorded_distance_km"})
    v = frames["vehicles"]
    v = v[v["home_warehouse_id"] == warehouse_id]
    if "available" in v:
        v = v[available_mask(v)]
    return depot, stops, assign.dropna(subset=["vehicle_id"]), v
