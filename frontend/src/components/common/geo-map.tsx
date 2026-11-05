"use client";

import * as maplibregl from "maplibre-gl";
import type { ErrorEvent, GeoJSONSource, Map as MLMap, StyleSpecification } from "maplibre-gl";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

if (typeof window !== "undefined") maplibregl.setWorkerUrl("/vendor/maplibre-gl-worker.mjs");

const STYLE = {
  light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
};
const BLANK = (dark: boolean): StyleSpecification => ({
  version: 8,
  sources: {},
  layers: [{ id: "bg", type: "background", paint: { "background-color": dark ? "#151821" : "#eef2f7" } }],
});

export type MapPoint = { id: string; lat: number; lon: number; color: string; radius?: number; html?: string };
export type PointLayer = { id: string; points: MapPoint[]; opacity?: number; stroke?: boolean };
export type MapLine = { id: string; coords: [number, number][]; color: string; width?: number; html?: string };
export type MapMarker = { id: string; lat: number; lon: number; label: string; tone?: "primary" | "dark" };

/**
 * 범용 지도: 원형 점 레이어(사전 계산 색) · 선(경로) · HTML 마커(한글 라벨) · 선택 강조 · 클릭 선택.
 * 배경지도 실패 시 단순 배경으로 전환하고 데이터 레이어는 유지.
 */
