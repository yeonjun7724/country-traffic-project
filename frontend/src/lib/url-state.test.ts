import { afterEach, describe, expect, it } from "vitest";

import { _resetPendingQuery, replaceQuery } from "./url-state";

afterEach(() => _resetPendingQuery());

describe("replaceQuery — 연속 URL 갱신이 서로 덮어쓰지 않음", () => {
  it("앞선 replace 가 반영되기 전 두 번째 갱신은 그 위에 쌓인다", () => {
    const calls: string[] = [];
    const router = { replace: (h: string) => calls.push(h) };
    const rendered = "a=1%2C0%2C0%2C0%2C1"; // 렌더 시점 쿼리 (아직 탭 변경 전)
    replaceQuery(router, "/scenario-lab/", rendered, (q) => q.set("tab", "saved")); // 탭 클릭
    replaceQuery(router, "/scenario-lab/", rendered, (q) => q.set("a", "20,0,0,0,1")); // 지연된 입력 동기화
    expect(calls.at(-1)).toBe("/scenario-lab/?a=20%2C0%2C0%2C0%2C1&tab=saved");
  });
  it("바뀐 것이 없으면 이동하지 않음", () => {
    const calls: string[] = [];
    replaceQuery({ replace: (h) => calls.push(h) }, "/x/", "tab=a", (q) => q.set("tab", "a"));
    expect(calls).toEqual([]);
  });
  it("다른 경로의 진행 중 쿼리는 쓰지 않음", () => {
    const calls: string[] = [];
    const r = { replace: (h: string) => calls.push(h) };
    replaceQuery(r, "/a/", "", (q) => q.set("x", "1"));
    replaceQuery(r, "/b/", "y=2", (q) => q.set("z", "3"));
    expect(calls.at(-1)).toBe("/b/?y=2&z=3");
  });
});
