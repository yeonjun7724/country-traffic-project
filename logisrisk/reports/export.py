"""Excel 리포트 · 인쇄용(브라우저 → PDF 저장) HTML 요약 리포트.

모든 리포트에 기준일·필터·데이터 버전·지표 정의·결측/경고·DEMO 여부를 포함한다.
"""
from __future__ import annotations

import html
import io
from datetime import datetime

import pandas as pd

from .. import CALC_VERSION, __version__
from ..data.validation import neutralize_formulas
from ..provenance import KIND_LABEL, Metric


def _meta_frame(meta: dict) -> pd.DataFrame:
    rows = [("생성 시각", datetime.now().isoformat(timespec="seconds")), ("플랫폼 버전", __version__),
            ("계산 로직 버전", CALC_VERSION)]
    for k, v in meta.items():
        rows.append((k, v if isinstance(v, str) else str(v)))
    return pd.DataFrame(rows, columns=["항목", "값"])


def metrics_frame(metrics: dict[str, Metric]) -> pd.DataFrame:
    rows = []
    for m in metrics.values():
        rows.append({"지표": m.label, "값": m.value if m.ok else None, "단위": m.unit,
                     "상태": "정상" if m.ok else "계산 불가", "사유": m.reason, "정의": m.definition,
                     "산식": m.formula, "분자": m.numerator, "분모": m.denominator, "표본수": m.n,
                     "기간": m.period, "직전기간": m.previous, "변화율(%)": m.delta_pct, "목표": m.target,
                     "데이터 성격": KIND_LABEL.get(m.kind, m.kind), "경고": " / ".join(m.warnings)})
    return pd.DataFrame(rows)


def csv_bytes(df: pd.DataFrame) -> bytes:
    """다운로드용 CSV (UTF-8 BOM · 수식 주입 방지)."""
    return neutralize_formulas(df).to_csv(index=False).encode("utf-8-sig")


def _clean_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    x = neutralize_formulas(df)
    for c in x.columns:
        if isinstance(x[c].dtype, pd.DatetimeTZDtype):
            x[c] = x[c].dt.tz_localize(None)
        if x[c].dtype == object:
            x[c] = x[c].map(lambda v: str(v) if isinstance(v, (dict, list)) else v)
    return x


def excel_report(meta: dict, sheets: dict[str, pd.DataFrame]) -> bytes:
    """meta → '00_정보' 시트, sheets → 각 시트 (시트명 31자 제한)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        _meta_frame(meta).to_excel(xw, sheet_name="00_정보", index=False)
        used = {"00_정보"}
        for name, df in sheets.items():
            if df is None:
                continue
            sn = name[:31]
            i = 2
            while sn in used:
                sn = f"{name[:28]}_{i}"
                i += 1
            used.add(sn)
            _clean_for_excel(df).to_excel(xw, sheet_name=sn, index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                w = max((len(str(c.value)) if c.value is not None else 0) for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(60, max(10, w + 2))
            ws.freeze_panes = "A2"
    return buf.getvalue()


def html_summary(title: str, meta: dict, metrics: dict[str, Metric], sections: list[tuple[str, str]],
                 tables: dict[str, pd.DataFrame] | None = None, demo: bool = False) -> str:
    """경영진 요약 — 브라우저 인쇄(Ctrl+P) → 'PDF로 저장' 으로 PDF 생성."""
    e = html.escape

    def fmt(m: Metric) -> str:
        if not m.ok:
            return f"<span class='nc'>계산 불가</span><div class='why'>{e(m.reason)}</div>"
        v = m.value
        s = f"{v:.1%}" if m.unit == "%" else f"{v:,.0f} {e(m.unit)}" if abs(v) >= 100 else f"{v:,.2f} {e(m.unit)}"
        d = m.delta_pct
        return s + (f"<div class='why'>직전기간 대비 {d:+.1f}%</div>" if d is not None else "")

    cards = "".join(f"<div class='card'><div class='lbl'>{e(m.label)}</div><div class='val'>{fmt(m)}</div>"
                    f"<div class='def'>{e(m.formula)}</div></div>" for m in metrics.values())
    meta_rows = "".join(f"<tr><th>{e(str(k))}</th><td>{e(str(v))}</td></tr>" for k, v in
                        {"생성 시각": datetime.now().isoformat(timespec='seconds'), "계산 로직 버전": CALC_VERSION, **meta}.items())
    secs = "".join(f"<h2>{e(h)}</h2><p>{e(b).replace(chr(10), '<br>')}</p>" for h, b in sections)
    tbls = ""
    for name, df in (tables or {}).items():
        if df is not None and len(df):
            tbls += f"<h2>{e(name)}</h2>" + df.head(30).to_html(index=False, border=0, classes="t", na_rep="—",
                                                                 float_format=lambda v: f"{v:,.2f}")
    banner = ("<div class='demo'>DEMO(가상) 데이터로 생성된 리포트입니다. 실제 운영 실적이 아닙니다.</div>" if demo else "")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{e(title)}</title>
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" rel="stylesheet">
<style>
body{{font-family:Pretendard,system-ui,sans-serif;color:#0f172a;margin:32px;max-width:1000px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:15px;margin:24px 0 8px;border-bottom:1px solid #e2e8f0;padding-bottom:4px}}
.sub{{color:#64748b;font-size:12px}} .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}}
.card{{border:1px solid #e2e8f0;border-radius:8px;padding:10px}} .lbl{{font-size:11px;color:#64748b}}
.val{{font-size:18px;font-weight:700;margin:4px 0}} .def,.why{{font-size:10px;color:#64748b;font-weight:400}}
.nc{{color:#b45309;font-size:14px}} table{{border-collapse:collapse;width:100%;font-size:11px}}
th,td{{text-align:left;padding:4px 6px;border-bottom:1px solid #f1f5f9;vertical-align:top}} th{{color:#475569;width:200px}}
.t th{{background:#f8fafc;width:auto}} .demo{{background:#fef3c7;border:1px solid #f59e0b;padding:8px 12px;border-radius:6px;margin:12px 0;font-weight:600}}
@media print{{body{{margin:12mm}} .grid{{grid-template-columns:repeat(4,1fr)}}}}
</style></head><body>
<h1>{e(title)}</h1><div class="sub">LogisRisk Enterprise · 인쇄(Ctrl/Cmd+P) → 'PDF로 저장'</div>{banner}
<div class="grid">{cards}</div>{secs}{tbls}
<h2>데이터 기준·출처</h2><table>{meta_rows}</table>
</body></html>"""
