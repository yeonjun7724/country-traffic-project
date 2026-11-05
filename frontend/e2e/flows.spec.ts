import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

/**
 * 실제 클릭 흐름 검증 (라이트 테마 1회). 샘플 워크스페이스 기준.
 * 업로드 테스트는 샘플 워크스페이스에 같은 샘플 파일을 새 버전으로 저장한다 (데이터 내용 동일).
 */
test.skip(({ colorScheme }) => colorScheme === "dark", "흐름 테스트는 라이트에서 1회");

const FIX = path.resolve(__dirname, "../../fixtures/demo");

async function ws(page: Page, id: string) {
  await page.addInitScript((w) => window.localStorage.setItem("lr.workspace", w), id);
}

function pctText(v: number) {
  return (v * 100).toFixed(1);
}

test("KPI 값이 API(엔진) 값과 일치하고, 정의·산식 시트가 열린다", async ({ page, request }) => {
  await ws(page, "demo");
  await page.goto("/control-tower/");
  const api = await (await request.get("/api/control-tower/overview", { headers: { "X-Workspace": "demo" } })).json();
  const otif = api.kpis.find((k: { key: string }) => k.key === "otif");
  const btn = page.getByRole("button", { name: /^OTIF:/ });
  await expect(btn).toContainText(pctText(otif.value));
  await btn.click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByRole("heading", { name: "OTIF" })).toBeVisible();
  await expect(sheet).toContainText("정의");
  await expect(sheet).toContainText(otif.formula);
  await expect(sheet).toContainText(Number(otif.denominator).toLocaleString("ko-KR"));
});

test("운송사 필터를 바꾸면 URL 과 KPI 가 함께 바뀐다", async ({ page, request }) => {
  await ws(page, "demo");
  await page.goto("/control-tower/");
  await page.getByRole("button", { name: "운송사 필터" }).click();
  await page.getByRole("option", { name: /DEMO운송A/ }).click();
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/carriers=DEMO/);
  const api = await (
    await request.get("/api/control-tower/overview?carriers=DEMO%EC%9A%B4%EC%86%A1A", { headers: { "X-Workspace": "demo" } })
  ).json();
  const ship = api.kpis.find((k: { key: string }) => k.key === "shipments");
  await expect(page.getByRole("button", { name: /^배송 건수:/ })).toContainText(Number(ship.value).toLocaleString("ko-KR"));
  // 새로고침해도 유지
  await page.reload();
  await expect(page.getByRole("button", { name: "운송사 필터" })).toContainText("DEMO운송A");
});

test("배송지 표에서 선택하면 원장이 좁혀진다", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/control-tower/");
  const table = page.getByRole("region", { name: "배송지 목록" });
  await table.getByRole("checkbox", { name: "행 선택" }).first().click();
  await expect(page.getByRole("button", { name: /배송지 1곳 선택됨/ })).toBeVisible();
  await page.getByRole("button", { name: /배송지 1곳 선택됨/ }).click();
  await expect(page.getByRole("button", { name: /곳 선택됨/ })).toHaveCount(0);
});

test("⌘K 검색으로 센터를 찾아 필터를 적용한다", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/control-tower/");
  await expect(page.locator("main h1")).toBeVisible();
  await page.keyboard.press("Control+k");
  await page.getByPlaceholder(/화면 이름/).fill("WH-A");
  await page.getByRole("option", { name: /수도권센터/ }).click();
  await expect(page).toHaveURL(/warehouses=WH-A/);
  await expect(page.getByRole("button", { name: "센터 필터" })).toContainText("수도권센터");
});

test("워크스페이스를 전환하면 데이터가 섞이지 않는다", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/control-tower/");
  await expect(page.getByRole("button", { name: /^OTIF:/ })).toBeVisible();
  await page.getByRole("button", { name: "워크스페이스 전환" }).click();
  await page.getByRole("menuitem", { name: /내 워크스페이스/ }).click();
  await expect(page.getByText("운영 데이터가 아직 없습니다")).toBeVisible();
  await expect(page.getByRole("button", { name: /^OTIF:/ })).toHaveCount(0);
});

test("업로드 → 자동 매핑 → 검증 → 저장 흐름", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/data-hub/");
  await expect(page.getByRole("heading", { name: /물류센터\(창고\) 업로드/ })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles(path.join(FIX, "DEMO_warehouses.csv"));
  await expect(page.getByRole("heading", { name: "컬럼 매핑" })).toBeVisible();
  await expect(page.getByText("자동").first()).toBeVisible();
  await page.screenshot({ path: "e2e-screens/flow-mapping.png", fullPage: true });
  await page.getByRole("button", { name: "검증 실행" }).click();
  await expect(page.getByText("유효 행")).toBeVisible();
  await page.getByRole("button", { name: /3행 저장/ }).click();
  await expect(page.getByText(/물류센터\(창고\) v\d+ 저장 완료/).first()).toBeVisible();
});

test("오류가 있는 파일은 오류 요약이 나오고, 동의 전에는 저장할 수 없다", async ({ page }) => {
  await ws(page, "demo");
  await page.goto("/data-hub/");
  await page.getByRole("button", { name: /^5\s*주문/ }).click();
  await expect(page.getByRole("heading", { name: /주문 업로드/ })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles(path.join(FIX, "DEMO_invalid_orders_for_validation.csv"));
  await page.getByRole("button", { name: "검증 실행" }).click();
  await expect(page.getByText("오류 요약")).toBeVisible();
  const save = page.getByRole("button", { name: /행 저장/ });
  await expect(save).toBeDisabled();
  await page.getByLabel(/오류 행 .*건을 제외하고/).click();
  await expect(save).toBeEnabled();
  await page.screenshot({ path: "e2e-screens/flow-validation.png", fullPage: true });
  // 매핑을 바꾸면 이전 검증 결과로 저장할 수 없다
  await page.getByRole("combobox", { name: "주문번호 에 매핑할 원본 컬럼" }).click();
  await page.getByRole("option", { name: "(매핑 안 함)" }).click();
  await expect(page.getByText("검증 후 매핑이 바뀌었습니다. 다시 검증하세요.")).toBeVisible();
  await expect(page.getByRole("button", { name: /행 저장/ })).toHaveCount(0);
});
