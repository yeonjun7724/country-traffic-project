# LogisRisk 개선 계획 — 진단 · 목표 · 우선순위 (2026-11-12)

> 상태: **승인 대기**. 이 문서는 진단 결과와 제안이며 코드 변경은 아직 없다.
> 모든 제안은 AGENTS.md 의 데이터 정직성 10개 조항·안전 규칙을 전제로 한다.

---

## 0. 측정 환경과 한계

| 항목 | 값 |
|---|---|
| 기준 커밋 | `f9c3e74` (main, clean) |
| 서버 | 정적 빌드(`frontend/out`) + `uvicorn backend.main:app --port 8600`, 워커 1, Python 3.12 / pandas 2.3.3 (`requirements-api.txt` 만 설치한 venv) |
| 데이터 | DEMO 워크스페이스 (배송 2,438 · 주문 2,470 · 주문상세 8,636 · 배송지 62 · 차량 20 · 92일) |
| 브라우저 | Playwright + Edge, 1440×900. "느린 환경"은 CPU 4× 스로틀 + 4G 근사 |
| 대용량 | DEMO 팩트를 메모리에서 40배 복제(97,520행)해 뷰 함수 직접 호출 |

한계 (숫자를 읽을 때 주의)
- **네트워크 스로틀이 완전히 적용되지 않았다** (전송량 대비 완료 시간이 맞지 않음). 느린 환경 수치는 사실상 "CPU 4× 스로틀" 결과로 본다. Railway 실측은 하지 않았다.
- API 측정에서 `localhost` 를 쓰면 Windows IPv6 폴백 때문에 모든 요청이 ~2,050ms 로 나온다 → `127.0.0.1` 로 재측정한 값만 사용.
- 40배 복제는 차량 ID 도 복제해 운행(trip) 수가 실제보다 많을 수 있다. ARCHITECTURE.md §7 의 기존 측정(민감도 3.6초)과 조건이 다르다. 추세 판단용.
- 접근성(대비·키보드)은 **측정하지 않았다** — 도구(axe) 도입이 필요해 계획 항목으로 넣었다.
- 이 PC 는 CLAUDE.md 의 인터프리터 경로(`C:/Users/yeonjun/...`)가 없고 기본 anaconda 에 FastAPI 가 없다. CLAUDE.md 갱신 여부는 결정사항 참고.

---

## 1. 현재 상태

### 1.1 성능

**프런트 번들** (`next build`, First Load JS = gzip 기준)

| 라우트 | First Load JS | 비고 |
|---|---:|---|
| /scenario-lab | **708 kB** | 지도 없는 화면인데 maplibre 포함 |
| /transportation | **697 kB** | maplibre 정적 포함 (dynamic 무력화) |
| /network | **672 kB** | 〃 |
| /fuel-risk | 410 kB | recharts |
| /control-tower | 392 kB | 지도는 정상적으로 지연 로딩 |
| /inventory | 364 kB | |
| /data-hub · /reports · /settings · /copilot | 212–251 kB | |
| 공통 | 103 kB | |

무거운 청크 (raw): maplibre **1,049 KB** (gzip 283 KB) · recharts 365 KB · react-dom 168 KB · 공통 170 KB · zod 119 KB(/login 전용) · radix/cmdk 합계 ~260 KB. 전체 JS raw 3,251 KB → gzip 971 KB.

**원인 확인됨**
1. `screens/network.tsx`·`screens/transportation.tsx` 가 `popupHtml`(순수 문자열 함수)을 `common/geo-map` 에서 **정적 import** → `dynamic()` 으로 감싼 지도 모듈 전체(maplibre)가 페이지 번들에 들어간다.
2. `screens/scenario-lab.tsx` 가 `SimpleTable` 을 `./transportation` 에서 import → transportation → geo-map → maplibre 가 연쇄로 들어간다.
3. **서버가 아무것도 압축하지 않는다** (`GZipMiddleware` 없음). maplibre 청크가 1.07 MB 그대로 전송된다.
4. 해시된 `/_next/static/*` 에 `Cache-Control: immutable` 이 없다 (ETag 재검증만).
5. 사이드바 `<Link>` 기본 프리페치 때문에 **어느 화면에 들어가도 JS 2.7 MB(raw)·요청 ~70개를 내려받는다** (inventory 첫 진입도 maplibre 다운로드).

