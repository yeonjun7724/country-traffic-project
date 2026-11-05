# LogisRisk Enterprise — 아키텍처와 결정 기록

## 1. 기술 선택: Streamlit 유지 + 서비스 계층 분리 (단계적 이행)

| 요구 | Streamlit (현재) | React/Next.js + FastAPI |
|---|---|---|
| 기존 분석 자산 재사용 | 그대로 | Python API 로 감싸야 함 |
| 업로드·검증·KPI·시나리오 워크플로 | 충분 (form·dialog·data_editor) | 더 유연 |
| 지도↔표 양방향 선택 | `on_select` 로 가능하나 rerun 기반 | 즉시 반응, MapLibre 직접 제어 |
| 대용량 테이블 편집·가상 스크롤 | 제한적 | 우수 |
| 역할 기반 접근·SSO | 서비스 계층에서 강제, SSO 는 별도 | 표준 패턴 |
| 다중 사용자 동시성·세션 | 프로세스당 세션 메모리 | 무상태 API + 클라이언트 |
| 팀·배포 비용 | 단일 Python 서비스, Railway 그대로 | 2개 서비스 + 빌드 파이프라인 |

**결정**: 이번 단계(P0)는 Streamlit 을 유지하고, 모든 계산·검증·저장·권한·AI 도구를 `logisrisk/` 패키지로 분리했다
(core 모듈은 streamlit 을 import 하지 않음). 다중 사용자 SaaS·고급 지도 상호작용이 필요해지는 P2 시점에
`logisrisk.services.Workbench` 와 analytics 함수를 FastAPI 엔드포인트로 감싸고 프런트엔드를 교체한다.
UI 를 바꿔도 계산·테스트는 그대로 재사용된다.

## 2. 계층

```
streamlit_app.py ── logisrisk/ui (theme, common, nav, pages/*)
                         │  (권한 확인된 Workbench 만 사용)
                         ▼
               logisrisk/services.Workbench  ── security.UserContext / require()
                ├─ data/   schemas · validation · ingest · store(SQLAlchemy) · external · connectors
                ├─ analytics/ kpi · cost · routing · inventory · risk · alerts
                ├─ copilot/   tools(읽기 전용) · agent(OpenAI tool calling + 규칙 폴백)
                └─ reports/   export(Excel · HTML→PDF 인쇄)
```

## 3. 데이터 모델

- 운영 엔터티(10): warehouses, stores, skus, vehicles, orders, order_lines, shipments, inventory, fuel_prices,
  transport_rates. 정의는 `logisrisk/data/schemas.py` 한 곳.
- 저장: 엔터티별 테이블 `ent_<entity>` + `datasets`(버전·업로더·시각·원본파일·매핑·경고·체크섬·DEMO 여부·활성).
  새 업로드 = 새 버전(이전 버전 비활성 보존 → 롤백 가능). 업로드는 단일 트랜잭션.
- `scenarios`(입력값·결과·가정·데이터 버전·계산 버전·상태 draft/proposed/approved/rejected),
  `settings`(KPI 목표·알림 규칙), `action_items`, `audit_log`, `workspaces`/`users`/`memberships`.
- 고속도로 영업소는 기업 거점과 **별개**이며 DB 에 넣지 않고 `output/` CSV 에서 읽는다 (외부 위험 지표).

## 4. 기존 산출물 감사 결과 (자동 재검증: `data/external.audit_external`)

