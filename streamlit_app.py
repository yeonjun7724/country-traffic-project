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


def _gate() -> bool:
    """LOGISRISK_ACCESS_CODE 설정 시 접근 코드 확인 (상수 시간 비교, 5회 실패 시 세션 잠금)."""
    import hmac

    from logisrisk.config import access_code
    code = access_code()
    if not code or st.session_state.get("_authed"):
        return True
    fails = st.session_state.get("_auth_fail", 0)
    st.markdown("<div class='lr-title' style='margin-top:12vh'>LogisRisk Enterprise</div>"
                "<div class='lr-sub'>접근 코드가 필요한 배포 환경입니다.</div>", unsafe_allow_html=True)
    if fails >= 5:
        st.error("시도 횟수를 초과했습니다. 브라우저를 새로 열어 다시 시도하세요.")
        return False
    with st.form("gate"):
        v = st.text_input("접근 코드", type="password")
        if st.form_submit_button("입장"):
            if hmac.compare_digest(v.encode(), code.encode()):
                st.session_state["_authed"] = True
                st.rerun()
            st.session_state["_auth_fail"] = fails + 1
            st.error("접근 코드가 올바르지 않습니다.")
    return False


def main():
    st.session_state.setdefault("theme_mode", "light")
    st.markdown(theme.css(C.mode()), unsafe_allow_html=True)
    C.inject_secrets_to_env()
    if not _gate():
        st.stop()
    pages = nav.build()
    store = C.get_store()
    C.ensure_demo()  # 데이터 버전이 바뀌므로 Workbench 캐시는 자동 갱신
    uid = st.session_state.setdefault("user_id", "local")
    with st.sidebar:
        st.markdown("<div class='lr-brand'><div class='lr-brand-mark'>LR</div><div><div class='lr-brand-name'>LogisRisk</div>"
                    "<div class='lr-brand-sub'>Enterprise · Control Tower</div></div></div>", unsafe_allow_html=True)
        wss = store.workspaces_for(uid)
        ids = [w["id"] for w in wss]
        from logisrisk.config import default_workspace
        cur = st.session_state.get("workspace_id", default_workspace())
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
