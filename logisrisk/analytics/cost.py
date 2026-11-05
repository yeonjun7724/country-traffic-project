"""운송비 · 유류비 · 시나리오 계산 (업로드된 기업 배송 데이터 기반).

결과 수치의 성격
- baseline: 업로드된 실적(관측). 연료량/단가가 없으면 추정치로 보완하고 출처 컬럼에 표시.
- scenario: '단순 가정 기반 추정' — 선형 비례·운행 단위 용량 가정. 최적화 결과 아님.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .kpi import Filters, apply_filters
from .routing import available_mask, haversine_km


def fuel_basis(fact: pd.DataFrame, fuel_prices: pd.DataFrame | None = None,
               external_diesel: pd.DataFrame | None = None) -> pd.DataFrame:
    """배송별 연료량·기준 경유가와 그 출처를 붙인다."""
    x = fact.copy()
    est_l = x["distance_km"] / x["fuel_efficiency_km_per_l"]
    x["fuel_l_eff"] = x["fuel_l"].where(x["fuel_l"].notna(), est_l)
    x["fuel_l_source"] = np.select([x["fuel_l"].notna(), est_l.notna()],
                                   ["실측 연료량", "추정(거리÷연비)"], "없음")
    implied = (x["fuel_cost"] / x["fuel_l"]).where((x["fuel_l"] > 0) & x["fuel_cost"].notna())
    x["price_base"] = implied
    x["price_source"] = np.where(implied.notna(), "실제 연료비÷연료량", "없음")
    if fuel_prices is not None and len(fuel_prices):
        fp = fuel_prices.sort_values("date")
        allr = fp[fp["region"].fillna("ALL") == "ALL"][["date", "diesel_price"]]
        if allr.empty:
            allr = fp.groupby("date", as_index=False)["diesel_price"].mean()
        need = x["price_base"].isna() & x["ship_date"].notna()
        if need.any():
            look = pd.merge_asof(x.loc[need, ["ship_date"]].reset_index().sort_values("ship_date"),
                                 allr.rename(columns={"date": "ship_date"}), on="ship_date", direction="backward")
            look = look.set_index("index")["diesel_price"]
            x.loc[look.index, "price_base"] = look
            x.loc[look.dropna().index, "price_source"] = "기업 유가 테이블"
    if external_diesel is not None and len(external_diesel):
        need = x["price_base"].isna() & x["ship_date"].notna()
        if need.any():
            ed = external_diesel[["date", "diesel_price"]].sort_values("date").rename(columns={"date": "ship_date"})
            look = pd.merge_asof(x.loc[need, ["ship_date"]].reset_index().sort_values("ship_date"), ed,
                                 on="ship_date", direction="backward", tolerance=pd.Timedelta(days=7))
            look = look.set_index("index")["diesel_price"]
            x.loc[look.index, "price_base"] = look
            x.loc[look.dropna().index, "price_source"] = "외부 전국평균 경유가(참고)"
    x["fuel_cost_eff"] = x["fuel_cost"].where(x["fuel_cost"].notna(), x["fuel_l_eff"] * x["price_base"])
    x["fuel_cost_source"] = np.where(x["fuel_cost"].notna(), "실제 연료비",
                                     np.where(x["fuel_cost_eff"].notna(), "추정(연료량×경유가)", "없음"))
    x["nonfuel_cost"] = (x["cost"] - x["fuel_cost"]).where(x["fuel_cost"].notna() & x["cost"].notna(),
                                                           x["cost"] - x["fuel_cost_eff"])
    x.loc[x["nonfuel_cost"] < 0, "nonfuel_cost"] = np.nan  # 비용 입력 불일치 → 분해 불가
    return x


def diesel_sensitivity(fact: pd.DataFrame, flt: Filters, pcts: list[float], fuel_prices=None,
                       external_diesel=None, by: str | None = None) -> dict:
    """경유가 ±p% 시 연료비 변화 (연료량 불변 가정)."""
    x = fuel_basis(apply_filters(fact, flt), fuel_prices, external_diesel)
    ok = x[x["fuel_l_eff"].notna() & x["price_base"].notna()]
    res = {"n_total": len(x), "n_computable": len(ok),
           "coverage": (len(ok) / len(x)) if len(x) else 0.0,
           "fuel_l_sources": ok["fuel_l_source"].value_counts().to_dict(),
           "price_sources": ok["price_source"].value_counts().to_dict(),
           "base_fuel_cost": float((ok["fuel_l_eff"] * ok["price_base"]).sum()),
           "base_total_cost": float(x["cost"].sum(min_count=1)) if x["cost"].notna().any() else None,
           "rows": []}
    for p in pcts:
        d = float((ok["fuel_l_eff"] * ok["price_base"] * p / 100).sum())
        res["rows"].append({"diesel_pct": p, "fuel_cost_delta": d,
                            "total_cost_delta_pct": (d / res["base_total_cost"] * 100) if res["base_total_cost"] else None})
    if by and by in ok.columns:
        g = ok.assign(base=ok["fuel_l_eff"] * ok["price_base"]).groupby(by, dropna=False).agg(
            shipments=("shipment_id", "count"), fuel_l=("fuel_l_eff", "sum"), base_fuel_cost=("base", "sum"),
            total_cost=("cost", lambda s: s.sum(min_count=1)))
        for p in pcts:
            g[f"delta_{p:+g}%"] = g["base_fuel_cost"] * p / 100
        res["by"] = g.reset_index().sort_values("base_fuel_cost", ascending=False)
    res["assumptions"] = [
        "연료 사용량은 경유가 변화와 무관하게 동일하다고 가정(단기 탄력성 0).",
        "연료량 미입력 건은 운행거리÷차량 연비로 추정.",
        "기준 경유가는 실제 연료비÷연료량 → 기업 유가 테이블 → 외부 전국평균(참고) 순으로 적용.",
        "유가 연동 할증(유류할증료) 계약 구조는 반영하지 않음.",
    ]
    return res


@dataclass
class ScenarioParams:
    name: str = "Scenario"
    diesel_pct: float = 0.0          # 경유가 변화율 %
    demand_pct: float = 0.0          # 물동량 변화율 %
    rate_pct: float = 0.0            # 연료 외 운송 단가 변화율 %
    fleet_change: int = 0            # 가용 차량 증감 대수
    trips_per_vehicle_day: int = 1   # 차량 1대 1일 운행 횟수 가정

    def to_dict(self):
        return asdict(self)


def scenario_engine(fact: pd.DataFrame, flt: Filters, params: ScenarioParams, vehicles: pd.DataFrame | None,
                    fuel_prices=None, external_diesel=None) -> dict:
    """Baseline 대비 시나리오 비용·운행·차량 영향 (단순 가정 기반 추정)."""
    x = fuel_basis(apply_filters(fact, flt), fuel_prices, external_diesel)
    x = x[x["cost"].notna()].copy()
    if x.empty:
        return {"status": "not_computable", "reason": "운송비가 입력된 배송이 없습니다."}
    x["fuel_c"] = x["fuel_cost_eff"].fillna(0.0)
    x["nonfuel_c"] = x["nonfuel_cost"].where(x["nonfuel_cost"].notna(), x["cost"] - x["fuel_c"]).clip(lower=0)
    has_trip = x["vehicle_id"].notna()
    x["trip_key"] = np.where(has_trip, x["vehicle_id"].astype(str) + "|" + x["ship_date"].astype(str),
                             "S|" + x["shipment_id"].astype(str))
    trips = x.groupby("trip_key").agg(date=("ship_date", "first"), vehicle=("vehicle_id", "first"),
                                      load=("load_kg_eff", lambda s: s.sum(min_count=1)),
                                      cap=("capacity_kg", "first"),
                                      dist=("distance_km", lambda s: s.sum(min_count=1)),
                                      fuel=("fuel_c", "sum"), nonfuel=("nonfuel_c", "sum"))
    d = params.demand_pct / 100
    cap_known = trips["load"].notna() & trips["cap"].notna() & (trips["cap"] > 0)
    k = pd.Series(1.0 + d, index=trips.index)  # 용량 정보 없으면 선형 비례
    k[cap_known] = np.maximum(1, np.ceil(trips.loc[cap_known, "load"] * (1 + d) / trips.loc[cap_known, "cap"] - 1e-9))
    # 원래도 용량 초과 운행이었으면 기존 운행 수를 1로 유지
    k[cap_known & (trips["load"] > trips["cap"])] = np.maximum(1.0, 1 + d)
    if d < 0:
        k[cap_known] = 1.0  # 수요 감소 시 운행 수 유지, 변동 연료만 감소한다고 보지 않음 (보수적)

    def total(diesel: float, rate: float, kk: pd.Series) -> dict:
        fuel = float((trips["fuel"] * (1 + diesel) * kk).sum())
        nonfuel = float((trips["nonfuel"] * (1 + rate) * kk).sum())
        return {"fuel": fuel, "nonfuel": nonfuel, "total": fuel + nonfuel}

    base = total(0, 0, pd.Series(1.0, index=trips.index))
    scen = total(params.diesel_pct / 100, params.rate_pct / 100, k)
    # 원인 기여도 (one-at-a-time + 상호작용 잔차)
    only_d = total(params.diesel_pct / 100, 0, pd.Series(1.0, index=trips.index))["total"] - base["total"]
    only_r = total(0, params.rate_pct / 100, pd.Series(1.0, index=trips.index))["total"] - base["total"]
    only_q = total(0, 0, k)["total"] - base["total"]
    delta = scen["total"] - base["total"]
    contrib = {"경유가": only_d, "운송 단가": only_r, "물동량(운행 증가)": only_q,
               "상호작용": delta - only_d - only_r - only_q}

    # 차량 수 검토: 일자별 필요 운행 / (가용 차량 × 1일 운행 횟수)
    fleet = None
    if vehicles is not None and len(vehicles):
        av = vehicles if "available" not in vehicles else vehicles[available_mask(vehicles)]
        if flt.warehouses:
            av = av[av["home_warehouse_id"].isin(flt.warehouses)]
        fleet = max(0, len(av) + params.fleet_change)
    day_need_base = trips.groupby("date").size()
    day_need = (k.groupby(trips["date"]).sum()).apply(math.ceil)
    short_days = None
    if fleet is not None:
        capday = fleet * max(1, params.trips_per_vehicle_day)
        short_days = int((day_need > capday).sum())
    dist_known = trips["dist"].notna()
    res = {
        "status": "ok", "params": params.to_dict(), "kind": "assumption",
        "n_shipments": len(x), "n_trips": len(trips),
        "baseline": {**base, "trips": float(len(trips)), "distance_km": float(trips.loc[dist_known, "dist"].sum()),
                     "peak_daily_trips": int(day_need_base.max()), "fleet": None if fleet is None else fleet - params.fleet_change},
        "scenario": {**scen, "trips": float(k.sum()), "distance_km": float((trips.loc[dist_known, "dist"] * k[dist_known]).sum()),
                     "peak_daily_trips": int(day_need.max()), "fleet": fleet, "days_fleet_short": short_days},
        "delta_total": delta, "delta_pct": delta / base["total"] * 100 if base["total"] else None,
        "contribution": contrib,
        "data_quality": {
            "fuel_cost_sources": x["fuel_cost_source"].value_counts().to_dict(),
            "trips_with_capacity": int(cap_known.sum()), "trips_total": len(trips),
            "shipments_without_vehicle": int((~has_trip).sum())},
        "assumptions": [
            "결과는 업로드된 실적을 기준으로 한 단순 가정 기반 추정이며 최적화 결과가 아님.",
            "연료비는 경유가에 선형 비례, 연료 외 비용(인건·고정·통행 등)은 운송 단가 변화율에 선형 비례.",
            "물동량 증가 시 기존 운행(차량×출고일)의 적재량이 같은 비율로 늘며, 용량 초과분은 동일 비용의 추가 운행으로 처리.",
            "용량 정보가 없는 운행은 물동량에 선형 비례하여 비용이 증가한다고 가정.",
            "수요 감소 시 운행 수는 줄이지 않음(보수적).",
            f"차량 부족 판정: 일자별 필요 운행 > 가용 차량 × {params.trips_per_vehicle_day}회.",
        ],
    }
    return res


def sensitivity(fact, flt, vehicles, fuel_prices=None, external_diesel=None, steps=(-20, -10, 10, 20)) -> pd.DataFrame:
    """요인별 단일 변화의 총비용 영향 (토네이도 차트용)."""
    rows = []
    for factor, key in (("경유가", "diesel_pct"), ("운송 단가", "rate_pct"), ("물동량", "demand_pct")):
        for s in steps:
            p = ScenarioParams(**{key: float(s)})
            r = scenario_engine(fact, flt, p, vehicles, fuel_prices, external_diesel)
            if r.get("status") == "ok":
                rows.append({"factor": factor, "change_pct": s, "delta_total": r["delta_total"], "delta_pct": r["delta_pct"]})
    return pd.DataFrame(rows)


def warehouse_outage(frames: dict[str, pd.DataFrame], warehouse_id: str, fact: pd.DataFrame | None = None,
                     flt: Filters | None = None) -> dict:
    """센터 중단 시 배송지별 대체 센터(직선거리 최근접)와 처리용량 검토."""
    wh, st, od = frames.get("warehouses"), frames.get("stores"), frames.get("orders")
    if wh is None or st is None or od is None:
        return {"status": "not_computable", "reason": "센터·배송지·주문 데이터가 모두 필요합니다."}
    if warehouse_id not in set(wh["warehouse_id"]):
        return {"status": "not_computable", "reason": f"센터 {warehouse_id} 없음"}
    alt = wh[wh["warehouse_id"] != warehouse_id]
    if alt.empty:
        return {"status": "infeasible", "reason": "대체 가능한 다른 센터가 없습니다."}
    o = od if flt is None else od[(od["order_date"] >= pd.Timestamp(flt.start)) & (od["order_date"] <= pd.Timestamp(flt.end))] \
        if (flt and flt.start) else od
    served = o[o["warehouse_id"] == warehouse_id]
    stores = st[st["store_id"].isin(served["store_id"])]
    src = wh.set_index("warehouse_id").loc[warehouse_id]
    rows = []
    for s in stores.itertuples():
        d_alt = haversine_km(s.lat, s.lon, alt["lat"].values, alt["lon"].values)
        i = int(np.argmin(d_alt))
        rows.append({"store_id": s.store_id, "store_name": s.name, "region": s.region,
                     "orders": int((served["store_id"] == s.store_id).sum()),
                     "dist_from_closed_km": float(haversine_km(src["lat"], src["lon"], s.lat, s.lon)),
                     "alt_warehouse_id": alt.iloc[i]["warehouse_id"], "alt_warehouse": alt.iloc[i]["name"],
                     "dist_from_alt_km": float(d_alt[i])})
    t = pd.DataFrame(rows)
    if t.empty:
        return {"status": "ok", "stores": t, "capacity": pd.DataFrame(), "assumptions": []}
    t["dist_change_km"] = t["dist_from_alt_km"] - t["dist_from_closed_km"]
    days = max(1, o["order_date"].dt.normalize().nunique())
    cap = []
    for wid, g in t.groupby("alt_warehouse_id"):
        cur = int((o["warehouse_id"] == wid).sum()) / days
        add = int(g["orders"].sum()) / days
        c = wh.set_index("warehouse_id").loc[wid, "daily_capacity_orders"] if "daily_capacity_orders" in wh else np.nan
        cap.append({"warehouse_id": wid, "current_orders_per_day": cur, "added_orders_per_day": add,
                    "daily_capacity_orders": c,
                    "utilization_after": (cur + add) / c if c and not pd.isna(c) and c > 0 else np.nan})
    return {"status": "ok", "stores": t.sort_values("dist_change_km", ascending=False), "capacity": pd.DataFrame(cap),
            "assumptions": ["대체 센터는 직선거리(하버사인) 최근접 기준. 실제 도로거리·재고 보유 여부·운송 계약은 반영하지 않음.",
                            "처리용량은 센터 테이블의 일 처리용량(주문/일) 입력값이 있을 때만 검토."]}