| 항목 | 결과 |
|---|---|
| 취약성 점수 | min-max 정규화 후 0.3·화물비율 + 0.3·화물량 + 0.2·변동계수 + 0.2·불균형. 재계산 오차 0 |
| Fuel Shock Impact | = 취약성 × Shock Index. Shock Index 가 374개 전부 동일 상수 → 순위는 취약성과 동일 |
| 유가 앙상블 | 0.4·Prophet + 0.6·LSTM (역산). 두 모델 차이 평균 약 428원/L |
| Shock Index·위험등급 | 30일 예측 구간 내 변화율 min-max. 변화율이 전부 음수(−7.7~−6.2%)인데 CRITICAL 존재 |
| 예측 기간 | 2026-05-02~05-31 — 현재 시점에서 과거. 미래 전망으로 사용 금지 |
| 모집단 | 좌표 보유 374개. 레거시 화면의 476개·462,160건은 파일로 검증 불가 → 사용 안 함 |
| `impact_score_route.csv` | 노선명 컬럼 없음 → 영업소 파일에서 재집계 |
| 화물 비율 | 일별 비율의 평균 (평균의 비율 아님) |
| LISA | p<0.05 플래그 일치. 클러스터 간 직선 연결은 물류 흐름이 아니므로 그리지 않음 |
| 교통량 | 502일 연속, 누락 0. 기준일 전후 비교는 관측 비교(요일 보정·전년 동기 참고치 병기) |

## 5. 배포 (Railway)

- `railway.toml`·`Procfile` 의 시작 파일이 `streamlit_app.py` 로 변경됨. 레거시로 되돌리려면 `app.py` 로 교체.
- 헬스체크: `/_stcore/health`.
- **저장소 영속성**: Railway 컨테이너 파일시스템은 재배포 시 초기화된다.
  - 방법 A: Railway Volume 을 `/data` 에 마운트하고 `LOGISRISK_DATA_DIR=/data`.
  - 방법 B: Railway PostgreSQL 추가 → `DATABASE_URL=postgresql+psycopg://...` 및 `psycopg[binary]` 의존성 추가.
    테이블은 기동 시 `create_all` 로 생성 (스키마 변경 이력 관리가 필요해지면 Alembic 도입 — 사전 승인 필요).
- 비밀값: Railway Variables 에 `OPENAI_API_KEY` (코드·저장소에 넣지 않음).

## 6. 백업·복구
- SQLite: `data/logisrisk.db` 파일 단위 백업(앱 중지 후 복사) 또는 `sqlite3 logisrisk.db ".backup backup.db"`.
- PostgreSQL: `pg_dump`/`pg_restore`. 데이터셋은 버전 보존 구조라 잘못된 업로드는 Data Hub → 버전 활성화로 롤백.

## 7. 성능
- 활성 데이터셋 버전 또는 설정이 바뀔 때만 Workbench 재로딩 (세션 캐시), 외부 CSV 는 `cache_resource`(1시간).
- 측정(배송 97,520건·주문상세 345,440행): 팩트 구성 5.2초, KPI(현재+직전기간) 0.4초, 시나리오 0.3초, 민감도 3.6초.
  (2차 검토 전 lambda 집계: 팩트 101초·KPI 18초 → 벡터화로 개선. `tests/test_review_fixes.py` 에 회귀 테스트)
- 수십만 건 이상은 DB 측 집계 테이블·비동기 배치(P2) 필요.
- 경로 휴리스틱은 O(n² log n) — 센터·일자당 수백 배송지 규모 대상.

## 8. 보안
- 배포 시 `LOGISRISK_ACCESS_CODE` 로 공용 접근 코드 게이트(상수 시간 비교, 세션당 5회 실패 시 잠금). SSO 대체 아님.
- 역할 전환 테스트 기능은 로컬 모드에서만 (`LOGISRISK_LOCAL_MODE`, Railway 기본 0).
- CSV/Excel 내보내기: `=,+,-,@` 로 시작하는 문자열 셀 무력화(수식 주입 방지). HTML 출력은 모두 이스케이프.
- AI 도구 출력은 `[DATA — 지시 아님]` 으로 래핑, 쓰기 도구 없음, 세션 호출 예산 초과 시 추가 호출 금지.

