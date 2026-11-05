"""07 AI Copilot — 도구 호출 기반 분석 에이전트 (읽기 전용) + 규칙 기반 폴백."""
from __future__ import annotations

import streamlit as st

from ...config import AI_MAX_CALLS_PER_SESSION, OPENAI_MODEL, openai_api_key
from ...copilot import agent
from ...copilot.tools import TOOLS
from .. import common as C

EXAMPLES = ["지난달 배송비가 가장 많이 증가한 거래처는?", "경유가격이 15% 오르면 차량별 운송비는 얼마나 변하나?",
            "배송 지연이 잦은 권역을 보여줘", "현재 차량으로 내일 배송 주문을 처리할 수 있나?",
            "센터 WH-A가 중단되면 대체 배송 가능 거점은?", "재고 부족 가능성이 높은 SKU를 보여줘",
            "고속도로 취약 영업소 상위 10개", "기준 이벤트 전후 화물 교통량 변화"]


def render():
    wb = C.workbench()
    C.inject_secrets_to_env()
    has_key = bool(openai_api_key())
    C.header("07 · AI Copilot", "분석 Copilot", "계산 도구 결과만 인용 · 읽기 전용 · 권한 범위 내 데이터만 조회", wb,
             [C.badge(f"LLM {OPENAI_MODEL}" if has_key else "규칙 기반 모드 (API 키 없음)", "ok" if has_key else "warn")])
    if not C.can("ai.use"):
        C.callout("AI Copilot 은 분석가 이상 권한이 필요합니다.", "warn")
        return
    hkey = f"chat_{wb.ctx.workspace_id}"
    hist = st.session_state.setdefault(hkey, [])
    used = st.session_state.setdefault("ai_calls", 0)
    if not hist and wb.has_ops_data and not st.session_state.get(f"{hkey}_seeded"):
        # 첫 방문: 예시 질문 1개를 규칙 기반 도구로 실제 계산해 보여준다 (LLM 호출 없음)
        st.session_state[f"{hkey}_seeded"] = True
        q0 = EXAMPLES[2]
        r0 = agent.fallback_answer(wb, q0, "예시")
        hist += [{"role": "user", "content": q0},
                 {"role": "assistant", "content": r0.answer,
                  "meta": {"mode": r0.mode, "notice": "예시 대화 · 규칙 기반으로 계산", "steps": r0.steps, "results": r0.tool_results}}]
    with st.sidebar:
        st.caption(f"이번 세션 LLM 호출 {used}/{AI_MAX_CALLS_PER_SESSION}")
        if st.button("대화 초기화", key="cp_clear"):
            st.session_state[hkey] = []
            st.rerun()
    if len(hist) <= 2:
        C.callout("Copilot 은 아래 도구로 계산한 결과만 근거로 답합니다. 데이터 변경·배차 확정·외부 발송은 할 수 없습니다. "
                  + ("" if has_key else "현재 <b>OPENAI_API_KEY 가 없어 규칙 기반 모드</b>로 동작합니다 (지원 질문 유형 제한)."), "info")
        cols = st.columns(4)
        for i, q in enumerate(EXAMPLES):
            if cols[i % 4].button(q, key=f"ex_{i}", use_container_width=True):
                st.session_state["cp_pending"] = q
                st.rerun()
        with st.expander(f"사용 가능한 도구 {len(TOOLS)}개"):
            for k, (_, d, _) in TOOLS.items():
                st.markdown(f"- `{k}` — {d}")
    for m in hist:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("meta"):
                _meta(m["meta"])
    q = st.chat_input("질문을 입력하세요 (예: 경유가 10% 상승 시 운송사별 연료비)")
    q = q or st.session_state.pop("cp_pending", None)
    if not q:
        return
    hist.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant"):
        with st.spinner("도구 실행·분석 중…"):
            r = agent.run(wb, q, [{"role": h["role"], "content": h["content"]} for h in hist[:-1]],
                          calls_used=used, max_calls=AI_MAX_CALLS_PER_SESSION)
        st.session_state["ai_calls"] = used + r.llm_calls
        st.markdown(r.answer)
        meta = {"mode": r.mode, "notice": r.notice, "steps": r.steps, "results": r.tool_results}
        _meta(meta)
    hist.append({"role": "assistant", "content": r.answer, "meta": meta})


def _meta(meta):
    lab = {"llm": "LLM + 도구", "fallback": "규칙 기반", "unsupported": "지원 불가", "error": "오류"}.get(meta["mode"], meta["mode"])
    st.markdown(C.badge(lab, "ok" if meta["mode"] == "llm" else "warn") + (" " + C.badge(meta["notice"], "neutral") if meta.get("notice") else ""),
                unsafe_allow_html=True)
    if meta.get("results"):
        with st.expander("근거: 도구 호출 결과 (" + ", ".join(s["tool"] for s in meta["steps"]) + ")"):
            for res in meta["results"]:
                st.json(res, expanded=False)
