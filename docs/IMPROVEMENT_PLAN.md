# LogisRisk 개선 계획 — 진단 · 목표 · 우선순위 (2026-11-12)

> 상태: **1·2·3차 실행 완료 (2026-11-12)** — 1차: 권장 8개 + F5·D8, 2차: P5·P6·P7·F3·F6·D3·D4·P9,
> 3차: 저장된 보기·Copilot 스트리밍·첫 화면 번들/선요청. 결과는 아래 '실행 결과 (3차)'·'(2차)'·'(1차)', 진단 기록은 §0 이하.
> 모든 제안은 AGENTS.md 의 데이터 정직성 10개 조항·안전 규칙을 전제로 한다.

---

## 실행 결과 (3차)

### 1. Control Tower 첫 화면 (2차 미달 항목) — (a) 번들 축소 + 선요청
| 지표 (CPU 4×, 중앙값) | 기준 | 2차 | **3차** | 목표 |
|---|---:|---:|---:|---:|
| LCP | 3,344 ms | 2,956 ms | **≈ 2,400 ms** | ≤ 1,800 ms — **미달** |
| CLS | 0.150 | 0.020 | **0** | < 0.02 |
| 첫 로딩 JS (gzip) | — | 405 kB | **262 kB** (−35%) | — |
| 첫 화면 데이터 도착 | — | 1.0~1.5 s | **≈ 0.3 s** | — |
| 데스크톱 KPI 표시 | — | — | **0.46 s** | — |

- 한 일: recharts·달력(react-day-picker·date-fns)·Ctrl+K(cmdk)를 쓸 때 불러오기, `<head>` 인라인 스크립트로 HTML 파싱 중
  `/api/me`·첫 화면 API 선요청(`lib/preload`, 한 번만·같은 URL 에서만), 배송 네트워크 섹션 지연 렌더.
- **미달 사유 (측정으로 확인)**: 선요청 유무를 같은 빌드에서 바꿔도 KPI 표시 시각이 같았다(2.6 s vs 2.5 s) → 데이터 대기가 아니다.
  웹폰트 차단 시 −0.2 s. 시간대별 CPU 프로파일상 0.3 s 이후 메인 스레드가 끝까지 포화(JS 실행 + 스타일·레이아웃).
  즉 남은 시간은 **클라이언트 렌더 자체**다. LCP 를 1.8 s 아래로 내리려면 첫 화면 HTML 을 서버에서 미리 그리는 (b) 방식
  (Next 서버 런타임 또는 FastAPI 측 템플릿)이 필요하다 — 배포 구조 변경이라 별도 결정 사항으로 남긴다.
- 번들 가드 예산을 440 → 410 kB 로 낮춰 이번 감소를 고정 (현재 최대 /fuel-risk 397 kB).

### 2. Copilot 응답 스트리밍 (OpenAI 유지)
- `POST /api/copilot/chat/stream` (SSE): 진행 문구 · 실행 도구 · 답변 조각 · 최종 확정. 화면은 흘러나오는 답변을 바로 표시.
- 기존 요청-응답 경로·규칙 기반 폴백·호출 예산 동작은 그대로(같은 이벤트 생성기를 비스트리밍으로 소비).
- 세션 LLM 호출 예산은 서버 메모리 집계로 이동(스트리밍은 응답 시작 후 쿠키를 못 바꿈) — 워커 1개 전제, 재시작 시 초기화.
- 실제 OpenAI 키로는 시험하지 않았다(키 없음). 가짜 스트리밍 클라이언트로 도구 호출 조각 이어 붙이기·답변 조각 전달·
  중간 오류 폴백을 단위·API 테스트로 확인.

### 3. 저장된 보기
- 화면 + URL(전역 필터·탭·입력값)을 이름 붙여 저장 → 상단 바 메뉴·Ctrl+K 에서 열기. 워크스페이스 공유, 최대 50개.
- settings 테이블 재사용 — **DB 스키마 변경 없음**. 계산 캐시 키에서 제외해 보기 저장이 계산 캐시를 깨지 않음.

### 검증
pytest 178 (pandas 3: 117) · vitest 31 · Playwright 95 · 번들 가드 통과.

