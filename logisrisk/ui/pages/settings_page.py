"""10 Settings — 워크스페이스 · 역할 · KPI 목표 · AI · 테마 · 감사 로그."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from ...config import DATABASE_URL, OPENAI_MODEL, access_code, local_mode, openai_api_key
from ...security import PERMISSIONS, ROLE_LABEL, ROLES
from .. import common as C


def render():
    wb = C.workbench()
    C.header("10 · Settings", "설정 · 권한 · 감사", "", wb)
    t1, t2, t3, t4 = st.tabs(["KPI 목표", "사용자 · 권한", "시스템", "감사 로그"])
    with t1:
        can = C.can("settings.manage")
        tg = dict(wb.targets)
        c = st.columns(3)
        tg["otif"] = c[0].number_input("OTIF 목표", 0.0, 1.0, float(tg.get("otif") or 0.95), 0.01, disabled=not can)
        tg["late_rate"] = c[1].number_input("지연율 목표(이하)", 0.0, 1.0, float(tg.get("late_rate") or 0.05), 0.01, disabled=not can)
        tg["load_factor"] = c[2].number_input("적재율 목표", 0.0, 1.0, float(tg.get("load_factor") or 0.8), 0.01, disabled=not can)
        c = st.columns(3)
        tg["cost_per_order"] = c[0].number_input("주문당 운송비 목표(원, 0=미설정)", 0.0, 1e9, float(tg.get("cost_per_order") or 0), 1000.0,
                                                 disabled=not can) or None
        tg["max_cost_per_shipment"] = c[1].number_input("배송당 비용 상한(원, 0=미설정·P95 사용)", 0.0, 1e9,
                                                        float(tg.get("max_cost_per_shipment") or 0), 1000.0, disabled=not can) or None
        if can and st.button("목표 저장", type="primary"):
            C.get_store().set_setting(wb.ctx, "targets", tg)
            st.session_state["settings_rev"] = st.session_state.get("settings_rev", 0) + 1
            st.success("저장되었습니다. 다시 열어도 유지됩니다.")
        if not can:
            st.caption("목표 변경은 관리자 권한이 필요합니다.")
    with t2:
        C.callout("현재 <b>인증 미구성 — 로컬 단일 사용자 모드</b>입니다. 역할 기반 권한은 서비스·AI 도구 계층에서 강제되며, "
                  "아래에서 역할을 낮춰 화면별 접근 제한을 확인할 수 있습니다. 실제 다중 사용자 운영에는 SSO/OIDC 연동(P2)이 필요합니다.", "warn")
        cur = wb.ctx.role
        st.markdown(C.badge("접근 코드 사용 중", "ok") if access_code() else C.badge("접근 코드 미설정 — 공개 배포 시 LOGISRISK_ACCESS_CODE 설정 필요", "bad"),
                    unsafe_allow_html=True)
        if not local_mode():
            st.caption(f"현재 역할: {ROLE_LABEL[cur]}. 역할 전환 테스트 기능은 로컬 모드(LOGISRISK_LOCAL_MODE=1)에서만 제공됩니다.")
        sim = st.selectbox("세션 역할 (로컬 모드 전용 테스트 기능)", ROLES, index=ROLES.index(cur),
                           format_func=lambda r: ROLE_LABEL[r], key="set_role", disabled=not local_mode())
        if local_mode() and st.button("역할 적용"):
            store = C.get_store()
            uid = f"local-{sim}"
            store.add_user(uid, f"로컬 {ROLE_LABEL[sim]}")
            for w in ("default", "demo"):
                store.grant(uid, w, sim)
            st.session_state["user_id"] = "local" if sim == "admin" else uid
            C.invalidate()
            st.rerun()
        st.dataframe(pd.DataFrame([{"권한": p, "최소 역할": ROLE_LABEL[r]} for p, r in PERMISSIONS.items()]),
                     hide_index=True, use_container_width=True)
    with t3:
        key = openai_api_key()
        st.dataframe(pd.DataFrame([
            ("데이터베이스", DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL),
            ("OpenAI API 키", "설정됨" if key else "미설정 (규칙 기반 모드)"), ("OpenAI 모델", OPENAI_MODEL),
            ("외부 위험 데이터", f"{len(wb.ext.provenance)}개 로드 · 누락 {len(wb.ext.missing)}"),
            ("이메일·외부 발송", "미구현 (의도적으로 비활성)"), ("ERP/WMS/TMS 연동", "미구현 (인터페이스만)"),
            ("배포 환경", "Railway" if os.environ.get("RAILWAY_ENVIRONMENT") else "로컬"),
        ], columns=["항목", "상태"]), hide_index=True, use_container_width=True)
        st.caption("API 키는 환경변수 OPENAI_API_KEY 또는 .streamlit/secrets.toml 로만 설정하며 화면·로그에 노출하지 않습니다.")
    with t4:
        if not C.can("audit.read"):
            st.caption("감사 로그 조회는 운영 관리자 이상 권한이 필요합니다.")
        else:
            lg = C.get_store().audit_log(wb.ctx)
            st.dataframe(lg, hide_index=True, use_container_width=True, height=420)