**화면 지표** (데스크톱 / CPU 4× 스로틀)

| 화면 | LCP | TBT | CLS | 전송량 | API 요청 |
|---|---:|---:|---:|---:|---:|
| control-tower | 936 / **3,260 ms** | 383 / **2,971 ms** | 0.069 / **0.147** | 3.4 MB | 13 |
| network | 540 / 548 | 149 / 900 | 0.096 / 0 | 3.5 MB | 6 |
| transportation | 636 / 804 | 80 / 928 | 0.017 / 0 | 3.2 MB | 4 |
| inventory | 368 / 2,668 | 26 / 1,915 | 0.078 | 3.3 MB | 6 |
| fuel-risk | 432 / 2,772 | 0 / 1,018 | 0.077 | 3.3 MB | 4 |
| scenario-lab | 388 / 2,200 | 37 / 796 | 0.080 | 3.3 MB | 5 |
| copilot | 412 / 2,380 | 11 / 1,136 | 0.077 | 3.3 MB | 3 |
| data-hub | 316 / 2,036 | 0 / 888 | 0.078 | 3.3 MB | 4 |
| reports | 288 / 2,020 | 0 / 937 | 0.083 | 3.3 MB | 6 |
| settings | 496 / 2,300 | 0 / 1,082 | 0.078 | 3.3 MB | 3 |

- 거의 모든 화면에서 CLS ≈ 0.08 이 반복 → 공통 레이아웃(샘플 배너/워크스페이스 로딩 후 높이 변화로 추정, **원인 미확정**).
- Control Tower 는 API 13건 + 지도 + 차트 2개 + 원장 표가 첫 화면에서 동시에 렌더 → 스로틀 시 TBT 3초.

**API** (DEMO, 워커 1, 웜 상태 p50 / 최대, 압축 없음)

| 엔드포인트 | p50 | max | 응답 크기 |
|---|---:|---:|---:|
| `/scenarios/sensitivity` | **628 ms** | 685 | 1 KB |
| `/reports/excel` | 194 ms | 226 | 32 KB |
| `/control-tower/overview` | 87 ms | 120 | 5 KB |
| `/network/units` | 70 ms | 96 | **158 KB** (gzip 시 33 KB) |
| `/reports/preview` | 54 ms | 80 | — |
| `/data/quality` · `/alerts` | 45–46 ms | — | — |
| 나머지 30개 | 3–32 ms | — | — |

- Workbench 콜드 로드 0.13 초, 앱 import 1.4 초 — 문제없음. 요청마다 `_wb_key`(DB 조회) 4 ms.

**대용량 추세** (97,520행, 뷰 함수 직접 호출)

| 경로 | 2,438행 | 97,520행 |
|---|---:|---:|
| `sensitivity_view` | 555 ms | **15,772 ms** |
| `overview` (KPI 현재+직전) | 44 ms | 209 ms |
| `ledger(late)` | 6 ms | 111 ms |
| `daily` / `network` | 8–9 ms | 38–39 ms |

**느린 계산 경로 상위 5**
1. `cost.sensitivity` → `scenario_engine` 을 **12회** 호출. 매번 `fuel_basis` + 운행(trip) groupby 를 처음부터 다시 계산한다 — 둘 다 파라미터와 무관하다. groupby 안의 `lambda s: s.sum(min_count=1)` 2개가 프로파일의 37% (pyinstrument).
2. `reports/excel` — 시트별로 같은 뷰를 재계산 (공유 캐시 없음).
3. `control-tower/overview` — 현재·직전 기간 KPI 를 요청마다 계산.
4. `network/units` — 계산보다 직렬화·전송(158 KB 무압축)이 비용.
5. `data/quality` · `alerts` — 요청마다 전체 프레임 스캔.

**반복 계산·캐시·N+1**
- 뷰/분석 계층에 메모이제이션이 **전혀 없다** (`lru_cache` 등 0건). 같은 필터로 Control Tower 의 7개 엔드포인트가 각각 `apply_filters(wb.fact, flt)` 를 다시 한다.
- Workbench 단위 캐시(LRU 8)는 잘 동작한다. N+1 쿼리는 발견하지 못했다 (계산이 메모리 DataFrame 기반).
- 프런트 React Query 는 staleTime 30초~무한으로 적절하다.

