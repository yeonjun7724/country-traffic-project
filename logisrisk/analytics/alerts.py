"""알림 규칙 평가 (앱 내 표시 전용 — 외부 발송 기능 없음)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

DEFAULT_RULES = {
    "otif_min": 0.95,          # OTIF 하한
    "late_rate_max": 0.05,     # 지연율 상한
    "monthly_cost_budget": None,  # 월 운송비 예산(원) — 선택 기간 일수로 일할 환산해 비교
    "stockout_max": 0,         # 결품 SKU·센터 허용 수
    "data_stale_days": 7,      # 데이터 갱신 지연 허용 일수
    "risk_vh_max": None,       # 외부: Very High 영업소 허용 수
}


DAYS_PER_MONTH = 365.25 / 12


# 규칙 key → '원인 보기' 목적지 (화면 키 = nav key, 화면 고유 파라미터). 기간·센터 등 전역 필터는 화면에서 이어 붙인다.
RULE_TARGETS: dict[str, tuple[str, dict[str, str]]] = {
    "otif": ("control-tower", {"ledger": "late"}),
    "late_rate": ("control-tower", {"ledger": "late"}),
    "cost_budget": ("transportation", {"tab": "cts"}),
    "stockout": ("inventory", {"risk": "결품"}),
    "data_stale": ("data-hub", {}),  # + entity → 해당 데이터 업로드 양식
}


def target_for(key: str, **extra: str) -> dict | None:
    """규칙 key 의 목적지. 조치 항목이 저장한 알림 key 로 근거 화면 링크를 다시 만들 때도 쓴다."""
    if key not in RULE_TARGETS:
        return None
    screen, params = RULE_TARGETS[key]
    return {"screen": screen, "params": {**params, **extra}}


def evaluate(kpis: dict, rules: dict, versions: dict, inventory: dict | None = None,
             now: datetime | None = None, period_days: int | None = None) -> list[dict]:
    now = now or datetime.now()
    out = []

    def add(sev, rule, msg, source, key, **target_params):
        out.append({"severity": sev, "rule": rule, "message": msg, "source": source, "key": key,
                    "target": target_for(key, **target_params)})

    m = kpis.get("otif")
    if m is not None and m.ok and rules.get("otif_min") is not None and m.value < rules["otif_min"]:
        add("high", "SLA(OTIF) 미달", f"OTIF {m.value:.1%} < 목표 {rules['otif_min']:.0%} (n={m.n})", "KPI", "otif")
    m = kpis.get("late_rate")
    if m is not None and m.ok and rules.get("late_rate_max") is not None and m.value > rules["late_rate_max"]:
        add("medium", "배송 지연율 초과", f"지연율 {m.value:.1%} > 허용 {rules['late_rate_max']:.0%}", "KPI", "late_rate")
    m = kpis.get("cost")
    if m is not None and m.ok and rules.get("monthly_cost_budget") and period_days:
        budget = float(rules["monthly_cost_budget"]) * period_days / DAYS_PER_MONTH
        if m.value > budget:
            add("high", "운송비 예산 초과",
                f"운송비 {m.value:,.0f}원 > 기간 예산 {budget:,.0f}원 (월 예산 {float(rules['monthly_cost_budget']):,.0f}원 × {period_days}일 일할)",
                "KPI", "cost_budget")
    if inventory and inventory.get("status") == "ok":
        so = inventory["summary"]["stockout"]
        if so > (rules.get("stockout_max") or 0):
            add("high", "재고 부족(결품)", f"가용재고 0 이하 SKU·센터 {so}건", "재고", "stockout")
    lim = rules.get("data_stale_days")
    if lim:
        for ent, v in versions.items():
            try:
                age = (now - pd.Timestamp(v["uploaded_at"]).to_pydatetime()).days
            except Exception:
                continue
            if age > lim:
                add("low", "데이터 갱신 지연", f"{ent} 마지막 업로드 {age}일 전 (허용 {lim}일)", "데이터 허브", "data_stale",
                    entity=str(ent))
    return out
