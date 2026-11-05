# CLAUDE.md

이 저장소의 작업 규칙은 [AGENTS.md](AGENTS.md) 를 따른다. 아래는 Claude Code 용 추가 지침.

## 실행 환경 (이 PC)
- 기본 `python` 은 Windows Store 스텁이라 실행되지 않는다.
- streamlit·plotly 가 설치된 인터프리터: `C:/Users/yeonjun/anaconda3/python.exe` (pandas 2.2)
- `py -3.11` 은 pandas 3.0 환경 (streamlit 없음) — core 테스트의 pandas 3 호환성 확인용:
  `py -3.11 -m pytest -q --ignore=tests/test_ui_smoke.py`
- 한글 출력이 깨지면 `PYTHONIOENCODING=utf-8`.
- Node 24 / npm 11. E2E 는 설치된 Edge 사용(`channel: msedge`, 브라우저 다운로드 불필요):
  `cd frontend && npm run build` → (루트) `python -m uvicorn backend.main:app --port 8600` → `npx playwright test`.
- 이 PC 에는 Docker 가 없다 — `Dockerfile.web` 은 `requirements-api.txt` 만 설치한 venv 로 기동 검증.

## 작업 방식
- 변경은 모듈 단위로. `app.py`(레거시)와 `templates/index.html`(포트폴리오)은 수정하지 않는다.
- 계산은 `logisrisk/analytics`, 화면은 `logisrisk/ui/pages` — UI 에 계산 로직을 넣지 않는다.
- Streamlit UI 변경 후 `tests/test_ui_smoke.py`, Next.js 변경 후 Playwright 스크린샷(`frontend/e2e-screens/`)을 직접 본다.
- 커밋·푸시는 사용자가 요청할 때만. Railway 는 push 시 배포되므로 push 전 반드시 확인.