### 1.2 디자인

**공통**
- **타이포 스케일 부재**: 임의 픽셀 글꼴 크기 **18종 / 329회** (`text-[12px]` 72, `text-[12.5px]` 61, `text-[11.5px]` 58 …). 0.5px 단위 차이가 화면마다 섞여 위계가 흐리다.
- **차트·지도 색이 토큰 밖**: tsx 안 hex/rgba 리터럴 약 40곳(`#2563eb`·`#94a3b8`·`#dc2626` …), 원색 팔레트 클래스 약 20곳. 다크 모드·브랜드 변경 시 따로 논다.
- **외부 지표 색 규칙 위반**: ARCHITECTURE 는 "외부 지표 = violet 계열"인데 Network 의 '노선별 평균 취약성' 막대는 primary blue, 영업소 지도는 기업 지연율과 같은 빨강–초록 팔레트를 쓴다 → 기업 실적과 시각적으로 혼동.
- **모바일(390px)**: 5개 화면 모두 가로 스크롤 발생 (문서 폭 531px). 원인은 상단 바 검색창 고정 폭 `w-56` (`app-shell.tsx:71`) — 본문 카드는 정상 리플로우. E2E 에 모바일 뷰포트가 없어 잡히지 않았다.
- 상태 처리: 빈 상태(내 워크스페이스)는 명확하고 정직하다. 로딩은 스켈레톤 있음. 오류 상태 컴포넌트 존재. → 기반은 좋음.
- 접근성: skip-link·aria-current·슬라이더 이름 있음. 대비·키보드 순회는 **미측정**.

**화면별**

| 화면 | 문제 |
|---|---|
| Control Tower | 정보 위계는 좋음. Cost-to-Serve 패널 하단 큰 빈 공간, 원장 '비용 출처' 열 말줄임에 툴팁 없음, 알림 행 '열기'가 데이터 허브 알림에만 존재 |
| Network | 지도 카드 하단 여백, 외부 지표 색(위 참고), 노선 막대에 값 라벨 없음 |
| Transportation | 경고 Callout 3개 연속(파랑·주황·주황) → 경고 피로. 경로별 요약은 깔끔 |
| Inventory | '근거' 열이 잘려 핵심 설명이 안 보임. 수요예측 차트가 **실적만** 그리고 holdout 구간·모델 예측선이 없어 옆 표(WAPE)와 연결이 안 됨 |
| Fuel & Risk | 시나리오 카드 3개가 4열 그리드에 놓여 오른쪽 빈칸, '데이터 출처' 패널 대부분 공백 |
| Scenario Lab | **원인 기여도 워터폴이 읽히지 않음** — y축이 0부터라 362만원 증분이 1.42억 위의 얇은 선으로만 보임. y축 단위 혼재(1.6억 / 8,000만) |
| Reports | 미리보기·섹션 선택 명확. 하단 빈 공간 |
| Copilot | 빈 상태 좋음. 도구 목록이 화면 높이를 넘어 잘림 |
| Data Hub / Settings | 큰 문제 없음 |

### 1.3 기능 — 하루 업무 흐름 기준

```
아침 점검 → 이상 탐지 → 원인 분석 → 대안 비교 → 승인 → 보고
 Control    알림 패널     원장·지도    Scenario /   Scenario   Reports
 Tower                               Transport    Lab 저장
```

| 연결 | 현재 | 끊김 |
|---|---|---|
| 알림 → 원인 | 알림 5종 중 **'데이터 갱신 지연'만 링크**(`alerts-panel.tsx:18`) | OTIF 미달·지연율 초과 → 원장(지연 탭) 없음, 예산 초과 → Cost-to-Serve 없음, 결품 → Inventory(결품 필터) 없음 |
| 원인 → 대안 | 원장·지도에서 시나리오로 가는 경로 없음 | 선택한 센터/권역을 Scenario Lab·센터 중단 분석에 넘길 수 없음 |
| Fuel & Risk → Scenario | 문구로만 안내("Scenario Lab 에서 비교할 수 있습니다") | 파라미터를 담은 링크 없음. Scenario Lab A/B 입력이 URL 에 없어 공유 불가 |
| 대안 → 승인 | Transportation 계획 저장 → Scenario Lab '저장된 시나리오'에서 승인 (토스트 안내만) | 저장 후 해당 항목으로 바로 가는 링크 없음 |
| 승인 → 조치·보고 | Reports 의 알림 탭에서 조치 생성 가능 | 조치(action_items)에 **시나리오·계획·알림 참조 필드가 없음** → "이 조치는 어떤 알림/시나리오 때문인가"를 기록할 수 없음 |
| 화면 간 링크 총계 | 사이드바 제외 **2개** (알림 1, 업로드 완료 1) | |
| Copilot → 화면 | 근거 도구 결과는 표시 | 답변에서 해당 화면·필터로 이동하는 링크 없음 |

