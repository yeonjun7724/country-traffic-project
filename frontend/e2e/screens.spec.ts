import { expect, test, type Page } from "@playwright/test";

/**
 * 10개 화면 × (샘플 / 빈 워크스페이스) × (라이트 / 다크) 실제 렌더링 + 스크린샷.
 * 스크린샷은 사람이 직접 보고 깨짐·겹침을 확인하기 위한 것 (e2e-screens/).
 */
const ROUTES = [
  "control-tower",
  "network",
  "transportation",
  "inventory",
  "fuel-risk",
  "scenario-lab",
  "copilot",
  "data-hub",
  "reports",
  "settings",
];

async function useWorkspace(page: Page, ws: string) {
  await page.addInitScript((w) => window.localStorage.setItem("lr.workspace", w), ws);
}

function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const t = m.text();
    // 배경지도 타일 네트워크 오류는 앱 오류가 아님 (오프라인 환경 대비 별도 처리됨)
    if (/basemaps\.cartocdn|tiles|Failed to load resource/i.test(t)) return;
    errors.push(`console: ${t}`);
  });
  return errors;
}

for (const ws of ["demo", "default"] as const) {
  test.describe(`workspace=${ws}`, () => {
    for (const r of ROUTES) {
      test(`${r} renders`, async ({ page }, info) => {
        const errors = watchErrors(page);
        await useWorkspace(page, ws);
        await page.goto(`/${r}/`);
        await expect(page.locator("main h1")).toBeVisible();
        // 스켈레톤이 모두 사라질 때까지 (데이터 로딩 완료)
        await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0, { timeout: 45_000 });
        if (r === "control-tower" && ws === "demo") {
          await expect(page.getByRole("button", { name: /OTIF:/ })).toBeVisible();
        }
        await page.waitForTimeout(2000); // 차트 애니메이션·지도 타일이 끝난 뒤 촬영
        await page.screenshot({ path: `e2e-screens/${info.project.name}/${ws}-${r}.png`, fullPage: true });
        expect(errors, errors.join("\n")).toEqual([]);
      });
    }
  });
}
