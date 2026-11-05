"""물류 운영 KPI (업로드된 기업 데이터 전용).

모든 KPI 는 Metric 으로 정의·산식·분자·분모·기간·표본수를 함께 반환하며,
필요 데이터가 없으면 값을 추정하지 않고 '계산 불가' 로 반환한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from ..provenance import Metric, not_computable, safe_div


@dataclass
class Filters:
    start: date | None = None
    end: date | None = None
    warehouses: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    carriers: list[str] = field(default_factory=list)
    vehicles: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    stores: list[str] = field(default_factory=list)

    @property
    def days(self) -> int | None:
        if not self.start or not self.end:
            return None
        return (pd.Timestamp(self.end) - pd.Timestamp(self.start)).days + 1

    def shifted(self) -> "Filters":
        """동일 길이의 직전 기간."""
        if not self.start or not self.end:
            return Filters(**{**self.__dict__, "start": None, "end": None})
        span = (pd.Timestamp(self.end) - pd.Timestamp(self.start)).days + 1
        s = (pd.Timestamp(self.start) - pd.Timedelta(days=span)).date()
        e = (pd.Timestamp(self.start) - pd.Timedelta(days=1)).date()
        return Filters(**{**self.__dict__, "start": s, "end": e})

    def describe(self) -> str:
        parts = [f"기간 {self.start}~{self.end}" if self.start else "전체 기간"]
        for k, lab in (("warehouses", "센터"), ("regions", "권역"), ("carriers", "운송사"), ("vehicles", "차량"),
                       ("categories", "상품군"), ("stores", "배송지")):
            v = getattr(self, k)
            if v:
                parts.append(f"{lab}={','.join(map(str, v[:5]))}{'…' if len(v) > 5 else ''}")
        return " · ".join(parts)


def _order_attrs(frames: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    """주문별 주문수량·중량·상품군."""
    ol = frames.get("order_lines")
    if ol is None:
        return None
    sk = frames.get("skus")
    x = ol.copy()
    if sk is not None:
        x = x.merge(sk[["sku_id", "category", "unit_weight_kg", "unit_volume_m3"]], on="sku_id", how="left")
    else:
        x["category"], x["unit_weight_kg"], x["unit_volume_m3"] = None, np.nan, np.nan
    x["w"] = x["qty"] * x["unit_weight_kg"]
    x["v"] = x["qty"] * x["unit_volume_m3"]
    x["w_na"], x["v_na"] = x["w"].isna(), x["v"].isna()
    # 벡터화 집계 (주문 수십만 건에서도 수 초 이내). 한 줄이라도 중량/부피 미상이면 주문 전체를 미상(NaN) 처리
    g = x.groupby("order_id").agg(ordered_qty=("qty", "sum"), w=("w", "sum"), w_na=("w_na", "any"),
                                  v=("v", "sum"), v_na=("v_na", "any"))
    g["order_weight_kg"] = g["w"].where(~g["w_na"])
    g["order_volume_m3"] = g["v"].where(~g["v_na"])
    cats = (x[["order_id", "category"]].dropna().astype({"category": str}).drop_duplicates()
            .sort_values(["order_id", "category"]).groupby("order_id")["category"].agg("|".join))
    g["categories"] = cats.reindex(g.index).fillna("")
    return g[["ordered_qty", "order_weight_kg", "order_volume_m3", "categories"]].reset_index()


def build_fact(frames: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    """배송 1건 = 1행 인 분석용 팩트 테이블."""
    sh = frames.get("shipments")
    if sh is None or sh.empty:
        return None
    f = sh.copy()
    for c in ("ship_date", "planned_delivery_date", "actual_delivery_date"):
        f[c] = pd.to_datetime(f[c], errors="coerce")
    o = frames.get("orders")
    if o is not None:
        f = f.merge(o[["order_id", "order_date", "store_id", "warehouse_id", "requested_date"]], on="order_id", how="left")
    else:
        for c in ("order_date", "store_id", "warehouse_id", "requested_date"):
            f[c] = np.nan
    st = frames.get("stores")
    if st is not None:
        f = f.merge(st[["store_id", "name", "region", "customer_group", "lat", "lon"]]
                    .rename(columns={"name": "store_name"}), on="store_id", how="left")
    else:
        f["store_name"], f["region"], f["customer_group"], f["lat"], f["lon"] = None, None, None, np.nan, np.nan
    vh = frames.get("vehicles")
    if vh is not None:
        f = f.merge(vh[["vehicle_id", "carrier", "vehicle_type", "capacity_kg", "fuel_efficiency_km_per_l"]]
                    .rename(columns={"carrier": "vehicle_carrier"}), on="vehicle_id", how="left")
        f["carrier"] = f["carrier"].fillna(f["vehicle_carrier"])
        f = f.drop(columns=["vehicle_carrier"])
    else:
        f["vehicle_type"], f["capacity_kg"], f["fuel_efficiency_km_per_l"] = None, np.nan, np.nan
    oa = _order_attrs(frames)
    if oa is not None:
        f = f.merge(oa, on="order_id", how="left")
    else:
        f["ordered_qty"], f["order_weight_kg"], f["order_volume_m3"], f["categories"] = np.nan, np.nan, np.nan, ""

    # 비용: total_cost 우선, 없으면 구성요소 합 (구성요소 전부 결측이면 NaN)
    comp = f[["fuel_cost", "toll_cost", "other_cost"]]
    comp_sum = comp.sum(axis=1, min_count=1)
    f["cost"] = f["total_cost"].where(f["total_cost"].notna(), comp_sum)
    f["cost_source"] = np.where(f["total_cost"].notna(), "총 운송비 입력값",
                                np.where(comp_sum.notna(), "구성요소 합(연료+통행+기타)", "없음"))
    f["load_kg_eff"] = f["load_kg"].where(f["load_kg"].notna(), f["order_weight_kg"])
    has_dates = f["actual_delivery_date"].notna() & f["planned_delivery_date"].notna()
    f["on_time"] = np.where(has_dates, f["actual_delivery_date"] <= f["planned_delivery_date"], np.nan)
    f["delay_days"] = np.where(has_dates, (f["actual_delivery_date"] - f["planned_delivery_date"]).dt.days, np.nan)
    # 완납(In-Full)은 주문 단위: 분할배송이면 같은 주문의 모든 배송 수량을 합산해 주문수량과 비교
    grp = f.groupby("order_id")
    dq = grp["delivered_qty"].transform("sum").where(~f["delivered_qty"].isna().groupby(f["order_id"]).transform("any"))
    f["order_delivered_qty"] = dq
    has_qty = dq.notna() & f["ordered_qty"].notna()
    f["in_full"] = np.where(has_qty, dq >= f["ordered_qty"] - 1e-9, np.nan)
    return f


def apply_filters(fact: pd.DataFrame, flt: Filters, date_col: str = "ship_date") -> pd.DataFrame:
    x = fact
    if flt.start:
        x = x[x[date_col] >= pd.Timestamp(flt.start)]
    if flt.end:
        x = x[x[date_col] <= pd.Timestamp(flt.end)]
    for col, vals in (("warehouse_id", flt.warehouses), ("region", flt.regions), ("carrier", flt.carriers),
                      ("vehicle_id", flt.vehicles), ("store_id", flt.stores)):
        if vals and col in x.columns:
            x = x[x[col].isin(vals)]
    if flt.categories and "categories" in x.columns:
        pat = x["categories"].fillna("").str.split("|")
        x = x[pat.apply(lambda cs: bool(set(cs) & set(flt.categories)))]
    return x


def _filter_orders(frames: dict[str, pd.DataFrame], flt: Filters, fact: pd.DataFrame | None = None) -> pd.DataFrame | None:
    o = frames.get("orders")
    if o is None:
        return None
    x = o
    # 운송사·차량은 주문 속성이 아니므로 해당 운송사/차량으로 배송된 주문만 남긴다
    if (flt.carriers or flt.vehicles) and fact is not None:
        sel = fact
        if flt.carriers:
            sel = sel[sel["carrier"].isin(flt.carriers)]
        if flt.vehicles:
            sel = sel[sel["vehicle_id"].isin(flt.vehicles)]
        x = x[x["order_id"].isin(sel["order_id"])]
    if flt.start:
        x = x[x["order_date"] >= pd.Timestamp(flt.start)]
    if flt.end:
        x = x[x["order_date"] <= pd.Timestamp(flt.end)]
    if flt.warehouses:
        x = x[x["warehouse_id"].isin(flt.warehouses)]
    if flt.stores:
        x = x[x["store_id"].isin(flt.stores)]
    if flt.regions and frames.get("stores") is not None:
        ids = frames["stores"].loc[frames["stores"]["region"].isin(flt.regions), "store_id"]
        x = x[x["store_id"].isin(ids)]
    if flt.categories:
        oa = _order_attrs(frames)
        if oa is not None:
            ok = oa[oa["categories"].fillna("").str.split("|").apply(lambda cs: bool(set(cs) & set(flt.categories)))]
            x = x[x["order_id"].isin(ok["order_id"])]
    return x


def _period(flt: Filters) -> str:
    return f"{flt.start}~{flt.end}" if flt.start else "전체 기간"


def compute(frames: dict[str, pd.DataFrame], fact: pd.DataFrame | None, flt: Filters) -> dict[str, Metric]:
    """단일 기간 KPI 계산."""
    per = _period(flt)
    m: dict[str, Metric] = {}

    orders = _filter_orders(frames, flt, fact)
    if orders is None:
        m["orders"] = not_computable("orders", "주문 수", "주문(orders) 데이터 없음")
    else:
        m["orders"] = Metric("orders", "주문 수", float(orders["order_id"].nunique()), "건",
                             "기간 내 주문일 기준 고유 주문번호 수 (운송사·차량 필터 시 해당 배송이 있는 주문만)",
                             "COUNT(DISTINCT order_id)", n=len(orders), period=per,
                             warnings=["취소 주문 포함"] if "status" in orders and (orders["status"] == "cancelled").any() else [])

    if fact is None:
        reason = "배송(shipments) 데이터 없음"
        for k, lab in (("shipments", "배송 건수"), ("volume_kg", "총 물동량"), ("cost", "총 운송비"),
                       ("late_rate", "배송 지연율"), ("otif", "OTIF"), ("load_factor", "적재율"),
                       ("cost_per_km", "km당 운송비"), ("cost_per_order", "주문당 운송비")):
            m[k] = not_computable(k, lab, reason, period=per)
        return m

    x = apply_filters(fact, flt)
    m["shipments"] = Metric("shipments", "배송 건수", float(len(x)), "건", "기간 내 출고일 기준 배송(운송장) 수",
                            "COUNT(shipment_id)", n=len(x), period=per)

    w = x["order_weight_kg"]
    if len(x) and w.notna().all():
        m["volume_kg"] = Metric("volume_kg", "총 물동량", float(w.sum()), "kg",
                                "출고된 주문의 주문수량 × SKU 단위중량 합계", "Σ(qty × unit_weight_kg)", n=len(x), period=per)
    else:
        miss = int(w.isna().sum())
        m["volume_kg"] = not_computable("volume_kg", "총 물동량",
                                        f"주문상세·SKU 단위중량 누락 {miss}건" if len(x) else "대상 배송 없음", period=per)

    c = x["cost"]
    if len(x) and c.notna().any():
        warn = [f"비용 미입력 배송 {int(c.isna().sum())}건 제외"] if c.isna().any() else []
        m["cost"] = Metric("cost", "총 운송비", float(c.sum()), "원",
                           "배송별 총 운송비 합계 (총 운송비 미입력 시 연료비+통행료+기타 합)", "Σ cost",
                           n=int(c.notna().sum()), period=per, higher_is_better=False, warnings=warn)
    else:
        m["cost"] = not_computable("cost", "총 운송비", "운송비 입력값 없음", period=per)

    d = x["on_time"].dropna()
    if len(d):
        late = float((d == 0).sum())
        m["late_rate"] = Metric("late_rate", "배송 지연율", late / len(d), "%",
                                "실제 배송일 > 약속 배송일 인 배송 비율", "지연 건 / 배송완료(일자 보유) 건",
                                numerator=late, denominator=float(len(d)), n=len(d), period=per,
                                higher_is_better=False)
    else:
        m["late_rate"] = not_computable("late_rate", "배송 지연율", "실제 배송일 데이터 없음", period=per)

    # OTIF 는 주문 단위: 주문의 (기간 내) 모든 배송이 정시 AND 주문 전체 배송수량 ≥ 주문수량
    og = x.assign(_known=x["on_time"].notna(), _ok=x["on_time"] == 1).groupby("order_id").agg(
        ot_known=("_known", "all"), ot=("_ok", "all"), inf=("in_full", "first"))
    judg = og[og["ot_known"] & og["inf"].notna()]
    n_orders = len(og)
    if len(judg):
        ok = float((judg["ot"] & (judg["inf"] == 1)).sum())
        warn = [f"판정 불가(배송일 또는 수량 결측) 주문 {n_orders - len(judg)}건 제외"] if n_orders > len(judg) else []
        if x.duplicated("order_id").any():
            warn.append("분할배송 주문은 배송수량을 합산해 완납 여부를 판정")
        m["otif"] = Metric("otif", "OTIF", ok / len(judg), "%",
                           "주문 단위: 해당 주문의 모든 배송이 약속일 이내 AND 배송수량 합계가 주문수량 이상인 비율",
                           "(정시 ∧ 완납) 주문 / 판정 가능 주문", numerator=ok, denominator=float(len(judg)),
                           n=len(judg), period=per, warnings=warn)
    else:
        m["otif"] = not_computable("otif", "OTIF", "실제 배송일·배송수량·주문수량 중 결측", period=per)

    t = x[x["vehicle_id"].notna() & x["capacity_kg"].notna() & x["load_kg_eff"].notna()]
    if len(t):
        trips = t.groupby(["vehicle_id", "ship_date"]).agg(load=("load_kg_eff", "sum"), cap=("capacity_kg", "first"))
        lf = safe_div(float(trips["load"].sum()), float(trips["cap"].sum()))
        warn = []
        over = int((trips["load"] > trips["cap"] * 1.0001).sum())
        if over:
            warn.append(f"차량·일 단위 적재 합이 용량을 초과한 경우 {over}건 — 1일 다회전 운행이거나 적재중량 입력 오류일 수 있음")
        if x["load_kg"].isna().any():
            warn.append("적재중량 미입력 건은 주문중량(수량×단위중량)으로 대체")
        m["load_factor"] = Metric("load_factor", "적재율(중량)", lf, "%",
                                  "운행(차량×출고일)별 적재중량 합 / 차량 적재용량 합", "Σ load_kg / Σ capacity_kg",
                                  numerator=float(trips["load"].sum()), denominator=float(trips["cap"].sum()),
                                  n=len(trips), period=per, warnings=warn)
    else:
        m["load_factor"] = not_computable("load_factor", "적재율(중량)", "차량 배정·용량·적재중량 데이터 부족", period=per)

    k = x[x["cost"].notna() & x["distance_km"].notna() & (x["distance_km"] > 0)]
    if len(k):
        v = safe_div(float(k["cost"].sum()), float(k["distance_km"].sum()))
        m["cost_per_km"] = Metric("cost_per_km", "km당 운송비", v, "원/km", "운송비 합 / 운행거리 합 (거리 입력 건만)",
                                  "Σ cost / Σ distance_km", numerator=float(k["cost"].sum()),
                                  denominator=float(k["distance_km"].sum()), n=len(k), period=per, higher_is_better=False)
    else:
        m["cost_per_km"] = not_computable("cost_per_km", "km당 운송비", "운행거리(distance_km) 또는 비용 없음", period=per)

    co = x[x["cost"].notna()]
    if len(co):
        n_ord = co["order_id"].nunique()
        m["cost_per_order"] = Metric("cost_per_order", "주문당 운송비", safe_div(float(co["cost"].sum()), n_ord), "원",
                                     "운송비 합 / 배송된 고유 주문 수", "Σ cost / COUNT(DISTINCT order_id)",
                                     numerator=float(co["cost"].sum()), denominator=float(n_ord), n=n_ord, period=per,
                                     higher_is_better=False)
    else:
        m["cost_per_order"] = not_computable("cost_per_order", "주문당 운송비", "운송비 입력값 없음", period=per)
    return m


def compute_with_comparison(frames, fact, flt: Filters, targets: dict | None = None) -> dict[str, Metric]:
    cur = compute(frames, fact, flt)
    if flt.start and flt.end:
        prev = compute(frames, fact, flt.shifted())
        for k, mt in cur.items():
            if prev.get(k) is not None and prev[k].ok:
                mt.previous = prev[k].value
    for k, v in (targets or {}).items():
        if k in cur and v is not None:
            cur[k].target = float(v)
    return cur


def exceptions(fact: pd.DataFrame | None, flt: Filters, targets: dict | None = None) -> dict[str, pd.DataFrame]:
    """예외 건: 지연 배송, 비용 초과 배송 (드릴다운 원장)."""
    if fact is None:
        return {}
    x = apply_filters(fact, flt)
    out = {"late": x[x["on_time"] == 0].sort_values("delay_days", ascending=False)}
    thr = (targets or {}).get("max_cost_per_shipment")
    c = x[x["cost"].notna()]
    if thr:
        out["cost_over"] = c[c["cost"] > float(thr)].sort_values("cost", ascending=False)
        out["cost_over_rule"] = f"배송당 비용 > 목표 {float(thr):,.0f}원"
    elif len(c) >= 20:
        p95 = float(c["cost"].quantile(0.95))
        out["cost_over"] = c[c["cost"] > p95].sort_values("cost", ascending=False)
        out["cost_over_rule"] = f"통계적 상위 5% (P95 {p95:,.0f}원 초과) — 목표값 미설정"
    return out


def by_dimension(fact: pd.DataFrame | None, flt: Filters, dim: str) -> pd.DataFrame:
    """Cost-to-Serve · 서비스 수준 차원별 집계."""
    if fact is None:
        return pd.DataFrame()
    x = apply_filters(fact, flt)
    if dim not in x.columns or x.empty:
        return pd.DataFrame()
    gb = x.assign(_late=(x["on_time"] == 0).astype(float)).groupby(dim, dropna=False)
    g = pd.DataFrame({"shipments": gb["shipment_id"].count(), "orders": gb["order_id"].nunique(),
                      "cost": gb["cost"].sum(min_count=1), "distance_km": gb["distance_km"].sum(min_count=1),
                      "weight_kg": gb["order_weight_kg"].sum(min_count=1), "on_time_n": gb["on_time"].count(),
                      "late": gb["_late"].sum()})
    g.index.name = dim
    g["cost_per_order"] = g["cost"] / g["orders"].replace(0, np.nan)
    g["cost_per_kg"] = g["cost"] / g["weight_kg"].replace(0, np.nan)
    g["cost_per_km"] = g["cost"] / g["distance_km"].replace(0, np.nan)
    g["late_rate"] = g["late"] / g["on_time_n"].replace(0, np.nan)
    return g.reset_index().sort_values("cost", ascending=False)


def store_map_frame(fact: pd.DataFrame | None, frames: dict, flt: Filters) -> pd.DataFrame:
    """지도용 배송지 집계 (좌표 보유 배송지만)."""
    st = frames.get("stores")
    if st is None:
        return pd.DataFrame()
    agg = by_dimension(fact, flt, "store_id") if fact is not None else pd.DataFrame(columns=["store_id"])
    out = st.merge(agg, on="store_id", how="left")
    if flt.regions:
        out = out[out["region"].isin(flt.regions)]
    if flt.stores:
        out = out[out["store_id"].isin(flt.stores)]
    return out.dropna(subset=["lat", "lon"])


def cost_change_by(fact: pd.DataFrame | None, flt: Filters, dim: str) -> pd.DataFrame:
    """직전 동일 길이 기간 대비 비용 변화 (예: '지난달 배송비가 가장 많이 증가한 거래처')."""
    if fact is None or not flt.start:
        return pd.DataFrame()
    cur = by_dimension(fact, flt, dim)[[dim, "cost", "orders"]]
    prev = by_dimension(fact, flt.shifted(), dim)[[dim, "cost", "orders"]]
    j = cur.merge(prev, on=dim, how="outer", suffixes=("_cur", "_prev"))
    j["cost_change"] = j["cost_cur"].fillna(0) - j["cost_prev"].fillna(0)
    j["cost_change_pct"] = (j["cost_cur"] / j["cost_prev"] - 1) * 100
    return j.sort_values("cost_change", ascending=False).reset_index(drop=True)
