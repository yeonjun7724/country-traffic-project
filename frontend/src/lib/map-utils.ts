/**
 * 지도 공용 타입·문자열 도우미 — maplibre 를 import 하지 않는다.
 * 화면 컴포넌트는 여기서 가져오고, 지도 본체(common/geo-map)는 next/dynamic 으로만 불러온다.
 * (geo-map 을 정적 import 하면 maplibre ~1MB 가 페이지 번들에 들어간다)
 */

export type MapPoint = { id: string; lat: number; lon: number; color: string; radius?: number; html?: string };
export type PointLayer = { id: string; points: MapPoint[]; opacity?: number; stroke?: boolean };
export type MapLine = { id: string; coords: [number, number][]; color: string; width?: number; html?: string };
export type MapMarker = { id: string; lat: number; lon: number; label: string; tone?: "primary" | "dark" };

export function esc(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

/** 팝업 HTML (토큰 색 사용) */
export function popupHtml(title: string, sub: string, rows: [string, string][]) {
  return `<div style="padding:10px 12px;font-size:13px;line-height:1.5">
    <div style="font-weight:600;font-size:13px">${esc(title)}</div>
    <div style="color:var(--muted-foreground)">${esc(sub)}</div>
    <div style="margin-top:6px;display:grid;grid-template-columns:auto auto;gap:2px 14px">
      ${rows.map(([k, v]) => `<span style="color:var(--muted-foreground)">${esc(k)}</span><b style="text-align:right">${esc(v)}</b>`).join("")}
    </div></div>`;
}
