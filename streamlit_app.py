"""LogisRisk Enterprise — 엔트리포인트.

실행:  streamlit run streamlit_app.py
레거시 공모전 대시보드는 그대로 보존:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

st.set_page_config(page_title="LogisRisk Enterprise", page_icon=":material/hub:", layout="wide",
                   initial_sidebar_state="expanded")

from logisrisk.ui import common as C  # noqa: E402
from logisrisk.ui import nav, theme  # noqa: E402


def _search(wb, q: str):
    q = q.strip().lower()
    hits = []
    for ent, cols in (("stores", ["store_id", "name", "region"]), ("skus", ["sku_id", "name", "category"]),
                      ("vehicles", ["vehicle_id", "carrier"]), ("warehouses", ["warehouse_id", "name"]),
                      ("orders", ["order_id"]), ("shipments", ["shipment_id", "order_id"])):
        df = wb.frames.get(ent)
        if df is None:
            continue
        m = pd.Series(False, index=df.index)
        for c in cols:
            m |= df[c].astype(str).str.lower().str.contains(q, regex=False, na=False)
        if m.any():
            hits.append((ent, df[m].head(20)))
    if wb.ext.units is not None:
        u = wb.ext.units
        m = u["unitName"].str.contains(q, na=False) | u["routeName"].str.contains(q, na=False)
        if m.any():
            hits.append(("고속도로 영업소(외부)", u[m][["unitCode", "unitName", "routeName", "vulnerability_score", "lisa_cluster"]].head(20)))
    return hits


@st.dialog("검색 결과", width="large")
def _search_dialog(wb, q):
    hits = _search(wb, q)
    if not hits:
        st.caption(f"'{q}' 에 대한 결과가 없습니다.")
    for ent, df in hits:
        st.markdown(f"**{ent}** · {len(df)}건{' (상위 20)' if len(df) == 20 else ''}")
        st.dataframe(df, hide_index=True, use_container_width=True)


def main():
    st.session_state.setdefault("theme_mode", "light")
    st.markdown(theme.css(C.mode()), unsafe_allow_html=True)
    C.inject_secrets_to_env()
    pages = nav.build()
    store = C.get_store()
    uid = st.session_state.setdefault("user_id", "local")
    with st.sidebar:
        st.markdown("<div class='lr-brand'><div class='lr-brand-mark'>LR</div><div><div class='lr-brand-name'>LogisRisk</div>"
                    "<div class='lr-brand-sub'>Enterprise · Control Tower</div></div></div>", unsafe_allow_html=True)
        wss = store.workspaces_for(uid)
        ids = [w["id"] for w in wss]
        cur = st.session_state.get("workspace_id", "default")
        wid = st.selectbox("워크스페이스", ids, index=ids.index(cur) if cur in ids else 0,
                           format_func=lambda i: next(w["name"] for w in wss if w["id"] == i), key="ws_sel")
        if wid != st.session_state.get("workspace_id"):
            st.session_state["workspace_id"] = wid
            C.invalidate()
    pg = st.navigation(pages, position="sidebar")
    with st.sidebar:
        q = st.text_input("글로벌 검색", placeholder="배송지·SKU·차량·주문·영업소", key="g_search")
        if q and st.session_state.get("_last_q") != q:
            st.session_state["_last_q"] = q
            _search_dialog(C.workbench(), q)
        dark = st.toggle("다크 모드", value=C.mode() == "dark", key="theme_toggle")
        if dark != (C.mode() == "dark"):
            st.session_state["theme_mode"] = "dark" if dark else "light"
            st.rerun()
    pg.run()
    with st.sidebar:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.caption("LogisRisk Enterprise v0.1 · 외부 위험 지표는 기업 실적이 아닙니다.")


main()
