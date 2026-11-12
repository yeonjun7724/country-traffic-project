import { expect, type Page } from "@playwright/test";

/**
 * 화면에 가까워질 때만 렌더하는 영역(Deferred: 지도·차트·원장)을 모두 렌더시킨다.
 * 남은 자리 표시자를 하나씩 화면 가운데로 스크롤해 렌더시키고(데이터 로딩 중 늦게 생기는 자리 표시자 포함) 맨 위로 돌아온다.
 * 전체 화면 스크린샷·접근성 검사·원장 조작 전에 호출.
 */
export async function revealAll(page: Page) {
  await expect(page.locator("main h1")).toBeVisible();
  const ph = page.locator('[aria-label$="불러오기 대기"]');
  for (let i = 0; i < 30; i++) {
    await page.waitForTimeout(250); // 데이터가 오면서 새 자리 표시자가 생길 수 있음
    if ((await ph.count()) === 0) break;
    await ph.first().evaluate((el) => el.scrollIntoView({ block: "center" }));
  }
  await expect(ph).toHaveCount(0, { timeout: 30_000 });
  await page.evaluate(() => window.scrollTo(0, 0));
}
