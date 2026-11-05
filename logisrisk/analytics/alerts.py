"""알림 규칙 평가 (앱 내 표시 전용 — 외부 발송 기능 없음)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

DEFAULT_RULES = {
    "otif_min": 0.95,          # OTIF 하한
    "late_rate_max": 0.05,     # 지연율 상한
    "cost_budget": None,       # 기간 운송비 예산(원)
    "stockout_max": 0,         # 결품 SKU·센터 허용 수
    "data_stale_days": 7,      # 데이터 갱신 지연 허용 일수
    "risk_vh_max": None,       # 외부: Very High 영업소 허용 수
}


def evaluate(kpis: dict, rules: dict, versions: dict, inventory: dict | None = None,
             now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    out = []

    def add(sev, rule, msg, source):
        out.append({"severity": sev, "rule": rule, "message": msg, "source": source})

    m = kpis.get("otif")
    if m is not None and m.ok and rules.get("otif_min") is not None and m.value < rules["otif_min"]:
        add("high", "SLA(OTIF) 미달", f"OTIF {m.value:.1%} < 목표 {rules['otif_min']:.0%} (n={m.n})", "KPI")
    m = kpis.get("late_rate")
    if m is not None and m.ok and rules.get("late_rate_max") is not None and m.value > rules["late_rate_max"]:
        add("medium", "배송 지연율 초과", f"지연율 {m.value:.1%} > 허용 {rules['late_rate_max']:.0%}", "KPI")
    m = kpis.get("cost")
    if m is not None and m.ok and rules.get("cost_budget"):
        if m.value > float(rules["cost_budget"]):
            add("high", "운송비 예산 초과", f"운송비 {m.value:,.0f}원 > 예산 {float(rules['cost_budget']):,.0f}원", "KPI")
    if inventory and inventory.get("status") == "ok":
        so = inventory["summary"]["stockout"]
        if so > (rules.get("stockout_max") or 0):
            add("high", "재고 부족(결품)", f"가용재고 0 이하 SKU·센터 {so}건", "재고")
    lim = rules.get("data_stale_days")
    if lim:
        for ent, v in versions.items():
            try:
                age = (now - pd.Timestamp(v["uploaded_at"]).to_pydatetime()).days
            except Exception:
                continue
            if age > lim:
                add("low", "데이터 갱신 지연", f"{ent} 마지막 업로드 {age}일 전 (허용 {lim}일)", "데이터 허브")
    return out
