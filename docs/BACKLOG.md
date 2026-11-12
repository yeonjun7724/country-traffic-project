# 다음 작업 목록 (2026-11-12 기준)

1·2·3차 개선 이후 남은 항목. 각 항목의 근거 수치·측정 방법은 [IMPROVEMENT_PLAN.md](IMPROVEMENT_PLAN.md) '실행 결과' 참고.
작업 규칙은 [AGENTS.md](../AGENTS.md)·[CLAUDE.md](../CLAUDE.md) (데이터 정직성, 승인 없는 의존성·스키마·배포 변경 금지).

| # | 항목 | 크기 | 결정 필요 | 권장 순서 |
|---|---|---|---|---|
| 1 | 다른 화면 차트 지연 로딩 | 작음 | 없음 | 1 |
| 2 | Copilot 실제 키 점검 | 작음 | 키 제공 | 2 |
| 3 | Network 화면 TBT 원인 확인 | 작음 | 없음 | 3 |
| 4 | Control Tower 첫 화면 서버 렌더 (LCP 목표) | 큼 | **배포 구조** | 4 |
| 5 | 업로드 임시 보관 영속화 | 중간 | 저장 위치 | — |
| 6 | 시간창 배차 (VRPTW) | 큼 | **의존성(OR-Tools)** | — |
| 7 | 서버 PDF | 중간 | **의존성·한글 글꼴** | — |
| 8 | SSO / 계정 체계 | 큼 | **인증 방식** | — |
| 9 | Streamlit 코드 정리 | 작음 | **삭제 승인** | — |

---

## 1. 다른 화면 차트 지연 로딩
- 현재: Control Tower 만 recharts 를 `next/dynamic` 으로 분리(첫 로딩 405→262 kB). Fuel & Risk·Transportation·Inventory·
  Scenario Lab·Network 는 아직 정적 import — 라우트당 첫 로딩 362~397 kB, recharts 가 ~100 kB.
- 방법: 각 화면의 차트 컴포넌트를 별도 파일로 빼고 `dynamic(() => import(...), { ssr: false, loading: 실제 높이 Skeleton })`.
  범례·머리글처럼 recharts 가 필요 없는 부분은 정적으로 남긴다 (`control-tower/daily-legend.tsx` 참고).
- 검증: `npm run build && npm run check:bundle` 에서 라우트별 감소 확인 후 예산(현재 410 kB)을 낮춘다. E2E 전체·스크린샷.

## 2. Copilot 실제 키 점검
- 현재: 스트리밍(SSE)은 가짜 스트리밍 클라이언트로만 시험했다(이 PC 에 키 없음).
- 할 일: `OPENAI_API_KEY` 를 넣고 예시 질문 3~4개로 ① 글자가 흘러나오는지 ② 도구 호출 후 답변 ③ 호출 예산 표시를 확인.
  Railway 프록시가 SSE 를 버퍼링해도 끝에 한 번에 오며 동작은 한다 — 체감만 확인.
- 참고: 세션 호출 예산은 서버 메모리 집계(워커 1개 전제, 재시작 시 0). 워커를 늘리면 공유 저장소로 옮겨야 한다.

## 3. Network 화면 TBT 원인 확인
- 현재: 데스크톱 TBT 104 → 약 190 ms (2차 이후). 프로파일상 maplibre 초기화(~440 ms)가 대부분이고 우리 코드는 보이지 않아 원인 미확정.
- 할 일: 1차 완료 커밋(`b56647f`)과 현재를 같은 조건으로 5회씩 비교, 차이가 재현되면 커밋 단위로 좁힌다.

## 4. Control Tower 첫 화면 서버 렌더 (LCP 목표 1.8 s)
- 현재: CPU 4× 에서 LCP ≈ 2.4 s (기준 3.3 s). 데스크톱 KPI 표시 0.46 s.
- 확인된 사실: 데이터 선요청 유무와 무관하게 KPI 표시 시각이 같다 → 병목은 **클라이언트 렌더(JS 실행·스타일·레이아웃)**.
  웹폰트 차단 시 −0.2 s 뿐. 남은 방법은 첫 화면 HTML 을 서버에서 미리 그리는 것.
- 선택지 (결정 필요):
  - (가) Next.js 서버 런타임(standalone) 을 Docker 에 함께 띄우고 FastAPI 는 API 만 — 구조 변경 가장 큼, 효과 확실.
  - (나) FastAPI 가 `control-tower/index.html` 을 줄 때 KPI 요약을 서버에서 계산해 HTML 에 끼워 넣기 — 구조 유지, 하이드레이션 불일치 관리 필요.
  - (다) 현 수준 유지 (데스크톱은 이미 충분히 빠름).
- 주의: 워크스페이스가 localStorage 에 있어 서버가 첫 요청에서 모른다 → 쿠키로 옮기는 작업이 선행돼야 한다.

## 5. 업로드 임시 보관 영속화
- 현재: 검증 중인 업로드 원본은 서버 메모리(1시간). 재시작·재배포 시 진행 중 업로드가 사라진다.
- 선택지: 볼륨(`/data/uploads`)에 임시 파일 + 만료 정리 (스키마 변경 없음, 권장) / DB 테이블 (스키마 변경).

## 6. 시간창 배차 (VRPTW)
- 현재: 배송 계획 휴리스틱(Clarke-Wright + 2-opt)은 시간창을 강제하지 않는다 — 화면에 '미지원'으로 명시.
- OR-Tools 도입은 대량 의존성 추가(이미지 크기·빌드 시간 증가) → 승인 필요. 도입 시 기존 휴리스틱은 대안·폴백으로 유지.

## 7. 서버 PDF
- 현재: 경영진 요약은 HTML 을 브라우저에서 인쇄. 서버 PDF 는 한글 글꼴 번들·렌더러(WeasyPrint 등) 의존성 필요 → 승인 필요.

## 8. SSO / 계정 체계
- 현재: 접근 코드 해제 상태(누구나 관리자). 역할·권한은 서버에서 강제되지만 사용자 구분이 없다.
- 결정 필요: OIDC 공급자(Google Workspace·Azure AD 등), 사용자·역할 관리 화면 범위.

## 9. Streamlit 코드 정리
- 모든 화면이 Next.js 로 이전됨. `streamlit_app.py`·`logisrisk/ui/` 와 관련 테스트(`tests/test_ui_smoke.py`) 삭제는 사용자 확인 후.
- `app.py`(레거시 공모전 대시보드)와 `templates/index.html` 은 대상 아님 — 수정·삭제 금지.

---

## 다시 시작할 때
- 환경: [CLAUDE.md](../CLAUDE.md) '실행 환경' (`.venv`, vitest 는 PowerShell, 로컬 측정은 `127.0.0.1`).
- 서버·계산 측정: `.venv/Scripts/python.exe scripts/bench.py [--api http://127.0.0.1:8600]`.
- 번들: `cd frontend && npm run build && npm run check:bundle`.
- 브라우저 지표(LCP·TBT·CLS·전송량)는 세션 임시 Playwright 스크립트로 쟀다(저장소에 없음). 같은 방식:
  Edge·1440×900·`PerformanceObserver`(largest-contentful-paint·layout-shift·longtask)·CDP `Emulation.setCPUThrottlingRate(4)`,
  화면당 3회 중앙값. LCP 가 opacity 애니메이션 요소에서 누락되는 경우가 있어, Control Tower 는 'OTIF 행이 보일 때까지'도 함께 쟀다.
