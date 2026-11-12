import { expect, type Page } from "@playwright/test";

/**
 * 화면에 가까워질 때만 렌더하는 영역(Deferred: 지도·차트·원장)을 모두 렌더시킨다.
 * 사람처럼 아래로 나눠 스크롤한 뒤 맨 위로 돌아온다. 전체 화면 스크린샷·접근성 검사·원장 조작 전에 호출.
 */
export async function revealAll(page: Page) {
  const step = Math.round((page.viewportSize()?.height ?? 900) * 0.5);
  for (let i = 0; i < 40; i++) {
    const done = await page.evaluate((s) => {
      window.scrollBy(0, s);
      return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
    }, step);
    await page.waitForTimeout(120);
    if (done) break;
  }
  await expect(page.locator('[aria-label$="불러오기 대기"]')).toHaveCount(0, { timeout: 30_000 });
  await page.evaluate(() => window.scrollTo(0, 0));
}
