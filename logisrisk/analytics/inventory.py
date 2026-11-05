"""재고 · 수요 · 보충 분석 (기업 재고/주문 이력이 업로드된 경우에만 계산).

- 수요 = 주문상세 수량(주문일·출고센터 기준). 출고/판매 실적이 아님을 명시.
- 안전재고 = z · σ_d · √LT,  재주문점(ROP) = μ_d · LT + 안전재고  (수요 독립·정규 근사, LT 고정 가정)
- 예측 모델 비교: Naive, 계절성 Naive(7일), 이동평균(7/28일) — holdout 백테스트로 WAPE/MAE/Bias 비교.
"""
from __future__ import annotations

from statistics import NormalDist

import numpy as np
import pandas as pd


def daily_demand(frames: dict) -> pd.DataFrame | None:
    o, ol = frames.get("orders"), frames.get("order_lines")
    if o is None or ol is None:
        return None
    x = ol.merge(o[["order_id", "order_date", "warehouse_id", "status"]], on="order_id", how="inner")
    x = x[x["status"].fillna("") != "cancelled"]
    return x.groupby(["warehouse_id", "sku_id", "order_date"], as_index=False)["qty"].sum()


def _dense(series: pd.DataFrame, start, end) -> pd.Series:
    idx = pd.date_range(start, end, freq="D")
    return series.set_index("order_date")["qty"].reindex(idx, fill_value=0.0)


def replenishment(frames: dict, service_level: float = 0.95, window_days: int = 28,
                  default_lead_time: float | None = None, review_days: float = 7.0) -> dict:
    inv, dd = frames.get("inventory"), daily_demand(frames)
    if inv is None:
        return {"status": "not_computable", "reason": "재고(inventory) 스냅샷이 업로드되지 않았습니다. 재고 위험을 추정하지 않습니다."}
    if dd is None or dd.empty:
        return {"status": "not_computable", "reason": "주문·주문상세 이력이 없어 수요를 계산할 수 없습니다."}
    snap_date = inv["snapshot_date"].max()
    cur = inv[inv["snapshot_date"] == snap_date].copy()
    end = min(snap_date, dd["order_date"].max())
    start = end - pd.Timedelta(days=window_days - 1)
    if not 0.5 <= service_level < 1:
        raise ValueError("service_level 은 0.5~1 미만")
    z = NormalDist().inv_cdf(service_level)
    # SKU×센터별 일 수요 행렬 (주문 없는 날 = 0) — 한 번에 계산
    win = dd[(dd["order_date"] >= start) & (dd["order_date"] <= end)]
    mat = win.pivot_table(index=["warehouse_id", "sku_id"], columns="order_date", values="qty", aggfunc="sum",
                          fill_value=0.0).reindex(columns=pd.date_range(start, end, freq="D"), fill_value=0.0)
    mu_s, sd_s = mat.mean(axis=1), mat.std(axis=1, ddof=1)
    rows = []
    for r in cur.itertuples():
        key = (r.warehouse_id, r.sku_id)
        mu = float(mu_s.get(key, 0.0))
        sd = float(sd_s.get(key, 0.0)) if window_days > 1 else 0.0
        sd = 0.0 if sd != sd else sd
        lt = r.lead_time_days if pd.notna(r.lead_time_days) else default_lead_time
        avail = float(r.on_hand - (r.allocated if pd.notna(r.allocated) else 0))
        inbound = float(r.inbound_qty) if pd.notna(r.inbound_qty) else 0.0
        row = {"warehouse_id": r.warehouse_id, "sku_id": r.sku_id, "on_hand": r.on_hand, "available": avail,
               "inbound_qty": inbound, "avg_daily_demand": mu, "std_daily_demand": sd, "lead_time_days": lt,
               "days_of_supply": avail / mu if mu > 0 else np.inf if avail > 0 else 0.0}
        if lt is None or pd.isna(lt):
            row.update(safety_stock=np.nan, reorder_point=np.nan, recommended_qty=np.nan,
                       basis="리드타임 미입력 → 재주문점 계산 불가")
        else:
            ss = z * sd * np.sqrt(lt)
            rop = mu * lt + ss
            target = rop + mu * review_days
            pos = avail + inbound
            rec = max(0.0, target - pos) if pos <= rop else 0.0
            if pos <= rop:
                basis = f"재고포지션 {pos:,.0f}(가용 {avail:,.0f}+입고예정 {inbound:,.0f}) ≤ ROP {rop:,.0f} → 목표 {target:,.0f}까지 보충"
            elif avail <= 0:
                basis = (f"현재 결품(가용 {avail:,.0f}) — 입고예정 {inbound:,.0f} 반영 시 ROP {rop:,.0f} 초과로 추가 발주 불필요. "
                         "입고 일정이 고객 납기 이전인지 확인 필요")
            else:
                basis = f"재고포지션 {pos:,.0f} > ROP {rop:,.0f} → 보충 불필요"
            row.update(safety_stock=ss, reorder_point=rop, recommended_qty=float(np.ceil(rec)), basis=basis)
        row["stockout_risk"] = ("결품" if avail <= 0 else
                                "높음" if pd.notna(row["reorder_point"]) and avail + inbound <= row["reorder_point"] else
                                "낮음" if pd.notna(row["reorder_point"]) else "판정 불가")
        rows.append(row)
    t = pd.DataFrame(rows)
    return {"status": "ok", "snapshot_date": str(snap_date.date()), "demand_window": f"{start.date()}~{end.date()}",
            "service_level": service_level, "z": z, "table": t.sort_values("days_of_supply"),
            "summary": {"sku_locations": len(t), "stockout": int((t["available"] <= 0).sum()),
                        "high_risk": int((t["stockout_risk"] == "높음").sum()),
                        "stockout_rate": float((t["available"] <= 0).mean()) if len(t) else None},
            "assumptions": ["수요는 주문수량(취소 제외) 기준이며 실제 출고·판매량과 다를 수 있음.",
                            f"최근 {window_days}일 일별 수요의 평균·표준편차 사용 (주문 없는 날 = 0).",
                            "수요는 정규분포·일간 독립, 리드타임은 고정이라고 가정.",
                            f"주기적 검토 {review_days:g}일, 보충 목표 = ROP + 검토주기 수요."]}


