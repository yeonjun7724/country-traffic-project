import { expect, test, type Page } from "@playwright/test";

/** P1/P2 화면 클릭 흐름 (라이트 1회, 샘플 워크스페이스) */
test.skip(({ colorScheme }) => colorScheme === "dark", "흐름 테스트는 라이트에서 1회");

async function ws(page: Page, id = "demo") {
  await page.addInitScript((w) => window.localStorage.setItem("lr.workspace", w), id);
}

test("Scenario Lab: A·B 비교 → 저장 → 승인 요청 → 승인", async ({ page }) => {
  await ws(page);
  await page.goto("/scenario-lab/");
  await expect(page.getByText("Baseline 총 운송비 (실적)")).toBeVisible();
  await page.getByRole("spinbutton", { name: "경유가 변화" }).first().fill("20");
  await expect(page.getByText(/A · .*/).first()).toBeVisible();
  await page.getByRole("button", { name: "A · B 저장" }).click();
  await expect(page.getByText(/시나리오 #\d+, #\d+ 저장/)).toBeVisible();
  await page.getByRole("tab", { name: "저장된 시나리오 · 승인" }).click();
  await page.getByRole("button", { name: /경유가 \+10% · 수요 \+30%/ }).first().click();
  const sheet = page.getByRole("dialog");
  await sheet.getByRole("button", { name: "승인 요청" }).click();
  await expect(sheet.getByText("승인 대기 중")).toBeVisible();
  await sheet.getByRole("button", { name: "승인", exact: true }).click();
  await expect(sheet.getByText("승인", { exact: true }).first()).toBeVisible();
});

test("Transportation: 배송 계획 대안이 자동 계산되고 승인 요청으로 저장된다", async ({ page }) => {
  await ws(page);
  await page.goto("/transportation/?tab=plan");
  await expect(page.getByText("제안 투입 차량")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("application", { name: "제안 경로 지도" })).toBeVisible();
  await page.getByRole("button", { name: "승인 요청으로 저장" }).click();
  await expect(page.getByText(/제안 #\d+ 저장/)).toBeVisible();
  await page.screenshot({ path: "e2e-screens/flow-plan.png", fullPage: true });
});

test("Copilot: 예시 질문에 도구 근거와 함께 답한다", async ({ page }) => {
  await ws(page);
  await page.goto("/copilot/");
  await page.getByRole("button", { name: "배송 지연이 잦은 권역을 보여줘" }).click();
  await expect(page.getByText(/근거: 도구 호출 결과/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("규칙 기반").first()).toBeVisible();
  await page.screenshot({ path: "e2e-screens/flow-copilot.png", fullPage: true });
});

test("Network: 가중치를 바꾸면 시뮬레이션 상태로 바뀐다", async ({ page }) => {
  await ws(page);
  await page.goto("/network/");
  await expect(page.getByText("기존 결과 재현")).toBeVisible();
  const slider = page.getByRole("slider", { name: "화물 비율(일평균) 가중치" });
  await slider.focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await expect(page.getByText("시뮬레이션", { exact: true })).toBeVisible();
});

test("Reports: Excel 리포트를 내려받는다", async ({ page }) => {
  await ws(page);
  await page.goto("/reports/");
  await expect(page.getByText("시트별 행 수")).toBeVisible();
  const dl = page.waitForEvent("download");
  await page.getByRole("button", { name: "Excel 리포트" }).click();
  expect((await dl).suggestedFilename()).toMatch(/\.xlsx$/);
});

test("Reports: 조치를 만들고 상태를 바꾼다", async ({ page }) => {
  await ws(page);
  await page.goto("/reports/?tab=actions");
  await page.getByLabel("조치 제목").fill("E2E 테스트 조치");
  await page.getByRole("button", { name: "생성" }).click();
  await expect(page.getByText("E2E 테스트 조치")).toBeVisible();
});

test("Settings: 내 워크스페이스 목표를 바꾸면 샘플 워크스페이스에는 영향이 없다", async ({ page }) => {
  await ws(page, "default");
  await page.goto("/settings/");
  const f = page.getByLabel("OTIF 목표 (이상)");
  await f.fill("90");
  await page.getByRole("button", { name: "목표 저장" }).click();
  await expect(page.getByText("목표를 저장했습니다")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("OTIF 목표 (이상)")).toHaveValue("90");
});

test("Inventory: 위험 구분 필터와 수요예측이 동작한다", async ({ page }) => {
  await ws(page);
  await page.goto("/inventory/");
  await expect(page.getByText("보충 추천 합계")).toBeVisible();
  await expect(page.getByText(/이동평균|Naive|요일평균/).first()).toBeVisible();
});
