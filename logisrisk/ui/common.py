"""Streamlit 공통: 세션 컨텍스트·캐시·글로벌 필터·UI 컴포넌트."""
from __future__ import annotations

import html
import math
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from ..analytics import kpi
from ..data.external import load_external
from ..data.store import Store
from ..provenance import KIND_LABEL, Metric
from ..security import ROLE_LABEL, PermissionDenied
from ..services import Workbench
from . import theme

E = html.escape


# ── 리소스 ─────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_store() -> Store:
    return Store()


@st.cache_resource(ttl=3600, show_spinner="외부 위험 데이터 로딩·감사 중…")
def get_external():
    return load_external()


def inject_secrets_to_env():
    """Streamlit secrets → 환경변수 (core 는 env 만 읽는다). 값은 로그/화면에 노출하지 않는다."""
    if os.environ.get("OPENAI_API_KEY"):
        return
    try:
        k = st.secrets.get("OPENAI_API_KEY")
        if k:
            os.environ["OPENAI_API_KEY"] = str(k)
    except Exception:
        pass


def mode() -> str:
    return st.session_state.get("theme_mode", "light")


def ctx():
    store = get_store()
    uid = st.session_state.get("user_id", "local")
    wid = st.session_state.get("workspace_id", "default")
    try:
        return store.context_for(uid, wid)
    except PermissionDenied:
        st.session_state["workspace_id"] = "default"
        return store.context_for(uid, "default")


def workbench() -> Workbench:
    """활성 데이터셋 버전이 바뀔 때만 다시 로드 (세션 캐시)."""
    store, c = get_store(), ctx()
    versions = store.data_versions(c)
    key = (c.workspace_id, c.role, tuple(sorted((k, v["dataset_id"]) for k, v in versions.items())),
           st.session_state.get("settings_rev", 0))
    cached = st.session_state.get("_wb")
    if cached and cached[0] == key:
        return cached[1]
    wb = Workbench.load(store, c, get_external())
    st.session_state["_wb"] = (key, wb)
    return wb


def invalidate():
    st.session_state.pop("_wb", None)


# ── 글로벌 필터 (사이드바) ─────────────────────────────────────────────────
def global_filters(wb: Workbench) -> kpi.Filters:
    flt = kpi.Filters()
    b = wb.date_bounds()
    with st.sidebar:
        st.markdown("<div style='font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#64748b;"
                    "margin:6px 0 2px'>글로벌 필터</div>", unsafe_allow_html=True)
        if b is None:
            st.caption("운영 데이터 업로드 후 기간·센터 필터가 활성화됩니다.")
            return flt
        lo, hi = b[0].date(), b[1].date()
        default = st.session_state.get("flt_range")
        if not default or default[0] < lo or default[1] > hi:
            default = (max(lo, (b[1] - pd.Timedelta(days=29)).date()), hi)
        rng = st.date_input("기간(출고일)", value=default, min_value=lo, max_value=hi, key="flt_range_w",
                            format="YYYY-MM-DD")
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            st.session_state["flt_range"] = tuple(rng)
            flt.start, flt.end = rng
        else:
            flt.start, flt.end = default
        flt.warehouses = st.multiselect("센터", wb.options("warehouse_id"), key="flt_wh")
        flt.regions = st.multiselect("권역", wb.options("region"), key="flt_region")
        flt.carriers = st.multiselect("운송사", wb.options("carrier"), key="flt_carrier")
        with st.expander("추가 필터"):
            flt.vehicles = st.multiselect("차량", wb.options("vehicle_id"), key="flt_vehicle")
            flt.categories = st.multiselect("상품군", wb.options("category"), key="flt_cat")
            flt.stores = st.multiselect("배송지", wb.options("store_id"), key="flt_store")
    return flt


# ── 컴포넌트 ───────────────────────────────────────────────────────────────
def badge(text: str, tone: str = "neutral") -> str:
    return f"<span class='lr-badge {tone}'>{E(text)}</span>"


def kind_badge(kind: str) -> str:
    return badge(KIND_LABEL.get(kind, kind), theme.KIND_TONE.get(kind, "neutral"))


def header(eyebrow: str, title: str, sub: str = "", wb: Workbench | None = None, extra_badges: list[str] | None = None):
    meta = list(extra_badges or [])
    if wb is not None:
        if wb.is_demo:
            meta.insert(0, badge("DEMO 데이터", "bad"))
        if wb.versions:
            last = max(v["uploaded_at"] for v in wb.versions.values())
            meta.append(badge(f"데이터 갱신 {last[:16]}", "neutral"))
        else:
            meta.append(badge("운영 데이터 없음", "warn"))
        meta.append(badge(f"{ROLE_LABEL.get(wb.ctx.role, wb.ctx.role)}", "info"))
    meta.append(badge(f"조회 {datetime.now():%Y-%m-%d %H:%M}", "neutral"))
    st.markdown(f"""<div class="lr-top"><div><div class="lr-eyebrow">{E(eyebrow)}</div>
<div class="lr-title">{E(title)}</div><div class="lr-sub">{E(sub)}</div></div>
<div class="lr-meta">{''.join(meta)}</div></div>""", unsafe_allow_html=True)
    if wb is not None and wb.is_demo:
        st.markdown("<div class='lr-demo'>DEMO 워크스페이스 — 화면의 모든 운영 수치는 테스트용 가상 데이터이며 실제 성과가 아닙니다.</div>",
                    unsafe_allow_html=True)


def callout(text: str, tone: str = "info"):
    st.markdown(f"<div class='lr-callout {tone}'>{text}</div>", unsafe_allow_html=True)