### 커밋 (3차)
`cd68f16` 저장된 보기 · `bfac9e1` Copilot 스트리밍 · `faeab02` 첫 화면 번들·선요청

### 남은 후보
1. Control Tower LCP — (b) 첫 화면 서버 렌더 (배포 구조 변경, 결정 필요).
2. 다른 화면의 차트(recharts)도 지연 로딩 → 라우트당 ~100 kB 추가 절감 여지.
3. 이전부터의 큰 항목: 시간창 배차(VRPTW), 서버 PDF, SSO, 업로드 임시 보관 영속화.

---

## 실행 결과 (2차)

측정: 1차와 같은 방법 — 기준 커밋 `f9c3e74` / 1차 완료 / 2차 완료를 같은 PC·조건에서 각 3회 중앙값.
브라우저 지표는 Playwright·Edge 측정 스크립트(PerformanceObserver LCP·CLS·longtask, 1440×900, CPU 4× 스로틀 — 세션 임시 스크립트로 저장소에 없음), API·계산은 `scripts/bench.py`.

### 성능 — Control Tower (1차 미달 항목)
| 지표 | 기준 | 1차 | **2차** | 목표 | 판정 |
|---|---:|---:|---:|---:|---|
| TBT, CPU 4× | 4,638 ms | 4,216 ms | **897 ms** | ≤ 800 ms | 근접 (5.2× 개선, 목표 대비 +97 ms) |
| LCP, CPU 4× | 3,344 ms | 4,030 ms | **2,956 ms** | ≤ 1,800 ms | **미달** |
| CLS | 0.150 | 0.145 | **0.015 (데스크톱) / 0.020 (4×)** | < 0.02 | 데스크톱 달성, 4× 경계 |
| 데스크톱 TBT | 264 ms | 296 ms | **0 ms** | — | |
| 첫 화면 API 요청 | 13 | 13 | **8** | — | |
| 첫 방문 전송량 | 3.47 MB | 1.17 MB | **0.76 MB** | ≤ 0.8 MB | 달성 |

- 원인과 조치: 첫 화면 메인 스레드의 대부분이 지도(maplibre, ~650 ms) → 절반 이상 보일 때 불러오기. 일별 차트·CTS·원장은 가까워질 때 렌더.
  `/api/me` 와 인증 확인을 병렬로, me 응답 직후 첫 화면 쿼리를 선요청(데이터 요청 시작이 me 완료 후 0.4~0.9 s → 25 ms).
- **LCP 미달 사유**: 4× 스로틀에서 JS 파싱·하이드레이션(공통 번들 ~400 kB)이 1초 이상 걸리고, 그 뒤 me → 데이터가 이어진다.
  단발 측정에서는 1.0~2.1 s 도 나왔지만 중앙값은 2.96 s. 더 줄이려면 첫 화면 KPI 를 서버에서 미리 렌더하거나(정적 export 구조 변경),
  공통 번들(react-query·radix·sidebar)을 줄여야 한다 — 3차 후보.

### 성능 — 다른 화면·서버
| 지표 | 기준 | 2차 |
|---|---:|---:|
| 공통 CLS (Control Tower 외 9개 화면, 데스크톱) | 0.076–0.093 | **0.001–0.019** |
| 97,520행 Control Tower 1회 로딩(뷰 5개) | 298 ms (1차) | **227 ms** |
| 97,520행 원장(지연) | 97–111 ms | **52 ms** |
| 민감도 API p50 (DEMO) | 628 ms | 91 ms (1차 80 ms — 측정 편차 범위) |

- 측정 주의: Network 데스크톱 TBT 는 104 → 190 ms 로 늘었다. 프로파일상 지도(maplibre) 초기화(~440 ms)가 대부분이며 2차 코드는
  보이지 않는다. 지도가 주 내용인 화면이라 지연 로딩 대상이 아니고, 초기화가 한 긴 작업으로 묶이는 시점 차이로 보인다 — 원인 미확정.
- CPU 4× 스로틀 수치는 화면에 따라 회차별 편차가 크다(1차 결과의 측정 주의 참고). 데스크톱 수치를 주 판단 근거로 둔다.

