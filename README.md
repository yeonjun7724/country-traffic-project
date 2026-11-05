# LogisRisk Enterprise — Logistics & Distribution Intelligence Platform

물류 담당자가 **자신의 주문·배송·차량·거점·재고 데이터를 업로드**해 실제 운송비·서비스 수준을 분석하고,
배송 계획 대안과 유가·수요·센터 중단 시나리오를 비교해 보고서로 내보내는 운영 분석 플랫폼입니다.
기존 공모전 분석(고속도로 영업소 취약성·유가 예측·교통량)은 **외부 위험 지표**로 통합되어 있습니다.

> 운영 데이터가 없으면 KPI 는 '계산 불가'로 표시되며, 가상의 성과를 보여주지 않습니다.
> 체험은 사이드바의 **DEMO 워크스페이스**(가상 데이터, 모든 화면에 DEMO 표시)에서 할 수 있습니다.

## 화면
| | 화면 | 내용 |
|---|---|---|
| 01 | Control Tower | KPI 9종(정의·산식·분모·직전기간 비교·목표), 알림, 지도↔표 선택 동기화, 지연·비용초과 원장 드릴다운 |
| 02 | Network Intelligence | 영업소 위험(외부)·센터·배송지·배송밀도 레이어, LISA, 가중치 재계산(시나리오 ID), 센터 주변 고위험 영업소 |
| 03 | Transportation | Cost-to-Serve, 연료비·연비, CVRP 휴리스틱 배송 계획 대안 vs 현행, 승인 요청 저장 |
| 04 | Demand & Inventory | 안전재고·재주문점·보충 추천(근거), 수요예측 모델 백테스트(WAPE/MAE/Bias/MAPE) |
| 05 | Fuel & Risk | 경유가 민감도(기업 연료비), 외부 유가·예측(재가중, 최신성 경고), 기준 이벤트 전후 교통량, 데이터 감사 |
| 06 | Scenario Lab | Baseline/A/B 비교, 원인 기여도, 민감도, 센터 중단, 저장·복제·승인·Excel |
| 07 | AI Copilot | OpenAI 도구 호출(읽기 전용) + 키 없음·오류 시 규칙 기반 폴백, 근거 도구 결과 표시 |
| 08 | Data Hub | CSV/Excel 업로드, 자동 컬럼 매핑, 검증·오류 행 다운로드, 원자적 저장, 버전·롤백, 품질 |
| 09 | Reports & Alerts | Excel 리포트, 경영진 요약(HTML→PDF 인쇄), 알림 규칙, 조치 워크플로 |
| 10 | Settings | KPI 목표, 역할·권한, 시스템 상태, 감사 로그 |

## 실행

### 신규 웹 앱 (Next.js + FastAPI) — 전환 중 (P0: Control Tower · Data Hub)
```bash
pip install -r requirements-api.txt
cd frontend && npm ci && npm run build && cd ..        # 정적 빌드 → frontend/out
python -m uvicorn backend.main:app --port 8000          # API + 화면을 한 서버에서 → http://localhost:8000
```
개발 모드(핫 리로드): API 를 `LOGISRISK_CORS_ORIGINS=http://localhost:3000` 로 띄우고
`cd frontend && NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev`.
API 문서: `/api/docs`. 나머지 8개 화면은 새 UI 에서 '준비 중'으로 표시되며 기존 Streamlit 앱에서 사용합니다.

### 기존 Streamlit 앱 (기능 동등성 확인 전까지 병행 유지)
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py      # 10개 화면 전체
streamlit run app.py                # 레거시 공모전 대시보드 (보존)
```
- 선택: `OPENAI_API_KEY` 환경변수 또는 `.streamlit/secrets.toml` (`.env.example` 참고). 없으면 규칙 기반 모드.
- 데이터는 `data/logisrisk.db`(SQLite)에 저장됩니다. `DATABASE_URL` 로 PostgreSQL 사용 가능.

## 빠른 시작 (DEMO)
앱을 처음 띄우면 **DEMO 워크스페이스**가 샘플 데이터로 자동으로 채워진 상태로 열립니다 (최초 1회, 약 20초).
- 운영 데이터: `fixtures/demo` 가상 데이터 (센터 3·배송지 62·SKU 40·차량 20·92일)
- 예시 작업물: 비용 시나리오 3건(승인·초안), 센터 중단 분석, 배송계획 제안(승인 대기), 알림 기반 조치 항목, Copilot 예시 대화
- 모든 수치는 샘플 데이터로 실제 엔진을 돌려 계산한 값이며, 화면 상단에 '샘플 데이터' 배지가 표시됩니다.
- 실데이터는 사이드바에서 **내 워크스페이스**로 전환해 업로드합니다 (샘플과 분리).
- 끄기: `LOGISRISK_AUTO_DEMO=0`, 첫 화면을 내 워크스페이스로: `LOGISRISK_DEFAULT_WORKSPACE=default`

## 내 데이터로 시작
08 Data Hub → 템플릿·스키마 탭에서 양식 확인 → 센터 → 배송지 → SKU → 차량 → 주문 → 주문상세 → 배송 순서로 업로드.
한글/영문 컬럼명은 자동 매핑되며, 오류 행은 행번호·사유와 함께 다운로드할 수 있습니다.

## 테스트
```bash
pip install -r requirements-dev.txt
python -m pytest -q                      # 계산·검증·저장·권한·API(141)
cd frontend && npm run typecheck && npx eslint . && npm test     # 타입·lint·단위
npm run build && (cd .. && python -m uvicorn backend.main:app --port 8600 &) && npm run test:e2e
# E2E: 10개 화면 × 샘플/빈 워크스페이스 × 라이트/다크 렌더링 + 클릭 흐름 7종, 스크린샷은 frontend/e2e-screens/
```
검증·KPI(손계산)·운송비·경로 제약·재고 공식·외부 산출물 재현성·권한/워크스페이스 격리·원자적 롤백·
AI 폴백(키 없음/쿼터/Rate limit/인증/타임아웃)·인수 시나리오 E2E·10개 화면 렌더링 스모크.

## 배포 (Railway)
- 기존 서비스: `railway.toml` → `streamlit_app.py` (변경 없음)
- 신규 웹 서비스: 같은 저장소로 **새 서비스**를 만들고 Config file path 를 `/railway.web.toml` 로 지정
  (`Dockerfile.web`: Next.js 빌드 + FastAPI, 헬스체크 `/api/health`). Variables 에 `LOGISRISK_SESSION_SECRET` 고정값 필요.

배포 전 필수 (두 서비스 공통):
- **`LOGISRISK_ACCESS_CODE` 설정** — 미설정 시 URL 을 아는 누구나 관리자 권한으로 접근합니다.
- 업로드 데이터 유지: Volume(`LOGISRISK_DATA_DIR=/data`) 또는 PostgreSQL.

상세: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 데이터 원칙
관측·모델 예측·시뮬레이션·가정 기반 추정·DEMO 를 구분 표기하고, 외부 지표(고속도로·전국 유가)를 기업 실적으로
사용하지 않습니다. 상세 규칙: [AGENTS.md](AGENTS.md)
