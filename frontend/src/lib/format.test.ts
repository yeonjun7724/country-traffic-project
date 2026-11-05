import { describe, expect, it } from "vitest";

import { dateLabel, deltaText, metricParts, metricText, pct, won } from "./format";

describe("won (원화 축약)", () => {
  it("억·만 단위", () => {
    expect(won(142_000_000)).toBe("1.42억");
    expect(won(170_000)).toBe("17만");
    expect(won(9_800)).toBe("9,800");
    expect(won(-250_000_000)).toBe("-2.5억");
  });
  it("축약 끄기", () => expect(won(275_608, { compact: false })).toBe("275,608"));
  it("값 없음은 대시 (0 으로 위장하지 않음)", () => {
    expect(won(null)).toBe("—");
    expect(won(Number.NaN)).toBe("—");
  });
});

describe("metricParts (KPI 카드 값·단위)", () => {
  it("비율은 % 로", () => expect(metricParts(0.8897, "%")).toEqual({ value: "89.0", unit: "%" }));
  it("원은 억원·만원", () => {
    expect(metricParts(141_906_000, "원")).toEqual({ value: "1.42", unit: "억원" });
    expect(metricParts(173_929, "원")).toEqual({ value: "17", unit: "만원" });
  });
  it("건·kg·원/km", () => {
    expect(metricParts(848, "건")).toEqual({ value: "848", unit: "건" });
    expect(metricParts(575_310.4, "kg")).toEqual({ value: "575,310", unit: "kg" });
    expect(metricParts(1277.3, "원/km")).toEqual({ value: "1,277", unit: "원/km" });
  });
  it("계산 불가", () => expect(metricParts(null, "%")).toEqual({ value: "—", unit: "" }));
  it("텍스트 결합", () => {
    expect(metricText(0.95, "%")).toBe("95.0%");
    expect(metricText(848, "건")).toBe("848 건");
  });
});

describe("기타", () => {
  it("pct", () => expect(pct(0.0811)).toBe("8.1%"));
  it("delta 부호", () => {
    expect(deltaText(43.88)).toBe("+43.9%");
    expect(deltaText(-3.78)).toBe("−3.8%");
    expect(deltaText(null)).toBe("—");
  });
  it("날짜", () => expect(dateLabel("2026-10-02")).toBe("2026.10.02"));
});
