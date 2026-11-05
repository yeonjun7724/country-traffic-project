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
- 활성 데이터셋 버전이 바뀔 때만 Workbench 재로딩 (세션 캐시), 외부 CSV 는 `cache_resource`(1시간).
- DEMO 규모(배송 2,438건) 기준 전 페이지 렌더 수 초 이내. 수십만 건 이상은 집계 테이블·비동기 배치(P2) 필요.
- 경로 휴리스틱은 O(n² log n) — 센터·일자당 수백 배송지 규모 대상.
