# CLAUDE.md

이 저장소의 작업 규칙은 [AGENTS.md](AGENTS.md) 를 따른다. 아래는 Claude Code 용 추가 지침.

## 실행 환경 (이 PC)
- 기본 `python` 은 Windows Store 스텁이라 실행되지 않는다. anaconda(`C:/Users/User/anaconda3`)에는 FastAPI 가 없다.
- **프로젝트 인터프리터: `.venv/Scripts/python.exe`** (Python 3.12, `requirements-dev.txt` 전체 — streamlit 1.45.1·FastAPI·pandas 2.3·pytest).
  없으면 `py -3.12 -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements-dev.txt` 로 만든다 (`.gitignore` 됨).
- `py -3.12` (시스템)는 pandas 3.0 환경 (FastAPI·streamlit 없음) — core 테스트의 pandas 3 호환성 확인용:
  `py -3.12 -m pytest -q --ignore=tests/test_ui_smoke.py --ignore=tests/test_api.py --ignore=tests/test_api_screens.py`
- 한글 출력이 깨지면 `PYTHONIOENCODING=utf-8`.
- 로컬 API 호출·측정은 `127.0.0.1` 을 쓴다. `localhost` 는 IPv6 폴백 때문에 요청마다 ~2초가 더해진다 (브라우저는 영향 없음).
- Node 24 / npm 11. `frontend/node_modules` 가 없으면 `npm ci`. E2E 는 설치된 Edge 사용(`channel: msedge`, 브라우저 다운로드 불필요):
  `cd frontend && npm run build` → (루트) `.venv/Scripts/python.exe -m uvicorn backend.main:app --port 8600` → `npx playwright test`.
- 성능 측정: `.venv/Scripts/python.exe scripts/bench.py` (API·대용량 계산 시간). 기준값과 목표는 `docs/IMPROVEMENT_PLAN.md`.
- 이 PC 에는 Docker 가 없다 — `Dockerfile.web` 은 `requirements-api.txt` 만 설치한 venv 로 기동 검증.

## 작업 방식
- 변경은 모듈 단위로. `app.py`(레거시)와 `templates/index.html`(포트폴리오)은 수정하지 않는다.
- 계산은 `logisrisk/analytics`, 화면은 `logisrisk/ui/pages` — UI 에 계산 로직을 넣지 않는다.
- Streamlit UI 변경 후 `tests/test_ui_smoke.py`, Next.js 변경 후 Playwright 스크린샷(`frontend/e2e-screens/`)을 직접 본다.
- 커밋·푸시는 사용자가 요청할 때만. Railway 는 push 시 배포되므로 push 전 반드시 확인.
