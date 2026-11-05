# LogisRisk Web (Next.js)

Next.js 15 (App Router, 정적 export) · TypeScript strict · Tailwind CSS v4 · shadcn/ui(Radix) · TanStack Query/Table/Virtual ·
Recharts · MapLibre GL. API 는 저장소 루트의 FastAPI(`backend/`)가 같은 도메인에서 제공한다.

| 명령 | 설명 |
|---|---|
| `npm run build` | 정적 빌드 → `out/` (FastAPI 가 서빙) |
| `npm run dev` | 개발 서버 (`NEXT_PUBLIC_API_BASE=http://localhost:8000`, API 측 `LOGISRISK_CORS_ORIGINS`) |
| `npm run gen:api` | 백엔드 OpenAPI → `src/lib/api-types.ts` |
| `npm run typecheck` / `npx eslint .` / `npm test` | 타입·lint·단위(vitest) |
| `npm run test:e2e` | Playwright (Edge) — 화면 렌더링·클릭 흐름·스크린샷 |

구조
- `src/app/(app)/*` 화면 라우트 · `src/app/login` 접근 코드
- `src/components/app` 셸(사이드바·상단 바·⌘K·워크스페이스) · `common` 공통(표·지도·필터·kit) · `metrics` KPI · `control-tower` · `data-hub` · `screens`(나머지 8개 화면)
- `src/lib` API 클라이언트·필터(URL 동기화)·쿼리 훅·포맷(만/억)·내비
- 디자인 토큰: `src/app/globals.css` (라이트/다크, 데이터 성격 kind 색, 외부 지표 전용색)

원칙: 숫자는 API 원값을 받아 화면에서만 반올림·축약. 계산 불가는 '계산 불가'로 표시하고 0 으로 위장하지 않는다.
샘플 워크스페이스는 항상 상단 배너와 ‘샘플 데이터’ 배지를 표시한다.
