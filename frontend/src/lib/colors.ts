"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

/**
 * 디자인 토큰(app/globals.css 의 CSS 변수) → 실제 색.
 * 차트(SVG)는 `var(--토큰)` 을 그대로 쓰면 되지만, 지도(maplibre)는 CSS 변수·oklch 를 해석하지 못하므로 rgb 로 바꿔 넘긴다.
 * 변환은 1×1 캔버스에 칠해 읽는 방식 (브라우저가 아는 모든 색 문법 지원).
 */
const cache = new Map<string, [number, number, number, number]>();
let ctx: CanvasRenderingContext2D | null = null;

function rgbaOf(raw: string): [number, number, number, number] {
  const hit = cache.get(raw);
  if (hit) return hit;
  if (!ctx) {
    const c = document.createElement("canvas");
    c.width = c.height = 1;
    ctx = c.getContext("2d", { willReadFrequently: true });
  }
  if (!ctx) return [128, 128, 128, 1];
  ctx.clearRect(0, 0, 1, 1);
  ctx.fillStyle = "#808080";
  ctx.fillStyle = raw;
  ctx.fillRect(0, 0, 1, 1);
  const d = ctx.getImageData(0, 0, 1, 1).data;
  const v: [number, number, number, number] = [d[0], d[1], d[2], +(d[3] / 255).toFixed(3)];
  cache.set(raw, v);
  return v;
}

/** 토큰 이름(예: "--ext-3") → "rgb(r,g,b)" / alpha 지정 시 "rgba(...)". 브라우저 밖에서는 회색. */
export function cssColor(token: string, alpha?: number): string {
  if (typeof document === "undefined") return "rgb(128,128,128)";
  const raw = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  const [r, g, b, a] = rgbaOf(raw || "#808080");
  const al = alpha ?? a;
  return al >= 1 ? `rgb(${r},${g},${b})` : `rgba(${r},${g},${b},${al})`;
}

/** 두 토큰 사이 선형 보간 (연속 척도: 0 → a, 1 → b) */
export function mixColor(a: string, b: string, t: number): string {
  const ca = rgbaOf(getComputedStyle(document.documentElement).getPropertyValue(a).trim());
  const cb = rgbaOf(getComputedStyle(document.documentElement).getPropertyValue(b).trim());
  const k = Math.max(0, Math.min(1, t));
  const c = [0, 1, 2].map((i) => Math.round(ca[i] + (cb[i] - ca[i]) * k));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

/** 테마(라이트/다크)가 바뀔 때마다 다시 계산되는 색 집합. 첫 렌더(서버·하이드레이션)에서는 null. */
export function useCssColors<K extends string>(tokens: Record<K, string>): Record<K, string> | null {
  const { resolvedTheme } = useTheme();
  const [colors, setColors] = useState<Record<K, string> | null>(null);
  const key = JSON.stringify(tokens);
  useEffect(() => {
    const t = JSON.parse(key) as Record<K, string>;
    setColors(Object.fromEntries(Object.entries(t).map(([k, v]) => [k, cssColor(v as string)])) as Record<K, string>);
  }, [key, resolvedTheme]);
  return colors;
}