**얕거나 미구현인 부분** (UI 는 이미 '미구현'으로 정직하게 표기 중)
- Copilot: 요청-응답만, 토큰 스트리밍 없음. OpenAI 전용.
- 배송 계획: 시간창 미강제(VRPTW 미구현), 직선거리 근사.
- PDF: 브라우저 인쇄 의존(서버 PDF 없음). SSO 없음.
- 업로드 임시 보관이 메모리 — 재시작 시 진행 중 업로드 소실.
- 저장된 뷰(필터 즐겨찾기)·기간 사용자 지정 비교 없음.
- 빈 워크스페이스 온보딩: 업로드 순서(센터→…→배송)가 README 에만 있고 화면에 진행 체크리스트 없음.

---

## 2. 목표

"10배"는 근거가 있는 항목에만 표기했다.

### 성능
| 지표 | 현재 | 목표 | 근거 |
|---|---:|---:|---|
| 민감도 API, 97,520행 | 15.8 s | **≤ 1.5 s (≥10×)** | 파라미터 무관 계산 12회 → 1회 + lambda 집계 벡터화 |
| 민감도 API, DEMO | 628 ms | ≤ 80 ms | 〃 |
| 최대 라우트 First Load JS | 708 kB | ≤ 430 kB | maplibre(283 kB gz) 제거만으로 산출 |
| 첫 방문 전송량(화면당) | 3.3 MB | ≤ 0.8 MB (~4×) | gzip(3.25→0.97 MB 실측) + 전 라우트 프리페치 중단 |
| `/network/units` 전송 | 158 KB | ≤ 35 KB | gzip 실측 32.8 KB |
| Control Tower LCP / TBT (CPU 4×) | 3.26 s / 2.97 s | ≤ 1.8 s / ≤ 0.8 s | 아래 지도·차트 지연 렌더, 요청 수 축소 |
| CLS (공통) | ~0.08 (CT 0.147) | < 0.02 | 공통 레이아웃 높이 예약 |
| Control Tower 동일 필터 재필터링 | 7회 | 1회 | 필터 결과 메모이제이션 |
| 재방문 정적 자원 재검증 요청 | ~70건 | 0건 | immutable 캐시 |

### 디자인
| 지표 | 현재 | 목표 |
|---|---:|---:|
| 임의 글꼴 크기 종류 | 18 | ≤ 7 (토큰) |
| tsx 내 색 리터럴 | ~40 | 0 (지도 스타일 JSON 제외, 토큰에서 읽음) |
| 390px 가로 스크롤 화면 | 5/5 측정 | 0/10 (E2E 로 강제) |
| 외부 지표 색 규칙 위반 | 2곳 | 0 |
| 읽히지 않는 차트 | 1 (워터폴) | 0 |
| axe 심각(serious+) 위반 | 미측정 | 0 |

### 기능
| 지표 | 현재 | 목표 |
|---|---:|---:|
| 목적지 없는 알림 유형 | 4/5 | 0/5 |
| 맥락(필터·선택·파라미터)을 넘기는 화면 간 링크 | 2 | ≥ 12 (아래 F1–F4 에 열거) |
| URL 로 공유 가능한 분석 상태 | 필터·탭 | + Scenario A/B 입력, 지도 선택, 센터 중단 대상 |
| 알림→조치→시나리오 추적 | 불가 | 가능 (결정 필요: 스키마) |

---

## 3. 작업 목록 (영향도 × 난이도 순)

표기: 영향 H/M/L · 난이도 S(≤반나절)/M(1–2일)/L(3일+) · ⚠ = 별도 승인 필요(스키마·의존성·마이그레이션)

