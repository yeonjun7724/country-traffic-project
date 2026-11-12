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

test("Fuel & Risk 카드 → Scenario Lab 이 그 입력값으로 열리고, 입력 변경은 URL·새로고침에 유지된다", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/fuel-risk/");
  await page.getByRole("link", { name: /Scenario Lab 에서 단가·물동량과 함께 비교/ }).first().click();
  await expect(page).toHaveURL(/\/scenario-lab\/\?.*a=/);
  const aName = page.getByLabel("시나리오 A 이름");
  await expect(aName).toHaveValue(/^경유가 [+-]\d+%$/);
  const pctA = Number((await aName.inputValue()).match(/[+-]?\d+/)![0]);
  await expect(page.locator("#dA")).toHaveValue(String(pctA));
  await expect(page.locator("#qB")).toHaveValue("10");
  // 입력 변경 → URL 반영 → 새로고침해도 유지
  await page.locator("#qA").fill("25");
  await expect(page).toHaveURL(new RegExp(`a=${pctA}%2C0%2C25%2C0%2C1`));
  await page.reload();
  await expect(page.locator("#qA")).toHaveValue("25");
});

test("Network 센터 카드 → Scenario Lab 센터 중단 탭이 해당 센터로 열린다", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/network/");
  await page.getByRole("link", { name: /센터 중단 분석/ }).nth(1).click();
  await expect(page).toHaveURL(/tab=outage/);
  await expect(page).toHaveURL(/wh=WH-B/);
  await expect(page.getByRole("combobox", { name: "중단 센터" })).toContainText("중부");
});

test("저장된 시나리오는 ?id= 로 바로 열리고, 같은 입력값으로 다시 분석할 수 있다", async ({ page, request }) => {
  await ws(page, "demo");
  const list = await (await request.get("/api/scenarios", { headers: { "X-Workspace": "demo" } })).json();
  const cost = list.find((r: { kind: string }) => r.kind === "cost_scenario");
  await page.goto(`/scenario-lab/?tab=saved&id=${cost.id}`);
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByRole("heading", { name: cost.name })).toBeVisible();
  await sheet.getByRole("link", { name: /이 입력값으로 다시 분석/ }).click();
  await expect(page).toHaveURL(/\/scenario-lab\/\?.*a=/);
  await expect(page.getByLabel("시나리오 A 이름")).toHaveValue(cost.name);
});

test("알림에서 만든 조치는 근거 알림의 원인 화면으로, 시나리오 조치는 시나리오 상세에 함께 보인다", async ({ page, request }) => {
  await ws(page, "demo");
  await page.goto("/reports/?tab=alerts");
  const row = page.getByRole("listitem").filter({ hasText: "재고 부족(결품)" });
  await row.getByRole("button", { name: /조치 생성/ }).click();
  await expect(page.getByText(/조치 #\d+ 를 만들었습니다/)).toBeVisible();
  await page.goto("/reports/?tab=actions");
  const card = page.locator("article").filter({ hasText: "[재고 부족(결품)]" }).first();
  await card.getByRole("link", { name: /근거 알림의 원인 보기/ }).click();
  await expect(page).toHaveURL(/\/inventory\/\?.*risk=/);

  const list = await (await request.get("/api/scenarios", { headers: { "X-Workspace": "demo" } })).json();
  const sid = list[0].id;
  await page.goto(`/scenario-lab/?tab=saved&id=${sid}`);
  const sheet = page.getByRole("dialog");
  const title = `E2E 후속 조치 ${Date.now()}`;
  await sheet.getByLabel("후속 조치 제목").fill(title);
  await sheet.getByRole("button", { name: "조치 추가" }).click();
  await expect(sheet.getByText(title)).toBeVisible();
  const linked = await (await request.get(`/api/actions?ref_type=scenario&ref_id=${sid}`, { headers: { "X-Workspace": "demo" } })).json();
  expect(linked.some((a: { title: string }) => a.title === title)).toBe(true);
});
