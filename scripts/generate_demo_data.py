"""DEMO(가상) 데이터 생성기 — 테스트·시연 전용. 실제 기업 실적이 아님.

생성물: fixtures/demo/DEMO_*.csv  (시드 고정 → 재현 가능)
앱에서는 'DEMO 워크스페이스' 에만 적재되며 모든 화면에 DEMO 배지가 표시된다.

실행: python scripts/generate_demo_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from logisrisk.analytics.routing import haversine_km  # noqa: E402

OUT = ROOT / "fixtures" / "demo"
SEED = 20261105


def main(out: Path = OUT, days: int = 92, end: str = "2026-10-31") -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    out.mkdir(parents=True, exist_ok=True)

    wh = pd.DataFrame([
        ("WH-A", "DEMO 수도권센터", 37.2636, 127.0286, "수도권", 260),
        ("WH-B", "DEMO 중부센터", 36.3504, 127.3845, "충청", 140),
        ("WH-C", "DEMO 영남센터", 35.8714, 128.6014, "영남", 160),
    ], columns=["warehouse_id", "name", "lat", "lon", "region", "daily_capacity_orders"])

    cities = [("수도권", 37.50, 127.00, 0.25, 26), ("강원", 37.75, 128.40, 0.30, 5), ("충청", 36.55, 127.25, 0.30, 10),
              ("호남", 35.30, 126.90, 0.30, 7), ("영남", 35.55, 128.80, 0.35, 14)]
    rows, k = [], 1
    for reg, la, lo, sp, n in cities:
        for _ in range(n):
            rows.append((f"ST-{k:03d}", f"DEMO 점포 {k:03d}", round(la + rng.normal(0, sp / 2), 5),
                         round(lo + rng.normal(0, sp / 2), 5), reg, rng.choice(["대형마트", "편의점", "도매"]),
                         "08:00", "18:00", float(rng.choice([10, 15, 20]))))
            k += 1
    st = pd.DataFrame(rows, columns=["store_id", "name", "lat", "lon", "region", "customer_group",
                                     "tw_start", "tw_end", "service_min"])
    # 배송지 → 최근접 센터
    dmat = np.stack([haversine_km(st["lat"], st["lon"], w.lat, w.lon) for w in wh.itertuples()], axis=1)
    st_wh = wh["warehouse_id"].to_numpy()[dmat.argmin(axis=1)]
    st_dist = dmat.min(axis=1)

    cats = ["가공식품", "음료", "생활용품", "냉장식품"]
    sk = pd.DataFrame({"sku_id": [f"SKU-{i:03d}" for i in range(1, 41)],
                       "name": [f"DEMO 상품 {i:03d}" for i in range(1, 41)],
                       "category": [cats[i % 4] for i in range(40)],
                       "unit_weight_kg": np.round(rng.uniform(0.5, 12, 40), 2),
                       "unit_volume_m3": np.round(rng.uniform(0.002, 0.04, 40), 4),
                       "unit_cost": np.round(rng.uniform(1500, 30000, 40), -2)})

    vrows = []
    for w, n in (("WH-A", 9), ("WH-B", 5), ("WH-C", 6)):
        for i in range(n):
            big = i % 3 == 0
            vrows.append((f"{w[-1]}-TRK{i + 1:02d}", w, ["DEMO운송A", "DEMO운송B"][i % 2], "5톤" if big else "2.5톤",
                          5000.0 if big else 2500.0, 30.0 if big else 16.0, 4.5 if big else 6.5,
                          180000.0 if big else 130000.0, 380.0 if big else 300.0, 10.0, True))
    vh = pd.DataFrame(vrows, columns=["vehicle_id", "home_warehouse_id", "carrier", "vehicle_type", "capacity_kg",
                                      "capacity_m3", "fuel_efficiency_km_per_l", "fixed_cost_per_day",
                                      "variable_cost_per_km", "max_hours", "available"])

    dates = pd.date_range(end=end, periods=days, freq="D")
    base_price = 1720.0
    fp = pd.DataFrame({"date": dates, "region": "ALL",
                       "diesel_price": np.round(base_price + np.cumsum(rng.normal(0.4, 6, days)), 1)})

    orders, lines, ships = [], [], []
    oid = sid = 1
    for d in dates:
        dow_f = 0.55 if d.dayofweek == 6 else 1.0
        n = rng.poisson(28 * dow_f)
        stores_today = rng.choice(len(st), size=min(n, len(st)), replace=False)
        day_orders = []
        for si in stores_today:
            o = f"OD-{oid:06d}"
            oid += 1
            w = st_wh[si]
            orders.append((o, d, st.loc[si, "store_id"], w, d + pd.Timedelta(days=1), "delivered"))
            nl = rng.integers(2, 6)
            wkg = 0.0
            for s in rng.choice(40, size=nl, replace=False):
                q = float(rng.integers(5, 60))
                lines.append((o, sk.loc[s, "sku_id"], q))
                wkg += q * sk.loc[s, "unit_weight_kg"]
            day_orders.append((o, si, w, wkg))
        # 센터별 차량에 순차 배정 (용량 기준)
        for w in wh["warehouse_id"]:
            vs = vh[vh["home_warehouse_id"] == w].reset_index(drop=True)
            load = np.zeros(len(vs))
            for o, si, ww, wkg in [x for x in day_orders if x[2] == w]:
                j = int(np.argmin(load / vs["capacity_kg"]))
                load[j] += wkg
                v = vs.loc[j]
                dist = float(st_dist[si] * 1.3 * 2)  # 왕복, DEMO 가정 우회계수
                fuel_l = dist / v["fuel_efficiency_km_per_l"]
                price = float(fp.loc[fp["date"] == d, "diesel_price"].iloc[0])
                fuel_c = fuel_l * price * rng.normal(1.0, 0.02)
                toll = 0.0 if dist < 40 else dist * 45
                other = v["variable_cost_per_km"] * dist * 0.5
                late_p = 0.03 + 0.12 * (st.loc[si, "region"] in ("강원", "호남")) + 0.05 * (d.dayofweek == 0)
                delay = int(rng.random() < late_p) * int(rng.integers(1, 3))
                ordered = sum(q for (oo, _, q) in lines if oo == o)
                short = rng.random() < 0.03
                ships.append((f"SH-{sid:06d}", o, v["vehicle_id"], v["carrier"], d, d + pd.Timedelta(days=1),
                              d + pd.Timedelta(days=1 + delay), ordered - (rng.integers(1, 5) if short else 0),
                              round(wkg, 1), round(dist, 1), round(fuel_l, 2), round(fuel_c, 0), round(toll, 0),
                              round(other, 0), None, "delivered"))
                sid += 1
    # 마지막 날 접수된 다음날 납기 미출고 주문 (배송 계획 '미출고 주문' 모드 시연용)
    nxt = dates[-1] + pd.Timedelta(days=1)
    for si in rng.choice(len(st), size=32, replace=False):
        o = f"OD-{oid:06d}"
        oid += 1
        orders.append((o, dates[-1], st.loc[si, "store_id"], st_wh[si], nxt, "created"))
        for s in rng.choice(40, size=rng.integers(2, 6), replace=False):
            lines.append((o, sk.loc[s, "sku_id"], float(rng.integers(5, 60))))
    od = pd.DataFrame(orders, columns=["order_id", "order_date", "store_id", "warehouse_id", "requested_date", "status"])
    ol = pd.DataFrame(lines, columns=["order_id", "sku_id", "qty"])
    sh = pd.DataFrame(ships, columns=["shipment_id", "order_id", "vehicle_id", "carrier", "ship_date",
                                      "planned_delivery_date", "actual_delivery_date", "delivered_qty", "load_kg",
                                      "distance_km", "fuel_l", "fuel_cost", "toll_cost", "other_cost", "total_cost",
                                      "status"])
    # 고정비 배분: 차량·일자 운행당 고정비를 배송 건수로 나눔
    per_trip = sh.groupby(["vehicle_id", "ship_date"])["shipment_id"].transform("count")
    fixed = sh["vehicle_id"].map(vh.set_index("vehicle_id")["fixed_cost_per_day"]) / per_trip
    sh["total_cost"] = (sh["fuel_cost"] + sh["toll_cost"] + sh["other_cost"] + fixed).round(0)

    inv = []
    last = dates[-1]
    for w in wh["warehouse_id"]:
        for s in sk["sku_id"]:
            inv.append((last, w, s, float(rng.integers(0, 900)), float(rng.integers(0, 60)),
                        float(rng.choice([0, 0, 200, 400])), float(rng.choice([2, 3, 5]))))
    iv = pd.DataFrame(inv, columns=["snapshot_date", "warehouse_id", "sku_id", "on_hand", "allocated", "inbound_qty",
                                    "lead_time_days"])

    frames = {"warehouses": wh, "stores": st, "skus": sk, "vehicles": vh, "orders": od, "order_lines": ol,
              "shipments": sh, "inventory": iv, "fuel_prices": fp}
    for name, df in frames.items():
        x = df.copy()
        for c in x.columns:
            if pd.api.types.is_datetime64_any_dtype(x[c]):
                x[c] = x[c].dt.strftime("%Y-%m-%d")
        x.to_csv(out / f"DEMO_{name}.csv", index=False, encoding="utf-8-sig")

    # 검증 테스트용 오류 포함 파일 (의도적 오류)
    bad = od.head(8).copy()
    bad["order_date"] = bad["order_date"].dt.strftime("%Y-%m-%d")
    bad["requested_date"] = bad["requested_date"].dt.strftime("%Y-%m-%d")
    bad.loc[1, "order_date"] = "2026-13-45"          # 날짜 형식 오류
    bad.loc[2, "store_id"] = "ST-999"                # 존재하지 않는 배송지
    bad.loc[3, "order_id"] = bad.loc[4, "order_id"]  # 기본키 중복
    bad.loc[5, "status"] = "lost"                    # 허용값 아님
    bad.loc[6, "warehouse_id"] = None                # 필수값 누락
    bad.rename(columns={"order_id": "주문번호", "order_date": "주문일자", "store_id": "거래처코드",
                        "warehouse_id": "출고센터", "requested_date": "납기일", "status": "주문상태"}) \
        .to_csv(out / "DEMO_invalid_orders_for_validation.csv", index=False, encoding="utf-8-sig")
    return frames


if __name__ == "__main__":
    fr = main()
    for k, v in fr.items():
        print(f"{k:12s} {len(v):6d} rows")