### 성능
| # | 작업 | 영향 | 난이도 | 바꿀 파일 | 검증 | 위험 |
|---|---|---|---|---|---|---|
| P1 | `popupHtml` 을 `lib/map-utils.ts` 로, `SimpleTable` 을 `components/common/` 로 이동 → maplibre 정적 포함 제거 | H | S | `common/geo-map.tsx`, `screens/{network,transportation,scenario-lab}.tsx` | `next build` 라우트 표, E2E 스크린샷 | 낮음 |
| P2 | `GZipMiddleware(minimum_size=1024)` + `/_next/static` 에 `Cache-Control: public, max-age=31536000, immutable` | H | S | `backend/main.py` | curl 헤더, 전송량 재측정, pytest | CSV/Excel 스트리밍 응답과의 상호작용 → 테스트로 확인 |
| P3 | 사이드바 링크 `prefetch={false}` (호버 시 프리페치는 유지 검토) | H | S | `app/app-sidebar.tsx` | 화면당 전송량·요청 수 | 첫 이동이 약간 느려질 수 있음 → 측정 비교 |
| P4 | `scenario_engine` 분리: 파라미터 무관 부분(`fuel_basis`, trips groupby) 1회 계산 → `sensitivity`·`scenario_compare` 가 재사용. lambda 집계를 `groupby.sum(min_count=1)` 로 교체 | H | M | `logisrisk/analytics/cost.py` | 기존 테스트 + **결과 동등성 테스트**(DEMO·대용량, 소수점까지 동일), 97k 벤치 | 결과가 바뀌면 안 됨. 바뀌면 CALC_VERSION 상향 |
| P5 | Workbench 에 필터 결과 LRU (`(flt 해시) → 필터·fuel_basis 적용 팩트`) | M | M | `logisrisk/services.py`, `views/control_tower.py` | 동일 필터 연속 호출 시간, 메모리 상한 테스트 | 캐시 무효화 — Workbench 자체가 데이터 버전 키라 범위 안전 |
| P6 | Control Tower 첫 화면 정리: 지도·일별 차트·원장은 뷰포트 진입 시 렌더(IntersectionObserver), recharts 화면별 `dynamic` | M | M | `control-tower/*`, `screens/*` | CPU 4× LCP/TBT | 레이아웃 점프 → 높이 예약으로 CLS 동시 관리 |
| P7 | 공통 CLS 원인 추적·제거 (샘플 배너·워크스페이스 로딩 높이 예약 추정) | M | S | `app/app-shell.tsx` | CLS 재측정 | 낮음 |
| P8 | `reports/excel` 시트 간 계산 공유 | L | S | `views/admin.py` 또는 `reports/` | 시간 측정, 시트 내용 동일성 | 낮음 |
| P9 | 성능 회귀 가드: `scripts/bench.py`(API·대용량) + `next build` 크기 예산을 테스트에 | M | S | `scripts/`, `tests/`, `frontend/e2e` | CI 로컬 실행 | 시간 의존 테스트는 여유 있게 |

