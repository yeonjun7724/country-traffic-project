import { defineConfig } from "@playwright/test";

/**
 * E2E: FastAPI 가 정적 빌드(frontend/out)를 서빙하는 운영과 같은 구성으로 실행한다.
 *   1) npm run build
 *   2) (저장소 루트) python -m uvicorn backend.main:app --port 8600
 *   3) npm run test:e2e
 * 브라우저는 설치된 Microsoft Edge 를 사용 (별도 바이너리 다운로드 없음). 다른 환경은 E2E_CHANNEL 로 지정.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  outputDir: "./e2e-results",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8600",
    channel: process.env.E2E_CHANNEL ?? "msedge",
    viewport: { width: 1440, height: 900 },
    locale: "ko-KR",
    timezoneId: "Asia/Seoul",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "light", use: { colorScheme: "light" } },
    { name: "dark", use: { colorScheme: "dark" } },
  ],
});