def wape(a: np.ndarray, f: np.ndarray) -> float | None:
    den = np.abs(a).sum()
    return float(np.abs(a - f).sum() / den) if den > 0 else None


def mape(a: np.ndarray, f: np.ndarray) -> tuple[float | None, int]:
    """0 실적은 제외(제외 건수 반환)."""
    m = a != 0
    if not m.any():
        return None, int((~m).sum())
    return float(np.mean(np.abs((a[m] - f[m]) / a[m]))), int((~m).sum())


def backtest(series: pd.Series, horizon: int = 14) -> pd.DataFrame:
    """일별 수요 시계열 단일에 대해 단순 모델 비교."""
    if len(series) < horizon + 28:
        return pd.DataFrame()
    train, test = series.iloc[:-horizon], series.iloc[-horizon:]
    a = test.to_numpy(float)
    preds = {
        "Naive(전일)": np.repeat(train.iloc[-1], horizon),
        "계절성 Naive(7일)": np.resize(train.iloc[-7:].to_numpy(), horizon),
        "이동평균 7일": np.repeat(train.iloc[-7:].mean(), horizon),
        "이동평균 28일": np.repeat(train.iloc[-28:].mean(), horizon),
    }
    # 요일 효과: 최근 8주 요일별 평균
    dow = train.iloc[-56:].groupby(train.index[-56:].dayofweek).mean()
    preds["요일평균(8주)"] = np.array([dow.get(d.dayofweek, train.mean()) for d in test.index])
    rows = []
    for k, f in preds.items():
        mp, z = mape(a, f)
        rows.append({"model": k, "WAPE": wape(a, f), "MAE": float(np.mean(np.abs(a - f))),
                     "Bias": float(np.mean(f - a)), "MAPE(0제외)": mp, "MAPE 제외건": z})
    return pd.DataFrame(rows).sort_values("WAPE", na_position="last").reset_index(drop=True)


def forecast_sku(frames: dict, sku_id: str, warehouse_id: str | None = None, horizon: int = 14) -> dict:
    dd = daily_demand(frames)
    if dd is None or dd.empty:
        return {"status": "not_computable", "reason": "주문 이력 없음"}
    h = dd[dd["sku_id"] == sku_id]
    if warehouse_id:
        h = h[h["warehouse_id"] == warehouse_id]
    if h.empty:
        return {"status": "not_computable", "reason": "해당 SKU 주문 이력 없음"}
    h = h.groupby("order_date", as_index=False)["qty"].sum()
    s = _dense(h, dd["order_date"].min(), dd["order_date"].max())
    bt = backtest(s, horizon)
    if bt.empty:
        return {"status": "not_computable", "reason": f"이력이 {horizon + 28}일 미만이라 백테스트 불가", "series": s}
    return {"status": "ok", "series": s, "backtest": bt, "best": bt.iloc[0]["model"], "horizon": horizon}