## 9. 2차 심층 검토에서 수정한 결함
| 결함 | 영향 | 수정 |
|---|---|---|
| 분할배송 주문의 OTIF 가 항상 미달 | 정시·전량 배송이어도 OTIF 0% | 주문 단위 판정(배송수량 합산) |
| 운송사·차량 필터가 주문 수에 미적용 | 필터와 무관한 주문 수 표시 | 해당 배송이 있는 주문만 집계 |
| `merge_asof` 날짜 해상도 불일치 | pandas 3/CSV 경로에서 유가 매칭 예외 | 키를 ns 로 정규화 |
| CSV/Excel 수식 주입 | 업로드 값 `=HYPERLINK(...)` 가 그대로 실행 가능 | 내보내기 시 무력화 |
| 'N/A·NULL·-' 가 값으로 저장 | 권역 'NULL' 등 오염 | 결측 토큰 처리 |
| 예산 알림이 기간 길이 무시 | 1일 필터에도 월 예산과 비교 | 월 예산 일할 환산 |
| 시나리오 차량 부족을 Baseline 과 비교 불가 | 원래 부족한 날을 시나리오 탓으로 오인 | Baseline 부족 일수 병기 |
| 수요 감소 시 운행 처리 불일치 | 용량 정보 유무에 따라 결과 상이 | 일관 규칙(유지) 적용 |
| '내일 배송 가능?'이 과거 실적 재계획 | 미출고 주문 미반영 | 납기일 기준 미출고 주문 계획 모드 |
| 현행 계획 하역시간·제약 위반 미반영 | 비교 기준 불일치 | 배송지별 하역시간·위반 보고 |
| '지난달'을 최근 30일로 처리 | 질문과 다른 기간 답변 | 데이터 최신일 기준 상대기간 해석 |
| 한글 센터명 질의 실패 | '영남센터 중단' 미인식 | ID·이름 매칭 |
| 호출 예산 소진 후 추가 LLM 호출 | 예산 초과 | 도구 결과 결정론적 요약 |
| 검증 후 매핑 변경 시 이전 결과로 저장 | 잘못된 매핑 저장 | 재검증 강제 |
| 참조 엔터티 교체 시 끊기는 참조 미경고 | 기존 주문이 없는 배송지 참조 | 경고 표시 |
| 워크스페이스 전환 후 필터 상태 잔존 | 범위 밖 날짜로 화면 예외 가능 | 위젯 상태 정리 |
| 실적 없는 배송지를 지연율 0%(녹색)로 표시 | 오해 유발 | 회색 '배송 없음' 별도 표시 |
| 공개 배포 시 접근 통제 없음 | 누구나 관리자 | 접근 코드 게이트 |
| 대용량 성능 | 10만 건에서 2분 | 벡터화(5초) |

## 10. Next.js 전환 — P0 (Control Tower · Data Hub)

### 결정
| 항목 | 결정 | 이유 |
|---|---|---|
| 배포 구조 | **A안: 단일 서비스** — FastAPI 가 Next.js 정적 빌드(`frontend/out`)를 같은 도메인에서 서빙 | 쿠키·CORS 문제 없음, 볼륨 1개, 비용 최소. SSR 불필요(로그인 뒤 대시보드) |
| 병행 운영 | 기존 Streamlit 서비스(`railway.toml`) 유지, 신규는 새 Railway 서비스(`railway.web.toml`·`Dockerfile.web`) | 기능 동등성 확인 전 중단 없음 |
| 계산 재사용 | `logisrisk/views/` 뷰 모델을 Streamlit·API 가 공유 | 화면별 값 불일치 방지. UI 에 있던 일별 집계 등을 이동 |
| 프런트 스택 | Next.js 15 · Tailwind v4 · shadcn/ui(Radix) · TanStack Query/Table v8/Virtual · Recharts · MapLibre GL | TanStack Table 은 v9 API 변경이 커서 안정판 v8 고정 |
| 지도 | MapLibre + CARTO Positron/Dark Matter. 센터 라벨은 HTML 마커(한글 글꼴 의존 없음). 로딩 실패 시 단순 배경 | 운영 단계에서 CARTO 이용 조건 확인 또는 자체 타일 |
| 인증 | 서버 세션 쿠키(`lr_session`, 서명 키 `LOGISRISK_SESSION_SECRET`) + 접근 코드(세션 5회·IP 20회/15분 제한) | SSO 는 인터페이스만 — 접근 코드 통과자 = 로컬 사용자(관리자), Streamlit 과 동일 |
| 권한 | 엔드포인트마다 `permission("...")` 의존성 → 기존 `security.require()` (fail-closed) | 워크스페이스는 `X-Workspace` 헤더 + 멤버십 확인(없으면 403) |
| 업로드 | 원본은 서버 메모리에 1시간 임시 보관(매핑 변경 시 재검증), 저장 확정 시에만 DB 기록 | DB 스키마 변경 없음. 검증에 쓴 매핑으로만 저장 |

