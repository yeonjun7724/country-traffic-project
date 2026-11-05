"""외부 위험 분석: 영업소 취약성 · Shock Index · Impact · 교통량 기간 비교.

기존 산출물의 계산식을 역공학으로 확인한 재현 가능한 함수.
가중치 변경 시 재계산 결과는 '시뮬레이션'으로 표기하며 시나리오 ID로 관리한다.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

# 기존 산출물에서 역산·검증된 기본 가중치 (잔차 0)
VULN_COMPONENTS = {
    "freight_share": ("mean_freight_345_share", "화물 비율(일평균)"),
    "freight_volume": ("mean_freight_345_traffic", "화물 교통량(일평균)"),
    "volatility": ("traffic_volatility", "화물 교통량 변동계수"),
    "imbalance": ("abs_imbalance_ratio", "유출입 불균형(절대값)"),
}
DEFAULT_WEIGHTS = {"freight_share": 0.3, "freight_volume": 0.3, "volatility": 0.2, "imbalance": 0.2}
GRADES = ["Low", "Moderate", "High", "Very High"]


def minmax(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    lo, hi = s.min(), s.max()
    if not np.isfinite(lo) or hi == lo:
        return pd.Series(0.0, index=s.index)  # 분산 0 → 정보 없음
    return (s - lo) / (hi - lo)


def normalize_weights(w: dict[str, float]) -> dict[str, float]:
    if set(w) != set(VULN_COMPONENTS):
        raise ValueError(f"가중치 키는 {list(VULN_COMPONENTS)} 이어야 합니다.")
    if any(v < 0 for v in w.values()):
        raise ValueError("가중치는 음수일 수 없습니다.")
    tot = sum(w.values())
    if tot <= 0:
        raise ValueError("가중치 합이 0 입니다.")
    return {k: v / tot for k, v in w.items()}


def vulnerability(units: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.Series:
    w = normalize_weights(weights or DEFAULT_WEIGHTS)
    score = sum(w[k] * minmax(units[col]) for k, (col, _) in VULN_COMPONENTS.items())
    return score.rename("vulnerability_score")


def quartile_grade(score: pd.Series) -> pd.Series:
    """4분위 등급 (기존 vulnerability_grade / fuel_shock_impact_grade 와 동일 방식)."""
    return pd.qcut(score.rank(method="first"), 4, labels=GRADES).astype(str)


def verify_vulnerability(units: pd.DataFrame) -> dict:
    s = vulnerability(units, DEFAULT_WEIGHTS)
    diff = float((s - units["vulnerability_score"]).abs().max())
    return {"weights": DEFAULT_WEIGHTS, "max_abs_diff": diff}


def scenario_id(params: dict) -> str:
    return "RS-" + hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8].upper()


def recompute_units(units: pd.DataFrame, weights: dict[str, float], shock_index: float | None = None) -> pd.DataFrame:
    """가중치(및 선택적 shock 값)로 재계산. 원본 컬럼은 보존하고 sim_* 컬럼을 추가."""
    out = units.copy()
    out["sim_vulnerability"] = vulnerability(units, weights)
    out["sim_grade"] = quartile_grade(out["sim_vulnerability"])
    out["rank_base"] = units["vulnerability_score"].rank(ascending=False, method="min").astype(int)
    out["rank_sim"] = out["sim_vulnerability"].rank(ascending=False, method="min").astype(int)
    out["rank_change"] = out["rank_base"] - out["rank_sim"]
    if shock_index is not None:
        out["sim_impact"] = out["sim_vulnerability"] * shock_index
    return out


def shock_index_minmax(change_rate: pd.Series) -> pd.Series:
    """기존 산출물 방식: 예측 구간 내 변화율의 min-max (구간 내부 상대값)."""
    return minmax(change_rate)


def infer_ensemble_weight(forecast: pd.DataFrame) -> float | None:
    p, l, e = (forecast[c].astype(float) for c in ("diesel_price_prophet", "diesel_price_lstm", "diesel_price_ensemble"))
    d = p - l
    if (d.abs() < 1e-9).all():
        return None
    w = float(((e - l) * d).sum() / (d * d).sum())
    return w


def reweight_ensemble(forecast: pd.DataFrame, prophet_weight: float) -> pd.Series:
    """저장된 구성모델 예측값의 재가중 (재학습 아님)."""
    if not 0 <= prophet_weight <= 1:
        raise ValueError("prophet_weight 는 0~1")
    return prophet_weight * forecast["diesel_price_prophet"] + (1 - prophet_weight) * forecast["diesel_price_lstm"]


def route_summary(units: pd.DataFrame, score_col: str = "vulnerability_score") -> pd.DataFrame:
    g = units.groupby("routeName").agg(units=("unitCode", "count"), mean_score=(score_col, "mean"),
                                       max_score=(score_col, "max"),
                                       hh=("lisa_cluster", lambda s: int((s == "High-High").sum())))
    return g.sort_values("mean_score", ascending=False).reset_index()


def period_comparison(traffic: pd.DataFrame, event_date: str, value_col: str = "freight_345_traffic") -> dict:
    """기준일 전/후 관측 비교 (인과 추정 아님).

    - 단순 평균 비교
    - 요일 구성 차이를 보정한 비교 (요일별 평균의 평균)
    - 전년 동기간 비교(데이터가 있으면): 계절성 영향 참고치
    """
    t = traffic.copy()
    ev = pd.Timestamp(event_date)
    pre, post = t[t["date"] < ev], t[t["date"] >= ev]
    res: dict = {"event_date": event_date, "pre_days": len(pre), "post_days": len(post),
                 "pre_period": f"{pre['date'].min().date()}~{pre['date'].max().date()}" if len(pre) else "",
                 "post_period": f"{post['date'].min().date()}~{post['date'].max().date()}" if len(post) else ""}
    if not len(pre) or not len(post):
        res["status"] = "not_computable"
        return res
    res["pre_mean"], res["post_mean"] = float(pre[value_col].mean()), float(post[value_col].mean())
    res["change_pct"] = (res["post_mean"] / res["pre_mean"] - 1) * 100
    dw = lambda d: d.groupby(d["date"].dt.dayofweek)[value_col].mean().mean()  # noqa: E731
    res["pre_dow_adj"], res["post_dow_adj"] = float(dw(pre)), float(dw(post))
    res["change_pct_dow_adj"] = (res["post_dow_adj"] / res["pre_dow_adj"] - 1) * 100
    # 전년 동기간
    ly0, ly1 = post["date"].min() - pd.DateOffset(years=1), post["date"].max() - pd.DateOffset(years=1)
    ly = t[(t["date"] >= ly0) & (t["date"] <= ly1)]
    if len(ly) >= 0.8 * len(post):
        res["last_year_same_period_mean"] = float(ly[value_col].mean())
        res["yoy_pct"] = (res["post_mean"] / res["last_year_same_period_mean"] - 1) * 100
    res["status"] = "ok"
    res["caveat"] = "시점 간 관측 비교입니다. 계절성·추세·기타 요인이 통제되지 않아 인과관계를 의미하지 않습니다."
    return res
