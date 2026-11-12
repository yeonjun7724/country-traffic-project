import { expect, test, type Page } from "@playwright/test";

/**
 * 화면 간 맥락 링크 (F1 알림 → 원인, F2 Scenario Lab URL 상태). 샘플 워크스페이스, 라이트 1회.
 */
test.skip(({ colorScheme }) => colorScheme === "dark", "흐름 테스트는 라이트에서 1회");

async function ws(page: Page, id: string) {
  await page.addInitScript((w) => window.localStorage.setItem("lr.workspace", w), id);
}

test("알림 '결품 SKU 보기' → Inventory 가 결품만 필터한 상태로 열리고 전역 필터가 유지된다", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/control-tower/?carriers=DEMO%EC%9A%B4%EC%86%A1A");
  const alerts = page.locator("section", { has: page.getByRole("heading", { name: /확인이 필요한 항목/ }) });
  await alerts.getByRole("link", { name: /결품 SKU 보기/ }).click();
  await expect(page).toHaveURL(/\/inventory\/\?.*risk=%EA%B2%B0%ED%92%88/);
  await expect(page).toHaveURL(/carriers=DEMO/);
  await expect(page.getByRole("button", { name: /^결품/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: /^높음/ })).toHaveAttribute("aria-pressed", "false");
});

test("알림 '지연 원장 보기' → 같은 화면의 원장 '지연 배송' 탭으로 스크롤된다", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/control-tower/");
  // 사용자가 다른 탭을 보고 있어도 링크가 탭을 지정한다
  await page.getByRole("tab", { name: /전체 원장/ }).click();
  await expect(page).toHaveURL(/ledger=all/);
  const alerts = page.locator("section", { has: page.getByRole("heading", { name: /확인이 필요한 항목/ }) });
  await alerts.getByRole("link", { name: /지연 원장 보기/ }).first().click();
  await expect(page).toHaveURL(/ledger=late/);
  await expect(page.getByRole("tab", { name: /지연 배송/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#ledger")).toBeInViewport();
});