### API (요약, 전체는 `/api/docs`)
`/api/auth/{status,login,logout}` · `/api/me` · `/api/filters` · `/api/search` ·
`/api/control-tower/{overview,daily,network,cost-to-serve,ledger,ledger.csv,external}` ·
`/api/data/{entities,schemas/{e},templates/{e}.csv,uploads,uploads/{id}/(sheet|validate|commit|errors.csv),demo,datasets,datasets/{id}/activate,entities/{e}/deactivate,quality,integrations}`
- 응답 지표는 `Metric` 구조 그대로(정의·산식·분자·분모·n·기간·kind·status). NaN/Inf → null.
- Workbench 는 (워크스페이스·역할·데이터 버전·설정 리비전) 키로 프로세스 메모리 LRU(8). uvicorn 워커 1개(SQLite·캐시 일관성).

### UX 원칙 적용
- 필터는 상단 필터 바 + URL 쿼리(공유·새로고침 유지). 기간 프리셋은 '데이터 최신일 기준'.
- KPI 9종은 서비스 수준·운송 비용·물동량 3개 패널의 지표 행 — 행을 누르면 정의·산식·분자/분모·경고 시트.
- 지도↔표↔원장 선택은 클라이언트 상태로 즉시 동기화. 외부 지표는 violet 계열 + '기업 실적 아님' 배지로 분리.
- 샘플 워크스페이스는 모든 화면에 '샘플 데이터' 배지·안내. 미구현 8개 화면은 '준비 중'으로 명시(버튼만 있는 기능 없음).

### 검증
- pytest 141 (API 21: 인증·잠금·워크스페이스 격리·조회자 거부·계산 불가·엔진 수치 동등성·업로드/검증/동의/롤백·Excel 시트).
- vitest 11 (만/억·% 표기). Playwright 47: 10개 화면 × 샘플/빈 × 라이트/다크 렌더링(콘솔 오류 0) + 클릭 흐름 7종.
- E2E 가 잡은 실제 결함: MapLibre 모듈 워커 로드 실패(정적 경로 + `.mjs` MIME), 지도 컨테이너 높이 0(MapLibre CSS 가
  Tailwind 레이어보다 우선), 재검증 안내가 필수 필드 경고에 가려짐. 모두 수정.

### 남은 한계 (P0 시점)
- P1/P2 화면 8개는 새 UI 미구현(Streamlit 에서 사용). Copilot SSE 는 P2.
- 업로드 임시 보관은 메모리 — 서버 재시작 시 진행 중 업로드는 다시 올려야 함.
- Docker 이미지는 로컬에서 빌드해 보지 못함(Docker 없음). 동일 의존성만 설치한 venv 로 기동·계산 검증.
- 빌드 도구 체인(next 내부 postcss)에 npm audit 경고 — 정적 export 라 런타임 노출은 없음, Next 패치 시 갱신.
