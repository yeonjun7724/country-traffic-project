"""09 Reports & Alerts · 10 Settings 뷰 모델 (리포트 구성은 Streamlit·API 공통)."""
from __future__ import annotations

import os

import pandas as pd

from ..analytics import alerts, cost, inventory, kpi
from ..config import DATABASE_URL, OPENAI_MODEL, access_code, openai_api_key
from ..provenance import KIND_LABEL
from ..reports.export import excel_report, html_summary, metrics_frame
from ..security import PERMISSIONS, ROLE_LABEL
from ..services import Workbench

REPORT_SECTIONS = ["KPI", "Cost-to-Serve(운송사)", "Cost-to-Serve(배송지)", "지연 배송", "경유가 민감도", "재고 보충",
                   "외부 위험(영업소)", "외부 데이터 감사"]
DEFAULT_SECTIONS = ["KPI", "Cost-to-Serve(운송사)", "지연 배송", "경유가 민감도", "외부 데이터 감사"]


def provenance_frame(prov: dict) -> pd.DataFrame:
    return pd.DataFrame([{"데이터": k, "출처": p.source, "성격": KIND_LABEL.get(p.kind, p.kind),
                          "기간": f"{p.period_start or ''}~{p.period_end or ''}", "표본": p.n, "방법": p.method,
                          "주의": " / ".join(p.warnings)} for k, p in prov.items()])


def build_report(wb: Workbench, flt: kpi.Filters, sections: list[str]) -> tuple[dict, dict[str, pd.DataFrame], dict]:
    ms = kpi.compute_with_comparison(wb.frames, wb.fact, flt, wb.targets)
    sheets: dict[str, pd.DataFrame | None] = {}
    if "KPI" in sections:
        sheets["KPI"] = metrics_frame(ms)
    if wb.fact is not None:
        if "Cost-to-Serve(운송사)" in sections:
            sheets["CTS_운송사"] = kpi.by_dimension(wb.fact, flt, "carrier")
        if "Cost-to-Serve(배송지)" in sections:
            sheets["CTS_배송지"] = kpi.by_dimension(wb.fact, flt, "store_id")
        if "지연 배송" in sections:
            sheets["지연배송"] = kpi.exceptions(wb.fact, flt, wb.targets).get("late")
        if "경유가 민감도" in sections:
            r = cost.diesel_sensitivity(wb.fact, flt, [5, 10, 20], wb.frames.get("fuel_prices"), wb.external_diesel(), by="carrier")
            sheets["경유가민감도"] = pd.DataFrame(r["rows"])
            sheets["경유가민감도_운송사"] = r.get("by")
            sheets["경유가민감도_가정"] = pd.DataFrame({"가정": r["assumptions"]})
    if "재고 보충" in sections and "inventory" in wb.frames:
        rr = inventory.replenishment(wb.frames)
        if rr["status"] == "ok":
            sheets["재고보충"] = rr["table"]
    if "외부 위험(영업소)" in sections and wb.ext.units is not None:
        sheets["외부_영업소위험"] = wb.ext.units[["unitCode", "unitName", "routeName", "vulnerability_score",
                                              "vulnerability_grade", "lisa_cluster", "local_p_value"]]
    if "외부 데이터 감사" in sections:
        sheets["외부_데이터감사"] = pd.DataFrame(wb.ext.findings)
        sheets["외부_출처"] = provenance_frame(wb.ext.provenance)
    sheets["데이터버전"] = pd.DataFrame([{"entity": k, **v} for k, v in wb.versions.items()])
    missing = [f"{m.label}: {m.reason}" for m in ms.values() if not m.ok]
    meta = {"워크스페이스": wb.ctx.workspace_id, "생성자": wb.ctx.user_id, "필터": flt.describe(),
            "DEMO(가상) 데이터": "예 — 실제 성과 아님" if wb.is_demo else "아니오",
            "데이터 버전": ", ".join(f"{k} v{v['version']}({v['uploaded_at'][:10]})" for k, v in wb.versions.items()) or "없음",
            "계산 불가 지표": " / ".join(missing) or "없음",
            "외부 데이터 주의": "고속도로·전국 유가 지표는 기업 실적이 아님. 유가 예측은 과거 기간이며 재학습하지 않음."}
    return meta, {k: v for k, v in sheets.items() if v is not None}, ms


def report_excel(wb: Workbench, flt: kpi.Filters, sections: list[str]) -> bytes:
    meta, sheets, _ = build_report(wb, flt, sections)
    return excel_report(meta, sheets)


def report_html(wb: Workbench, flt: kpi.Filters, sections: list[str]) -> str:
    meta, sheets, ms = build_report(wb, flt, sections)
    secs = [("범위", flt.describe())]
    if "경유가민감도" in sheets:
        rows = sheets["경유가민감도"].to_dict(orient="records")
        secs.append(("경유가 민감도 (단순 가정 기반 추정)", "\n".join(
            f"경유가 {r['diesel_pct']:+g}% → 연료비 {r['fuel_cost_delta']:,.0f}원"
            + (f" (총 운송비 대비 {r['total_cost_delta_pct']:+.2f}%)" if r.get("total_cost_delta_pct") is not None else "")
            for r in rows)))
    warn = [f["title"] + ": " + f["detail"] for f in wb.ext.findings if f["level"] in ("warn", "error")]
    if warn:
        secs.append(("외부 위험 데이터 주의사항", "\n".join(warn)))
    return html_summary("경영진 요약 리포트", meta, ms, secs, {"운송사별 Cost-to-Serve": sheets.get("CTS_운송사")},
                        demo=wb.is_demo)


def report_preview(wb: Workbench, flt: kpi.Filters, sections: list[str]) -> list[dict]:
    _, sheets, _ = build_report(wb, flt, sections)
    return [{"sheet": k, "rows": int(len(v))} for k, v in sheets.items()]


def current_alerts(wb: Workbench, flt: kpi.Filters) -> list[dict]:
    ms = kpi.compute_with_comparison(wb.frames, wb.fact, flt, wb.targets)
    inv = inventory.replenishment(wb.frames) if "inventory" in wb.frames else None
    return alerts.evaluate(ms, wb.rules, wb.versions, inv, period_days=flt.days)


def system_status(wb: Workbench) -> list[dict]:
    db = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    return [
        {"item": "데이터베이스", "value": db.replace("sqlite:///", "SQLite · ")},
        {"item": "AI Copilot", "value": f"OpenAI {OPENAI_MODEL}" if openai_api_key() else "규칙 기반 모드 (API 키 미설정)"},
        {"item": "외부 위험 데이터", "value": f"{len(wb.ext.provenance)}개 로드 · 누락 {len(wb.ext.missing)}"},
        {"item": "접근 제어", "value": "공용 접근 코드" if access_code() else "공개 (로그인 없음)"},
        {"item": "이메일·외부 발송", "value": "미구현 (의도적으로 비활성)"},
        {"item": "ERP/WMS/TMS 연동", "value": "미구현 (인터페이스만)"},
        {"item": "배포 환경", "value": "Railway" if os.environ.get("RAILWAY_ENVIRONMENT") else "로컬"},
    ]


def permissions_table() -> list[dict]:
    return [{"permission": p, "min_role": r, "min_role_label": ROLE_LABEL[r]} for p, r in PERMISSIONS.items()]
