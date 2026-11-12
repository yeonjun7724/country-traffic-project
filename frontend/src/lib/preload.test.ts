import { afterEach, describe, expect, it } from "vitest";

import { preloadScript, takePreload } from "./preload";

const g = globalThis as unknown as { window?: unknown };
afterEach(() => {
  delete g.window;
});

function fakeWindow(path: string, search: string, items: Record<string, Promise<unknown>>) {
  g.window = { location: { pathname: path, search }, __lrPre: { sig: path + search, items } };
  return g.window as { location: { pathname: string; search: string } };
}

describe("takePreload — 첫 화면 선요청은 한 번만, 같은 URL 에서만", () => {
  it("한 번 꺼내면 다음엔 null (이후 요청은 평소대로)", async () => {
    fakeWindow("/control-tower/", "?carriers=A", { me: Promise.resolve({ id: 1 }) });
    await expect(takePreload("me")).resolves.toEqual({ id: 1 });
    expect(takePreload("me")).toBeNull();
  });
  it("URL(필터)이 바뀌었으면 쓰지 않는다", () => {
    const w = fakeWindow("/control-tower/", "?carriers=A", { "ct.overview": Promise.resolve(1) });
    w.location.search = "?carriers=B";
    expect(takePreload("ct.overview")).toBeNull();
  });
  it("브라우저 밖·선요청 없음 → null", () => {
    expect(takePreload("me")).toBeNull();
    g.window = { location: { pathname: "/", search: "" } };
    expect(takePreload("me")).toBeNull();
  });
  it("스크립트는 Control Tower 에서만 동작하고 API 접두사를 넣는다", () => {
    const s = preloadScript("http://api.local");
    expect(s).toContain('indexOf("/control-tower")!==0)return');
    expect(s).toContain('"http://api.local"');
  });
});