### 기능
| 항목 | 2차 |
|---|---|
| Control Tower → 대안 | 표·지도에서 고른 배송지로 Scenario Lab(전역 필터 유지), 센터별 '센터 중단 분석' 메뉴 |
| 빈 워크스페이스 | 업로드 순서·완료·선행 데이터·다음 단계 체크리스트 (`/api/data/entities` 그대로, 수치 생성 없음), 일부만 올린 경우 안내 한 줄 |
| Data Hub | 업로드 대상 `?entity=` — 체크리스트·'데이터 갱신 지연' 알림에서 해당 양식으로 |
| 화면 간 맥락 링크(종류) | 14 → **17** |

### 디자인
| 지표 | 기준 | 2차 |
|---|---:|---:|
| 임의 글꼴 크기 종류 / 사용처 | 18 / 343 | **7단계 토큰 / 0** (`text-caption…text-display`) |
| 화면 코드 색 리터럴 | ~70 | **0** (테마 색 메타태그 2곳만) |
| 외부 지표 색 규칙 위반 | 2+ (지도·등급·LISA·노선 막대·근접 배지·외부 유가 예측) | **0** — 모두 보라 계열 |
| axe serious·critical | 0 | 0 유지 |

### 회귀 가드 (P9)
- `npm run check:bundle`: 라우트당 첫 로딩 JS(gzip) 440 kB 예산, 첫 로딩에 maplibre 포함 시 실패 (정적 import 를 넣어 실패 확인).
  현재 최대 /fuel-risk 419 kB (1차 411 kB → 2차 기능·색·선요청 코드로 라우트당 +10~14 kB).
- `tests/test_perf_guard.py`: 민감도·A/B 비교의 집계 1회, 필터 위치 캐시 재사용(호출 횟수로 결정적 검증), 대용량 상한.

### 2차 중 발견해 고친 결함
- 입력 직후 탭을 누르면 지연된 URL 동기화가 탭을 되돌림(F2 경합) → URL 갱신 일원화(`lib/url-state`).
- 결측 날짜(NaT)가 API 에 문자열 `"NaT"` 로 나감(1차 이전부터) → null.
- 새 글자 크기 클래스를 병합기(cn)가 색으로 오인해 지움 → font-size 그룹 등록.
- E2E: 같은 제목으로 조치를 만들어 반복 실행 시 실패하던 테스트, 지연 렌더 도입에 맞춘 스크롤 도우미.

### 커밋 (2차)
`c0c54eb` P5 · `da34d4c` P6·P7 · `85b7b1b` F3·F6 · `b898007` D4 · `164589e` D3 · `17b9ae3` P9 · `5191dcc` 지도 팔레트

### 3차 후보
1. Control Tower LCP(4×) — 공통 번들 축소 또는 첫 화면 KPI 사전 렌더(정적 export 구조 변경 필요, 승인 사항).
2. Copilot 응답 스트리밍(SSE) — OpenAI 유지 전제.
3. 저장된 뷰(필터 즐겨찾기) — 저장 위치 결정 필요.

---

## 실행 결과 (1차)

측정: 같은 PC·같은 조건에서 기준 커밋 `f9c3e74` 과 현재를 번갈아 3회씩 측정한 중앙값 (브라우저 지표),
API 는 `scripts/bench.py --api`, 계산은 `scripts/bench.py`.

