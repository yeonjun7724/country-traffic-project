"""외부 위험 데이터 (기존 공모전 분석 산출물) 로더 + 자동 감사.

이 데이터는 '고속도로 영업소·전국 유가·전국 교통량' 이며, 개별 기업의 주문·배송·재고
실적이 아니다. 화면/AI/리포트에서 항상 '외부 위험 지표'로 구분해 표시한다.
모든 기간·건수는 파일에서 계산한다 (하드코딩 금지).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import OUTPUT_DIR, REFERENCE_EVENT_DATE, ROOT
from ..provenance import Provenance

FILES = {
    "units": "impact_score_grade_unit.csv",
    "fuel_history": "model_A_inputdata.csv",
    "forecast_final": "model_A_result_final.csv",
    "forecast_ensemble": "model_A_result_ensemble.csv",
    "traffic": "pre_post_war_traffic_volumne.csv",
}

UNIT_REQUIRED = ["unitCode", "unitName", "routeName", "xValue", "yValue", "vulnerability_score",
                 "mean_freight_345_share", "mean_freight_345_traffic", "traffic_volatility",
                 "abs_imbalance_ratio", "local_moran_i", "local_p_value", "lisa_cluster"]


def _find(name: str, dirs: list[Path] | None = None) -> Path | None:
    for d in dirs or [OUTPUT_DIR, ROOT]:
        p = Path(d) / name
        if p.exists():
            return p
    return None


@dataclass
class ExternalData:
    units: pd.DataFrame | None = None
    fuel_history: pd.DataFrame | None = None
    forecast: pd.DataFrame | None = None
    traffic: pd.DataFrame | None = None
    provenance: dict[str, Provenance] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)  # 감사 결과

    @property
    def available(self) -> bool:
        return self.units is not None


def load_external(dirs: list[Path] | None = None, today: date | None = None) -> ExternalData:
    today = today or datetime.now().date()
    ext = ExternalData()

    p = _find(FILES["units"], dirs)
    if p:
        u = pd.read_csv(p, encoding="utf-8-sig")
        miss = [c for c in UNIT_REQUIRED if c not in u.columns]
        if miss:
            ext.missing.append(f"{FILES['units']} (컬럼 누락: {', '.join(miss)})")
        else:
            u["unitCode"] = u["unitCode"].astype(str)
            ext.units = u
            ext.provenance["units"] = Provenance(
                source=f"output/{FILES['units']}", kind="derived", unit="점수(0~1)",
                method="TCS 영업소별 교통량 집계 → 4개 지표 min-max 정규화 가중합(취약성), Local Moran's I(LISA)",
                n=len(u), version=_mtime(p))
    else:
        ext.missing.append(FILES["units"])

    p = _find(FILES["fuel_history"], dirs)
    if p:
        h = pd.read_csv(p, encoding="utf-8-sig", parse_dates=["date"])
        ext.fuel_history = h.sort_values("date").reset_index(drop=True)
        ext.provenance["fuel_history"] = Provenance(
            source=f"output/{FILES['fuel_history']}", kind="observed", unit="경유·휘발유 원/L, WTI·Brent USD/bbl",
            period_start=str(h["date"].min().date()), period_end=str(h["date"].max().date()), n=len(h),
            method="원천 수집 파이프라인 산출물(국내 평균 유가·국제 유가·환율 등). 기업 구매 단가 아님",
            version=_mtime(p))
    else:
        ext.missing.append(FILES["fuel_history"])

    pf, pe = _find(FILES["forecast_final"], dirs), _find(FILES["forecast_ensemble"], dirs)
    if pf and pe:
        f = pd.read_csv(pf, encoding="utf-8-sig", parse_dates=["date"])
        e = pd.read_csv(pe, encoding="utf-8-sig", parse_dates=["date"])
        f = f.merge(e[["date", "diesel_price_prophet_lower", "diesel_price_prophet_upper"]], on="date", how="left")
        ext.forecast = f.sort_values("date").reset_index(drop=True)
        stale = (pd.Timestamp(today) - f["date"].max()).days
        w = []
        if stale > 0:
            w.append(f"예측 기간({f['date'].min().date()}~{f['date'].max().date()})이 오늘({today}) 기준 "
                     f"{stale}일 지난 과거입니다. 재학습 전까지 미래 전망으로 사용할 수 없습니다.")
        ext.provenance["forecast"] = Provenance(
            source=f"output/{FILES['forecast_final']} + {FILES['forecast_ensemble']}", kind="forecast",
            unit="원/L", period_start=str(f["date"].min().date()), period_end=str(f["date"].max().date()),
            n=len(f), method="Prophet·LSTM 예측의 가중 앙상블 (저장된 산출물, 이 앱에서 재학습하지 않음)",
            version=_mtime(pf), warnings=w)
    else:
        ext.missing.append(f"{FILES['forecast_final']} / {FILES['forecast_ensemble']}")

    p = _find(FILES["traffic"], dirs)
    if p:
        t = pd.read_csv(p, encoding="utf-8-sig")
        t["date"] = pd.to_datetime(t["sumDate"])
        t = t.sort_values("date").reset_index(drop=True)
        t["total_traffic"] = t["passenger_126_traffic"] + t["freight_345_traffic"]
        t["freight_share"] = np.where(t["total_traffic"] > 0, t["freight_345_traffic"] / t["total_traffic"], np.nan)
        ext.traffic = t
        ext.provenance["traffic"] = Provenance(
            source=f"output/{FILES['traffic']}", kind="observed", unit="대/일 (전국 고속도로 합계)",
            period_start=str(t["date"].min().date()), period_end=str(t["date"].max().date()), n=len(t),
            method="TCS 일별 전국 합계. 승용(1·2·6종)/화물(3·4·5종)", version=_mtime(p))
    else:
        ext.missing.append(FILES["traffic"])

    ext.findings = audit_external(ext, today)
    return ext


def _mtime(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")


def audit_external(ext: ExternalData, today: date) -> list[dict]:
    """기존 산출물의 정합성·재현성·해석상 주의점을 자동 점검한다 (결과는 파일에서 매번 재계산)."""
    from ..analytics import risk

    out: list[dict] = []

    def add(level: str, title: str, detail: str):
        out.append({"level": level, "title": title, "detail": detail})

    u = ext.units
    if u is not None:
        add("info", "공간분석 모집단",
            f"좌표 보유 영업소 {len(u)}개 (파일 기준). 과거 화면의 '476개소'는 이 파일로 검증할 수 없는 값이므로 사용하지 않습니다.")
        dup = int(u["unitCode"].duplicated().sum())
        if dup:
            add("error", "영업소 코드 중복", f"{dup}건")
        bad = ~(u["yValue"].between(33, 39) & u["xValue"].between(124, 132))
        if bad.any():
            add("error", "좌표 범위 오류", f"국내 범위 밖 좌표 {int(bad.sum())}건")
        rep = risk.verify_vulnerability(u)
        add("ok" if rep["max_abs_diff"] < 1e-9 else "error", "취약성 점수 재현성",
            f"min-max 정규화 후 가중합 {rep['weights']} 로 재계산 시 최대 오차 {rep['max_abs_diff']:.2e}")
        if "mean_diesel_shock_index_30d" in u.columns:
            k = u["mean_diesel_shock_index_30d"].nunique()
            if k == 1:
                add("warn", "Fuel Shock Impact Score 해석 주의",
                    f"Shock Index 가 전 영업소 동일 상수({u['mean_diesel_shock_index_30d'].iloc[0]:.4f})입니다. "
                    "Impact Score = 취약성 × 상수 이므로 순위는 취약성 점수와 동일하며, 영업소별 유류 충격 차이를 담고 있지 않습니다.")
        if "fuel_shock_impact_score_mean" in u.columns and "mean_diesel_shock_index_30d" in u.columns:
            ok = np.allclose(u["vulnerability_score"] * u["mean_diesel_shock_index_30d"],
                             u["fuel_shock_impact_score_mean"])
            add("ok" if ok else "error", "Impact Score 재현성",
                "Impact(mean) = Vulnerability × mean Shock Index " + ("일치" if ok else "불일치"))
        sig_ok = bool(((u["local_p_value"] < 0.05) == u["lisa_significant"]).all()) if "lisa_significant" in u else None
        if sig_ok is not None:
            add("ok" if sig_ok else "error", "LISA 유의성 플래그", "p<0.05 기준과 " + ("일치" if sig_ok else "불일치"))
        add("info", "화물 비율 정의",
            "mean_freight_345_share 는 '일별 화물비율의 평균'이며 평균 화물량/평균 총량 비율과 다릅니다(최대 차이 "
            f"{(u['mean_freight_345_traffic'] / u['mean_total_traffic'] - u['mean_freight_345_share']).abs().max():.3f}).")
        if {"impact_grade", "fuel_shock_impact_grade"} <= set(u.columns):
            add("info", "등급 체계 2종 공존",
                "fuel_shock_impact_grade 는 4분위 등급, impact_grade 는 상위 5%/5%/40%/50% 구간 등급입니다. 화면마다 어떤 등급인지 명시합니다.")
    f = ext.forecast
    if f is not None:
        stale = (pd.Timestamp(today) - f["date"].max()).days
        if stale > 0:
            add("warn", "유가 예측 기간 경과",
                f"예측 기간 {f['date'].min().date()}~{f['date'].max().date()} — 오늘({today}) 기준 {stale}일 경과. "
                "'향후 30일'로 표시하지 않으며, 재학습 없이 미래 전망에 쓰지 않습니다.")
        w = risk.infer_ensemble_weight(f)
        if w is not None:
            add("info", "앙상블 가중치 역산", f"ensemble = {w:.2f}·Prophet + {1 - w:.2f}·LSTM (저장된 산출물 기준)")
        gap = (f["diesel_price_prophet"] - f["diesel_price_lstm"]).abs()
        add("warn", "구성 모델 간 큰 불일치",
            f"Prophet·LSTM 예측 차이 평균 {gap.mean():,.0f}원/L (최대 {gap.max():,.0f}원/L). 예측 불확실성이 큽니다.")
        if "diesel_change_rate" in f and (f["diesel_change_rate"] < 0).all() and (f["risk_level"] == "CRITICAL").any():
            add("warn", "위험 등급 의미 불일치",
                "예측 경유가가 전 기간 마지막 관측가보다 낮음(변화율 "
                f"{f['diesel_change_rate'].min():.1f}%~{f['diesel_change_rate'].max():.1f}%)에도 CRITICAL 등급이 존재합니다. "
                "Shock Index 가 30일 구간 내 min-max 상대값이기 때문이며, 절대적 가격 상승 위험을 의미하지 않습니다.")
    if ext.traffic is not None:
        t = ext.traffic
        full = pd.date_range(t["date"].min(), t["date"].max())
        miss = len(full.difference(t["date"]))
        add("ok" if miss == 0 else "warn", "교통량 시계열 연속성", f"누락 일자 {miss}일, 중복 {int(t['date'].duplicated().sum())}일")
        add("info", "기준 이벤트 전후 비교 해석",
            f"{REFERENCE_EVENT_DATE} 전후 비교는 시점 간 관측 비교이며, 계절성·추세·기타 요인이 통제되지 않아 인과관계를 입증하지 않습니다.")
    if _find("impact_score_route.csv"):
        add("warn", "노선 결과 파일 키 누락",
            "impact_score_route.csv 에 노선명 컬럼이 없어 단독 사용 불가 → 영업소 파일에서 노선별 평균을 재계산합니다.")
    return out