### 디자인
| # | 작업 | 영향 | 난이도 | 바꿀 파일 | 검증 | 위험 |
|---|---|---|---|---|---|---|
| D1 | 모바일 상단 바: md 미만에서 검색을 아이콘 버튼으로, 브레드크럼 축약. E2E 에 390px 프로젝트 + `scrollWidth ≤ innerWidth` 단언 | H | S | `app/app-shell.tsx`, `playwright.config.ts`, `e2e/screens.spec.ts` | 10개 화면 모바일 스크린샷 | 낮음 |
| D2 | Scenario 원인 기여도를 진짜 워터폴로 (떠 있는 막대·증분 라벨·y축 기준선 조정, 단위 통일) | H | S | `screens/scenario-lab.tsx` | 스크린샷, 막대 합 = 총 변화 단위 테스트 | 낮음 |
| D3 | 타이포 토큰 6–7단계(`--text-2xs … --text-xl`)를 `globals.css @theme` 에 정의하고 코드모드로 치환 | M | M | `globals.css`, 컴포넌트 전반 | 40장 스크린샷 전후 비교 | 변경 범위 넓음 → 단독 커밋 |
| D4 | 차트·지도 색을 CSS 토큰(`--chart-*`, `--kind-external`)에서 읽는 `useChartColors()` 로 통일. 외부 지표는 violet 계열로 | M | M | `globals.css`, `lib/`, 차트·지도 컴포넌트 | 라이트/다크 스크린샷 | 지도 레이어는 hex 필요 → 런타임에 토큰 값 변환 |
| D5 | 경고 정리: 같은 화면의 가정·한계 Callout 을 하나의 '가정·한계 (N)' 블록으로 묶고 핵심 1줄은 항상 표시 | M | S | `common/kit.tsx`, `screens/transportation.tsx` 등 | 스크린샷 | **정직성 규칙: 경고를 숨기지 않는다** — 접힘 상태에서도 개수·핵심 문장 노출 |
| D6 | 레이아웃 빈칸 정리: Fuel 카드 그리드, Cost-to-Serve 패널, 지도 카드 하단, 말줄임 열에 툴팁 | L | S | 해당 화면 | 스크린샷 | 낮음 |
| D7 | Inventory 수요예측 차트에 holdout 구간 음영 + 선택 모델 예측선 (API 가 예측값을 이미 주는지 확인 후, 없으면 뷰 모델에 추가) | M | M | `views/analysis.py`, `screens/inventory.tsx` | 백테스트 수치와 차트 일치 테스트 | 계산은 기존 `forecast_sku` 그대로 |
| D8 | 접근성: Playwright 에 axe 검사 (10개 화면 × 테마) | M | S | `frontend/e2e`, ⚠ devDependency `@axe-core/playwright` 1개 추가 | serious+ 0건 | 의존성 1개 추가 |

### 기능 (기존 흐름을 깊게)
| # | 작업 | 영향 | 난이도 | 바꿀 파일 | 검증 | 위험 |
|---|---|---|---|---|---|---|
| F1 | **알림 → 원인 딥링크**: 알림에 구조화된 `target`(화면·탭·필터) 추가. OTIF/지연 → 원장 지연 탭(현재 필터 유지), 예산 → Cost-to-Serve, 결품 → Inventory 결품 필터, 데이터 → Data Hub 해당 엔터티 | H | S–M | `analytics/alerts.py`, `backend/models.py`, `alerts-panel.tsx`, `screens/inventory.tsx`, `screens/reports.tsx` | 알림 5종 각각 E2E 클릭 흐름 | API 스키마 변경 → `gen:api` |
| F2 | **Scenario Lab URL 상태**: A/B 입력·탭·센터 중단 대상을 쿼리로 → 공유 링크·새로고침 유지. Fuel & Risk 각 카드·Copilot 답변·원장 선택에서 "Scenario Lab 에서 비교" 링크(파라미터 포함) | H | M | `screens/scenario-lab.tsx`, `fuel-risk.tsx`, `copilot.tsx`, `lib/` | URL 왕복 단위 테스트 + E2E | 낮음 |
| F3 | **원인 → 대안**: Control Tower 지도/표에서 센터·권역 선택 시 "센터 중단 분석"·"이 범위로 시나리오" 액션, Network 센터 카드 → 센터 중단 | M | S | `control-tower/*`, `screens/network.tsx` | E2E | 낮음 |
| F4 | **저장 → 승인 이동**: Transportation 계획/Scenario 저장 토스트에 해당 항목 링크(`?tab=saved&id=`), 저장 목록에서 id 로 바로 열기 | M | S | `screens/transportation.tsx`, `scenario-lab.tsx` | E2E | 낮음 |
| F5 | **조치 추적**: 조치에 `ref_type`(alert/scenario/plan)·`ref_id` 연결 → 시나리오 상세에 관련 조치, 조치에서 근거 화면으로 이동 | H | M | ⚠ `data/schemas.py`·`data/store.py`(컬럼 추가), API, `reports.tsx` | 마이그레이션 테스트(기존 DB 호환), E2E | **스키마 변경 — 마이그레이션 계획 승인 필요** |
| F6 | 빈 워크스페이스 온보딩 체크리스트: 엔터티 업로드 순서·완료 상태(`/api/data/entities` 기반)를 Control Tower 빈 상태에 | M | S | `control-tower.tsx`, `data-hub/*` | 빈 워크스페이스 스크린샷 | 값 생성 없음(정직성 OK) |
| F7 | 저장된 뷰: 현재 URL(필터·탭)을 이름 붙여 저장·⌘K 에서 호출 | M | M | ⚠ 저장 위치 결정 필요(`settings` 테이블 재사용이면 스키마 변경 없음) | E2E | 낮음 |
| F8 | Copilot 응답 스트리밍(SSE) + 답변 내 화면 딥링크 | M | L | `copilot/agent.py`, `backend/routers/analysis.py`, `copilot.tsx` | 폴백 경로 테스트 유지 | ⚠ LLM 공급자 결정과 묶임 |

