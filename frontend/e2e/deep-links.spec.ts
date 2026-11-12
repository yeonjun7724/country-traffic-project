import { revealAll } from "./reveal";
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
  await revealAll(page);
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

test("입력을 바꾼 직후 탭을 눌러도 탭이 되돌아가지 않는다 (URL 동기화 경합)", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/scenario-lab/");
  await expect(page.locator("#dA")).toBeVisible();
  await page.locator("#dA").fill("17");
  await page.getByRole("tab", { name: "저장된 시나리오 · 승인" }).click(); // 입력 동기화(350ms 지연)보다 먼저
  await page.waitForTimeout(1200);
  await expect(page).toHaveURL(/tab=saved/);
  await expect(page.getByRole("tab", { name: "저장된 시나리오 · 승인" })).toHaveAttribute("aria-selected", "true");
});

test("Control Tower: 선택한 배송지 범위로 시나리오, 센터 중단 분석으로 바로 이동", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/control-tower/");
  const table = page.getByRole("region", { name: "배송지 목록" });
  await table.getByRole("checkbox", { name: "행 선택" }).first().click();
  await page.getByRole("link", { name: /선택 1곳으로 시나리오/ }).click();
  await expect(page).toHaveURL(/\/scenario-lab\/\?.*stores=/);
  await expect(page.getByText("Baseline 총 운송비 (실적)")).toBeVisible();

  await page.goto("/control-tower/");
  await page.getByRole("button", { name: /센터 중단 분석/ }).click();
  await page.getByRole("menuitem", { name: /중부/ }).click();
  await expect(page).toHaveURL(/tab=outage/);
  await expect(page.getByRole("combobox", { name: "중단 센터" })).toContainText("중부");
});

test("빈 워크스페이스: 업로드 순서 체크리스트 → Data Hub 해당 양식", async ({ page }) => {
  await ws(page, "default");
  await page.goto("/control-tower/");
  const list = page.getByRole("list", { name: "업로드 순서" });
  await expect(page.getByRole("heading", { name: /데이터 준비 0\/\d+/ })).toBeVisible();
  await expect(list.getByRole("listitem")).not.toHaveCount(0);
  await list.getByRole("link", { name: /업로드/ }).first().click();
  await expect(page).toHaveURL(/\/data-hub\/(\?entity=warehouses)?$/);
  await expect(page.getByRole("heading", { name: /물류센터\(창고\) 업로드/ })).toBeVisible();
  // 다른 데이터 유형을 고르면 URL 에 남는다
  await page.goto("/data-hub/?entity=stores");
  await expect(page.getByRole("heading", { name: /배송지\(점포·거래처\) 업로드/ })).toBeVisible();
});

test("저장된 보기: 현재 필터·탭을 저장하고 다른 화면에서 다시 연다", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/inventory/?risk=%EA%B2%B0%ED%92%88&carriers=DEMO%EC%9A%B4%EC%86%A1B");
  await page.getByRole("button", { name: /저장된 보기/ }).click();
  await page.getByRole("menuitem", { name: /현재 화면을 보기로 저장/ }).click();
  const name = `E2E 보기 ${Date.now()}`;
  await page.getByLabel("보기 이름").fill(name);
  await page.getByRole("button", { name: "저장", exact: true }).click();
  await expect(page.getByText(`'${name}' 보기를 저장했습니다`)).toBeVisible();

  await page.goto("/settings/");
  await page.getByRole("button", { name: /저장된 보기/ }).click();
  await page.getByRole("menuitem", { name: new RegExp(name) }).click();
  await expect(page).toHaveURL(/\/inventory\/\?.*risk=%EA%B2%B0%ED%92%88/);
  await expect(page).toHaveURL(/carriers=DEMO/);

  // Ctrl+K 에서도 찾을 수 있고, 지우면 목록에서 사라진다
  await page.keyboard.press("Control+k");
  await page.getByPlaceholder(/화면 이름/).fill(name.slice(0, 8));
  await expect(page.getByRole("option", { name: new RegExp(name) })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /저장된 보기/ }).click();
  await page.getByRole("button", { name: `${name} 보기 지우기` }).click();
  await expect(page.getByText("보기를 지웠습니다")).toBeVisible();
});