export function GeoMap({
  layers = [],
  lines = [],
  markers = [],
  selected = [],
  onPointClick,
  height = 480,
  legend,
  className,
  fitKey,
  ariaLabel = "지도",
}: {
  layers?: PointLayer[];
  lines?: MapLine[];
  markers?: MapMarker[];
  selected?: string[];
  onPointClick?: (layerId: string, id: string) => void;
  height?: number;
  legend?: React.ReactNode;
  className?: string;
  /** 바뀌면 데이터 범위로 다시 맞춤 */
  fitKey?: string;
  ariaLabel?: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const mk = useRef<maplibregl.Marker[]>([]);
  const clickRef = useRef(onPointClick);
  clickRef.current = onPointClick;
  const { resolvedTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  const [ready, setReady] = useState(0);
  const [failed, setFailed] = useState(false);
  const known = useRef(new Set<string>());

  useEffect(() => {
    if (!el.current) return;
    if (!map.current) {
      const m = new maplibregl.Map({
        container: el.current,
        style: STYLE[dark ? "dark" : "light"],
        center: [127.8, 36.3],
        zoom: 5.6,
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
      });
      m.touchZoomRotate.disableRotation();
      m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      m.on("style.load", () => {
        known.current = new Set();
        setReady((n) => n + 1);
      });
      m.on("error", (e: ErrorEvent) => {
        if (!m.isStyleLoaded() && !(e as { sourceId?: string }).sourceId) {
          setFailed(true);
          m.setStyle(BLANK(dark));
        }
      });
      map.current = m;
    } else {
      map.current.setStyle(failed ? BLANK(dark) : STYLE[dark ? "dark" : "light"]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dark]);

  useEffect(
    () => () => {
      map.current?.remove();
      map.current = null;
    },
    [],
  );

  // 선
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !m.getStyle()) return;
    const data = {
      type: "FeatureCollection" as const,
      features: lines.map((l) => ({
        type: "Feature" as const,
        geometry: { type: "LineString" as const, coordinates: l.coords },
        properties: { id: l.id, color: l.color, width: l.width ?? 3 },
      })),
    };
    if (!m.getSource("lines")) {
      m.addSource("lines", { type: "geojson", data });
      m.addLayer({
        id: "lines",
        type: "line",
        source: "lines",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": ["get", "color"], "line-width": ["get", "width"], "line-opacity": 0.85 },
      });
    } else (m.getSource("lines") as GeoJSONSource).setData(data);
  }, [ready, lines]);

  // 점 레이어
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !m.getStyle()) return;
    const ids = new Set(layers.map((l) => l.id));
    for (const old of known.current) {
      if (!ids.has(old)) {
        if (m.getLayer(old)) m.removeLayer(old);
        if (m.getLayer(`${old}-sel`)) m.removeLayer(`${old}-sel`);
        if (m.getSource(old)) m.removeSource(old);
        known.current.delete(old);
      }
    }
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, maxWidth: "280px" });
    for (const l of layers) {
      const data = {
        type: "FeatureCollection" as const,
        features: l.points.map((p) => ({
          type: "Feature" as const,
          id: p.id,
          geometry: { type: "Point" as const, coordinates: [p.lon, p.lat] },
          properties: { id: p.id, color: p.color, r: p.radius ?? 5, html: p.html ?? "" },
        })),
      };
      if (!m.getSource(l.id)) {
        m.addSource(l.id, { type: "geojson", data, promoteId: "id" });
        m.addLayer({
          id: `${l.id}-sel`,
          type: "circle",
          source: l.id,
          filter: ["in", ["get", "id"], ["literal", []]],
          paint: {
            "circle-radius": ["+", ["get", "r"], 6],
            "circle-color": "rgba(37,99,235,0.16)",
            "circle-stroke-width": 2,
            "circle-stroke-color": "#2563eb",
          },
        });
        m.addLayer({
          id: l.id,
          type: "circle",
          source: l.id,
          paint: {
            "circle-radius": ["get", "r"],
            "circle-color": ["get", "color"],
            "circle-opacity": l.opacity ?? 0.88,
            "circle-stroke-width": l.stroke === false ? 0 : 1,
            "circle-stroke-color": dark ? "#0f172a" : "#ffffff",
          },
        });
        m.on("mousemove", l.id, (e) => {
          const f = e.features?.[0];
          const html = f?.properties?.html as string | undefined;
          m.getCanvas().style.cursor = clickRef.current ? "pointer" : "";
          if (f && html) popup.setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number]).setHTML(html).addTo(m);
        });
        m.on("mouseleave", l.id, () => {
          m.getCanvas().style.cursor = "";
          popup.remove();
        });
        m.on("click", l.id, (e) => {
          const id = e.features?.[0]?.properties?.id;
          if (id && clickRef.current) clickRef.current(l.id, String(id));
        });
        known.current.add(l.id);
      } else (m.getSource(l.id) as GeoJSONSource).setData(data);
      m.setFilter(`${l.id}-sel`, ["in", ["get", "id"], ["literal", selected]]);
    }
    return () => {
      popup.remove();
    };
  }, [ready, layers, selected, dark]);

  // HTML 마커
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    mk.current.forEach((x) => x.remove());
    mk.current = markers.map((w) => {
      const node = document.createElement("div");
      node.className =
        "flex items-center gap-1.5 rounded-full border border-white/70 bg-slate-900 py-0.5 pl-0.5 pr-2 text-[11px] font-semibold text-white shadow-md dark:border-slate-700";
      node.innerHTML = `<span style="display:inline-flex;width:18px;height:18px;border-radius:9999px;background:#2563eb;align-items:center;justify-content:center"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5"><path d="M3 21V9l9-6 9 6v12"/><path d="M9 21v-6h6v6"/></svg></span>${esc(w.label)}`;
      node.setAttribute("role", "img");
      node.setAttribute("aria-label", w.label);
      return new maplibregl.Marker({ element: node, anchor: "left", offset: [-9, 0] }).setLngLat([w.lon, w.lat]).addTo(m);
    });
  }, [markers]);

  // 범위 맞춤
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const pts: [number, number][] = [];
    layers.forEach((l) => l.points.forEach((p) => pts.push([p.lon, p.lat])));
    lines.forEach((l) => l.coords.forEach((c) => pts.push(c)));
    markers.forEach((w) => pts.push([w.lon, w.lat]));
    if (!pts.length) return;
    const b = pts.reduce((bb, p) => bb.extend(p), new maplibregl.LngLatBounds(pts[0], pts[0]));
    m.fitBounds(b, { padding: 48, maxZoom: 11, duration: 300 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey]);

  return (
    <div className={cn("relative overflow-hidden rounded-lg border border-border", className)} style={{ height }}>
      <div ref={el} className="h-full w-full" role="application" aria-label={ariaLabel} />
      {legend && (
        <div className="pointer-events-none absolute bottom-2 left-2 max-w-[70%] rounded-lg border border-border bg-card/92 px-3 py-2 text-[11px] shadow-sm backdrop-blur">
          {legend}
        </div>
      )}
      {failed && (
        <div className="absolute right-12 top-2 rounded-md bg-card/90 px-2 py-1 text-[11px] text-muted-foreground shadow">
          배경지도를 불러오지 못해 단순 배경으로 표시합니다
        </div>
      )}
    </div>
  );
}

export function esc(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

/** 팝업 HTML (토큰 색 사용) */
export function popupHtml(title: string, sub: string, rows: [string, string][]) {
  return `<div style="padding:10px 12px;font-size:12.5px;line-height:1.5">
    <div style="font-weight:600;font-size:13px">${esc(title)}</div>
    <div style="color:var(--muted-foreground)">${esc(sub)}</div>
    <div style="margin-top:6px;display:grid;grid-template-columns:auto auto;gap:2px 14px">
      ${rows.map(([k, v]) => `<span style="color:var(--muted-foreground)">${esc(k)}</span><b style="text-align:right">${esc(v)}</b>`).join("")}
    </div></div>`;
}
