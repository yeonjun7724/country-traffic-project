import { describe, expect, it } from "vitest";

import { cn } from "./utils";

describe("cn — 글자 크기 단계와 색 클래스가 서로 지우지 않음", () => {
  it("크기 + 색은 둘 다 남는다", () => {
    expect(cn("text-metric font-semibold", "text-danger")).toBe("text-metric font-semibold text-danger");
    expect(cn("text-caption text-kind-demo")).toBe("text-caption text-kind-demo");
  });
  it("크기끼리는 뒤의 것이 이긴다", () => {
    expect(cn("text-body", "text-title")).toBe("text-title");
    expect(cn("text-sm", "text-caption")).toBe("text-caption");
  });
});
