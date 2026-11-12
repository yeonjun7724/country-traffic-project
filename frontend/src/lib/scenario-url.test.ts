import { describe, expect, it } from "vitest";

import { decodeScenario, encodeScenario, outageLink, savedScenarioLink, scenarioLink, scenarioName, SCENARIO_BASE } from "./scenario-url";

describe("시나리오 URL 인코딩", () => {
  it("왕복", () => {
    const s = { name: "경유가 +10% · 수요 +30%", diesel_pct: 10, rate_pct: -2.5, demand_pct: 30, fleet_change: -2, trips_per_vehicle_day: 2 };
    expect(encodeScenario(s)).toBe("10,-2.5,30,-2,2");
    expect(decodeScenario(encodeScenario(s), s.name)).toEqual(s);
  });
  it("범위 밖 값은 편집기 한계로 자르고 정수 필드는 반올림", () => {
    expect(decodeScenario("999,-99,1000,3.6,9", "x")).toEqual({ name: "x", diesel_pct: 200, rate_pct: -50, demand_pct: 300, fleet_change: 4, trips_per_vehicle_day: 5 });
  });
  it("형식이 틀리면 null (화면 기본값 사용)", () => {
    expect(decodeScenario(null)).toBeNull();
    expect(decodeScenario("1,2,3")).toBeNull();
    expect(decodeScenario("a,0,0,0,1")).toBeNull();
    expect(decodeScenario("1,,0,0,1")).toBeNull();
  });
  it("이름이 없으면 기본 이름, 100자 제한", () => {
    expect(decodeScenario("0,0,0,0,1")?.name).toBe("Scenario");
    expect(decodeScenario("0,0,0,0,1", "가".repeat(150))?.name).toHaveLength(100);
  });
});

describe("시나리오 링크", () => {
  it("자동 이름", () => {
    expect(scenarioName({ ...SCENARIO_BASE, diesel_pct: 20 })).toBe("경유가 +20%");
    expect(scenarioName({ ...SCENARIO_BASE, demand_pct: -10, fleet_change: 2 })).toBe("수요 -10% · 차량 +2대");
    expect(scenarioName(SCENARIO_BASE)).toBe("Baseline 동일");
  });
  it("A 만 지정 + 전역 필터 유지", () => {
    const href = scenarioLink({ diesel_pct: 20 }, undefined, { start: "2026-10-01", end: "2026-10-31", warehouses: ["WH-A"], regions: [], carriers: [], vehicles: [], categories: [], stores: [] });
    const u = new URL(href, "http://x");
    expect(u.pathname).toBe("/scenario-lab/");
    expect(u.searchParams.get("a")).toBe("20,0,0,0,1");
    expect(u.searchParams.get("an")).toBe("경유가 +20%");
    expect(u.searchParams.get("b")).toBeNull();
    expect(u.searchParams.getAll("warehouses")).toEqual(["WH-A"]);
    expect(u.searchParams.get("start")).toBe("2026-10-01");
  });
  it("센터 중단·저장 시나리오", () => {
    expect(outageLink("WH-B")).toBe("/scenario-lab/?tab=outage&wh=WH-B");
    expect(savedScenarioLink(12)).toBe("/scenario-lab/?tab=saved&id=12");
  });
});