### 성능
| 지표 | 기준 | 현재 | 목표 | 판정 |
|---|---:|---:|---:|---|
| 민감도 계산, 97,520행 | 15,772 ms | **192 ms (82×)** | ≤ 1,500 ms | 달성 |
| 민감도 API p50, DEMO | 628 ms | **80 ms** | ≤ 80 ms | 달성 |
| 최대 라우트 First Load JS | 708 kB | **411 kB** (fuel-risk) | ≤ 430 kB | 달성 |
| 화면당 첫 방문 전송량 | 3.26–3.63 MB | **0.53–1.25 MB** | ≤ 0.8 MB | 지도 없는 8개 화면 달성, 지도 2개 화면(지도 타일 포함) 1.17–1.25 MB |
| 화면당 JS 전송 | 2.7 MB | 0.22–0.72 MB | — | |
| `/network/units` 전송 | 158 KB | **33 KB** | ≤ 35 KB | 달성 |
| 재방문 정적 자원 재검증 | 매 요청 | 0 (immutable) | 0 | 달성 |
| Control Tower LCP / TBT (CPU 4×) | 3.34 s / 4.64 s | 4.03 s / 4.22 s | ≤ 1.8 s / ≤ 0.8 s | **미달** — 메인 스레드 작업(P6)은 2차 범위. 전송 감소만으로는 개선되지 않음 |
| 데스크톱 LCP / TBT | 변화 거의 없음 | | | 로컬 무제한 네트워크라 전송 감소 효과가 드러나지 않음 |
| 공통 CLS | ≈0.08 (CT 0.15) | 동일 | < 0.02 | **미착수** (P7, 2차) |

측정 주의: CPU 4× 스로틀에서 기준 커밋의 network·transportation·scenario-lab 은 데스크톱보다 적은 바이트를 받은 상태에서
networkidle 로 판정되어(데이터 렌더 전 측정 추정, CLS 0) 비교에서 제외했다. 스로틀 수치는 실행마다 편차가 크다.

### 기능
| 지표 | 기준 | 현재 |
|---|---:|---:|
| 목적지 없는 알림 유형 | 4/5 | **0/5** (OTIF·지연율 → 원장 지연 탭, 예산 → CTS, 결품 → Inventory 결품, 데이터 → Data Hub) |
| 맥락을 넘기는 화면 간 링크(종류) | 2 | **14** — 알림 패널(규칙별 목적지)·Reports 알림·조치 근거 2종(알림·시나리오)·Fuel 카드 → Scenario·Network 센터 → 센터 중단·저장 시나리오 재분석 2종(비용·센터 중단)·저장/복제 토스트 5곳·시나리오 조치 토스트 → 조치 워크플로 |
| URL 로 공유 가능한 상태 | 필터·탭 | + 원장 종류·위험 구분·Scenario A/B 입력·중단 센터·열린 시나리오 |
| 알림 → 조치 → 시나리오 추적 | 불가 | 가능 (스키마 v2, 시나리오 상세에 관련 조치) |

### 디자인·접근성
| 지표 | 기준 | 현재 |
|---|---:|---:|
| 390px 가로 스크롤 | 측정 5/5 화면 | **0/10** (E2E 강제) |
| 읽히지 않는 차트 | 1 (워터폴) | **0** (변화량 워터폴, 값 라벨) |
| axe serious·critical | 미측정 → 첫 측정 20/20 화면 위반 | **0** (10 화면 × 라이트/다크, E2E 강제) |
| 임의 글꼴 크기 / 색 리터럴 | 18종 / ~40 | 동일 — **미착수** (D3·D4, 2차) |
| 외부 지표 색 규칙 위반 | 2 | 동일 — **미착수** (D4) |

### 커밋
`3775415` 계획·CLAUDE.md · `9a86e6e` P1 · `5e31eb4` P2 · `36cd581` P3 · `a43954c` P4 · `aa6dc4c` F1 · `0deea71` F2 ·
`d3bbfe2` F5 · `7e9a968` D1 · `2f5c63e` D2 · `549ab7d`·`69ec87c` D8

### 2차 권장 (우선순위)
1. **P6·P7** Control Tower 첫 화면 지연 렌더(지도·차트·원장) + 공통 CLS 원인 제거 — 남은 성능 목표 2개가 여기 걸려 있다.
2. **D3·D4** 타이포 토큰·차트/지도 색 토큰화 + 외부 지표 violet 통일 — 범위가 넓어 단독 진행.
3. **P5** 필터 결과 메모이제이션 (97k 행에서 overview 181 ms·ledger 97 ms).
4. **F3·F6** Control Tower 선택 → 센터 중단/시나리오, 빈 워크스페이스 온보딩 체크리스트.
5. **P9** `next build` 크기 예산·벤치 회귀 가드를 테스트에.


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
