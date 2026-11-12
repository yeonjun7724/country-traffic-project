import { expect, test } from "@playwright/test";

/**
 * 모바일 폭(390×844) 10개 화면: 가로 스크롤이 생기지 않아야 한다 (표·지도는 자체 스크롤 영역 안에서만).
 * 스크린샷: e2e-screens/mobile/ — 사람이 직접 보고 겹침·잘림을 확인.
 */
const ROUTES = ["control-tower", "network", "transportation", "inventory", "fuel-risk", "scenario-lab", "copilot", "data-hub", "reports", "settings"];

test.skip(({ colorScheme }) => colorScheme === "dark", "모바일은 라이트에서 1회");
test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

for (const r of ROUTES) {
  test(`mobile ${r}: 가로 스크롤 없음`, async ({ page }) => {
    await page.addInitScript(() => window.localStorage.setItem("lr.workspace", "demo"));
    await page.goto(`/${r}/`);
    await expect(page.locator("main h1")).toBeVisible();
    await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0, { timeout: 45_000 });
    await page.waitForTimeout(800);
    // isMobile 에서는 내용이 넓으면 브라우저가 레이아웃 뷰포트 자체를 넓힌다 → innerWidth 가 아니라 기기 폭(390)과 비교
    const [doc, win] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    await page.screenshot({ path: `e2e-screens/mobile/${r}.png`, fullPage: false });
    expect(doc, `문서 폭 ${doc}px > 기기 폭 390px`).toBeLessThanOrEqual(390);
    expect(win, `레이아웃 뷰포트가 ${win}px 로 넓어짐`).toBeLessThanOrEqual(390);
    // 상단 바 핵심 동작은 좁은 화면에서도 보인다
    await expect(page.getByRole("button", { name: /검색/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /모드로$/ })).toBeVisible();
  });
}
