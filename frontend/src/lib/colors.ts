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

/**
 * 여러 토큰을 한 번에 rgb 로 읽는 팔레트 (지도 점 수백 개에 색을 줄 때 점마다 스타일을 읽지 않도록).
 * get(token) 은 미리 읽은 값을, scale(tokens, t) 는 토큰들 사이 연속 보간 색을 준다.
 */
export function palette(tokens: string[]) {
  const st = getComputedStyle(document.documentElement);
  const rgb = new Map(tokens.map((t) => [t, rgbaOf(st.getPropertyValue(t).trim() || "#808080")] as const));
  const fmt = (c: readonly number[]) => `rgb(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])})`;
  return {
    get: (t: string) => fmt(rgb.get(t) ?? [128, 128, 128]),
    /** tokens 순서대로 균등 구간 보간 (t: 0~1) */
    scale: (stops: string[], t: number) => {
      const x = Math.max(0, Math.min(1, t)) * (stops.length - 1);
      const i = Math.min(stops.length - 2, Math.floor(x));
      const a = rgb.get(stops[i]) ?? [128, 128, 128];
      const b = rgb.get(stops[i + 1]) ?? [128, 128, 128];
      return fmt([0, 1, 2].map((j) => a[j] + (b[j] - a[j]) * (x - i)));
    },
  };
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