---

## 4. 별도 승인이 필요한 항목

| 항목 | 이유 |
|---|---|
| F5 조치 참조 컬럼 | `action_items` 에 컬럼 추가 = 스키마 변경. 기존 SQLite/운영 볼륨 DB 호환 방법(기동 시 `ALTER TABLE ADD COLUMN` nullable vs Alembic 도입)을 먼저 정해야 함 |
| F7 저장된 뷰 | `settings` 재사용(스키마 무변경) vs 전용 테이블(스키마 변경) |
| F8 Copilot | 현재 OpenAI 전용. 공급자 유지/추가(예: Anthropic Claude) 여부는 의존성·키 관리 변경 |
| D8 axe | devDependency 1개 추가 |
| P2 배포 영향 | Railway 는 push 시 배포 — 압축·캐시 헤더는 운영 동작을 바꾸므로 push 전 확인 |

---

## 5. 1차 실행 권장 범위 (8개)

| 순서 | 항목 | 이유 |
|---|---|---|
| 1 | **P1** maplibre 정적 포함 제거 | 반나절 이하, 3개 라우트 −280 kB(gz). 위험 거의 없음 |
| 2 | **P2** gzip + immutable 캐시 | 한 파일 수정으로 전송량 ~3.3× 감소, 재방문 요청 ~70건 제거 |
| 3 | **P3** 전 라우트 프리페치 중단 | 모든 화면이 2.7 MB 를 받는 문제의 직접 원인 |
| 4 | **P4** 시나리오 엔진 공통 계산 1회화 | 근거 있는 유일한 10× 항목(15.8 s → ≤1.5 s). 결과 동등성 테스트로 안전 확보 |
| 5 | **F1** 알림 → 원인 딥링크 | 하루 업무 흐름의 첫 끊김. 계산 변경 없이 연결만 추가 |
| 6 | **F2** Scenario Lab URL 상태 + 진입 링크 | 분석 결과 공유·재현의 기반. F3·F4·F8 이 이 위에 올라감 |
| 7 | **D1** 모바일 상단 바 + 모바일 E2E | 모든 화면의 가로 스크롤을 한 곳 수정으로 해결하고 회귀 방지 |
| 8 | **D2** 워터폴 수정 | 현재 화면에서 유일하게 "읽을 수 없는" 차트. Scenario Lab 의 핵심 설명 도구 |

2차 후보: P5·P6·P7(Control Tower 체감 속도), D3·D4(토큰 체계 — 범위가 넓어 단독 진행), F3·F4·F6, P9(회귀 가드).
3차(승인 후): F5·F7·F8·D8.

각 항목은 "변경 → 같은 방법으로 재측정 → 이 문서의 표 갱신 → pytest·typecheck·eslint·vitest·E2E 통과 → 스크린샷 확인 → 항목 단위 커밋(push 없음)" 순서로 진행한다.

---

## 부록: 재현 방법

- 번들: `cd frontend && npm run build` (라우트 표) / `.next/app-build-manifest.json` 으로 라우트별 청크 합산
- API: 서버 기동 후 `127.0.0.1:8600` 로 엔드포인트별 1회(콜드) + 6회(웜) 요청, p50·max·바이트
- 대용량: Workbench 를 로드한 뒤 `wb.fact` 를 40배 복제(배송·주문·차량 ID 접미사)하여 뷰 함수 직접 시간 측정
- 화면: Playwright(Edge) PerformanceObserver 로 LCP·CLS·longtask(TBT), CDP 로 전송량, CPU 4× 스로틀
- 모바일: 390×844 `isMobile`, `document.documentElement.scrollWidth` 비교
- 측정 스크립트는 세션 임시 폴더에서 실행했다 — 1차 작업 P9 에서 `scripts/bench.py` 로 저장소에 정식 추가 제안
