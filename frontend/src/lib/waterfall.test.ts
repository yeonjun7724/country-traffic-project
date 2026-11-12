import { describe, expect, it } from "vitest";

import { waterfallSteps } from "./waterfall";

describe("변화량 워터폴", () => {
  it("요인 막대가 이어지고 마지막 '총 변화'가 합계와 같다", () => {
    const s = waterfallSteps({ 경유가: 3_620_000, "운송 단가": 0, "물동량(운행 증가)": 2_000_000, 상호작용: 400_000 }, { 경유가: "경유" });
    expect(s.map((x) => x.name)).toEqual(["경유", "운송 단가", "물동량(운행 증가)", "상호작용", "총 변화"]);
    expect(s[0].range).toEqual([0, 3_620_000]);
    expect(s[2].range).toEqual([3_620_000, 5_620_000]); // 앞 막대 끝에서 시작
    expect(s.at(-1)).toMatchObject({ kind: "total", value: 6_020_000, range: [0, 6_020_000] });
  });
  it("감소 요인은 아래로, 총 변화가 음수면 0 아래 막대", () => {
    const s = waterfallSteps({ a: -500, b: 200 });
    expect(s[0]).toMatchObject({ kind: "down", range: [-500, 0] });
    expect(s[1]).toMatchObject({ kind: "up", range: [-500, -300] });
    expect(s[2]).toMatchObject({ kind: "total", value: -300, range: [-300, 0] });
  });
  it("숫자가 아닌 값은 0 으로 (계산 불가 요인이 그래프를 깨지 않음)", () => {
    expect(waterfallSteps({ a: Number.NaN }).at(-1)!.value).toBe(0);
  });
});

describe("niceCeil", () => {
  it("1·2·2.5·5×10ⁿ 로 올림", async () => {
    const { niceCeil } = await import("./waterfall");
    expect(niceCeil(3_620_000)).toBe(5_000_000);
    expect(niceCeil(6_020_000)).toBe(10_000_000);
    expect(niceCeil(2_400_000)).toBe(2_500_000);
    expect(niceCeil(100)).toBe(100);
    expect(niceCeil(-5)).toBe(0);
  });
});
