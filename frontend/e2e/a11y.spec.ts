import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/**
 * 접근성 자동 검사 (axe-core, WCAG 2.1 A·AA) — 10개 화면 × 라이트/다크, 샘플 워크스페이스.
 * serious·critical 위반 0 을 강제한다. 자동 검사는 일부 기준만 확인하므로 키보드·스크린리더 수동 점검을 대체하지 않는다.
 * 제외: 지도 캔버스·타일 저작권 표기(서드파티 MapLibre 렌더링).
 */
const ROUTES = ["control-tower", "network", "transportation", "inventory", "fuel-risk", "scenario-lab", "copilot", "data-hub", "reports", "settings"];

for (const r of ROUTES) {
  test(`a11y ${r}`, async ({ page }, info) => {
    await page.addInitScript(() => window.localStorage.setItem("lr.workspace", "demo"));
    await page.goto(`/${r}/`);
    await expect(page.locator("main h1")).toBeVisible();
    await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0, { timeout: 45_000 });
    await page.waitForTimeout(1000);
    const res = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .exclude(".maplibregl-canvas")
      .exclude(".maplibregl-ctrl-attrib")
      .analyze();
    const bad = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    const report = bad
      .map((v) => `[${v.impact}] ${v.id}: ${v.help} (${v.nodes.length})\n` + v.nodes.slice(0, 4).map((n) => `    ${n.target.join(" ")} — ${n.failureSummary?.split("\n")[1] ?? ""}`).join("\n"))
      .join("\n");
    await info.attach("axe", { body: JSON.stringify(res.violations, null, 2), contentType: "application/json" });
    expect(bad.length, `${info.project.name}/${r}\n${report}`).toBe(0);
  });
}