def empty(title: str, desc: str, page: str | None = None, label: str = "Data Hub 로 이동"):
    st.markdown(f"<div class='lr-empty'><div class='lr-empty-t'>{E(title)}</div><div class='lr-empty-d'>{E(desc)}</div></div>",
                unsafe_allow_html=True)
    if page:
        st.page_link(page, label=label, icon=":material/upload_file:")


def section(title: str, sub: str = ""):
    st.markdown(f"<div class='lr-sec'>{E(title)} <small>{E(sub)}</small></div>", unsafe_allow_html=True)


def fmt_value(v: float | None, unit: str) -> str:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "—"
    if unit == "%":
        return f"{v:.1%}"
    if unit == "원" and abs(v) >= 1e8:
        return f"{v / 1e8:,.2f}억원"
    if unit == "원" and abs(v) >= 1e4:
        return f"{v / 1e4:,.0f}만원"
    if abs(v) >= 100:
        return f"{v:,.0f} {unit}".strip()
    return f"{v:,.2f} {unit}".strip()


def kpi_card(m: Metric, key: str):
    if not m.ok:
        st.markdown(f"""<div class="lr-kpi"><div class="lr-kpi-lbl">{E(m.label)}</div>
<div class="lr-kpi-val nc">계산 불가</div><div class="lr-kpi-foot">{E(m.reason)}</div></div>""", unsafe_allow_html=True)
    else:
        d = m.delta_pct
        if d is None:
            dtxt = "<span class='lr-flat'>직전기간 없음</span>"
        else:
            good = (d >= 0) == m.higher_is_better
            cls = "lr-flat" if abs(d) < 0.05 else ("lr-up" if good else "lr-down")
            dtxt = f"<span class='{cls}'>{'▲' if d > 0 else '▼' if d < 0 else '■'} {abs(d):.1f}%</span>"
        tgt = ""
        if m.target is not None:
            hit = (m.value >= m.target) if m.higher_is_better else (m.value <= m.target)
            tgt = f"<span class='{'lr-up' if hit else 'lr-down'}'>목표 {fmt_value(m.target, m.unit)}</span>"
        warn = f"<span title='{E(' / '.join(m.warnings))}'>⚠ 경고 {len(m.warnings)}</span>" if m.warnings else ""
        st.markdown(f"""<div class="lr-kpi"><div class="lr-kpi-lbl">{E(m.label)}</div>
<div class="lr-kpi-val">{fmt_value(m.value, m.unit)}</div>
<div class="lr-kpi-foot">{dtxt}{tgt}<span>n={m.n:,}</span>{warn}</div></div>""", unsafe_allow_html=True)
    with st.popover("정의·산식", use_container_width=True):
        st.markdown(f"**{m.label}** · {KIND_LABEL.get(m.kind, m.kind)}")
        st.markdown(f"<div class='lr-def'>{E(m.definition)}<br>산식: <code>{E(m.formula)}</code><br>"
                    f"분자 {fmt_value(m.numerator, '') if m.numerator is not None else '—'} / "
                    f"분모 {fmt_value(m.denominator, '') if m.denominator is not None else '—'}<br>"
                    f"측정기간: {E(m.period)} · 표본 {m.n if m.n is not None else '—'}"
                    + (f"<br>직전기간 값: {fmt_value(m.previous, m.unit)}" if m.previous is not None else "")
                    + "".join(f"<br>⚠ {E(w)}" for w in m.warnings)
                    + (f"<br>계산 불가 사유: {E(m.reason)}" if not m.ok else "") + "</div>", unsafe_allow_html=True)


def kpi_grid(metrics: dict[str, Metric], keys: list[str], cols: int = 4, prefix: str = "k"):
    for i in range(0, len(keys), cols):
        cs = st.columns(cols)
        for c, k in zip(cs, keys[i:i + cols]):
            with c:
                kpi_card(metrics[k], f"{prefix}_{k}")


def can(permission: str) -> bool:
    return ctx().can(permission)


def download_button(label: str, data: bytes | str, file_name: str, mime: str, key: str):
    if not can("data.export"):
        st.button(label + " (권한 필요)", disabled=True, key=key, help="내보내기는 분석가 이상 권한이 필요합니다.")
        return
    if st.download_button(label, data, file_name=file_name, mime=mime, key=key):
        get_store().log(ctx(), "data.export", file_name)


def provenance_table(prov: dict) -> pd.DataFrame:
    rows = []
    for k, p in prov.items():
        rows.append({"데이터": k, "원천": p.source, "성격": KIND_LABEL.get(p.kind, p.kind),
                     "관측기간": f"{p.period_start or ''}~{p.period_end or ''}" if p.period_start else "—",
                     "건수": p.n, "단위": p.unit, "계산 방식": p.method, "파일 갱신": p.version,
                     "경고": " / ".join(p.warnings)})
    return pd.DataFrame(rows)


def format_df(df: pd.DataFrame, pct_cols=(), money_cols=(), num_cols=()) -> pd.DataFrame:
    """표시용 포맷 (원본 수치는 다운로드에서 보존)."""
    x = df.copy()
    for c in pct_cols:
        if c in x:
            x[c] = x[c].map(lambda v: "—" if pd.isna(v) else f"{v:.1%}")
    for c in money_cols:
        if c in x:
            x[c] = x[c].map(lambda v: "—" if pd.isna(v) else f"{v:,.0f}")
    for c in num_cols:
        if c in x:
            x[c] = x[c].map(lambda v: "—" if pd.isna(v) else f"{v:,.1f}")
    return x
