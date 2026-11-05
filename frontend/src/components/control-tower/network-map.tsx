"use client";

import * as maplibregl from "maplibre-gl";
import type { ErrorEvent, GeoJSONSource, Map as MLMap, StyleSpecification } from "maplibre-gl";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState } from "react";

import type { Schemas } from "@/lib/api";
import { pct, won } from "@/lib/format";

type Store = Schemas["StorePoint"];
type Warehouse = Schemas["WarehousePoint"];

const STYLE = {
  light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
};
/** 배경지도 로딩 실패 시 — 점·센터는 계속 보이도록 빈 배경 스타일 */
const BLANK = (dark: boolean): StyleSpecification => ({
  version: 8,
  sources: {},
  layers: [{ id: "bg", type: "background", paint: { "background-color": dark ? "#151821" : "#eef2f7" } }],
});

// 모듈 워커를 정적 경로에서 로드 (scripts/copy-vendor.mjs 가 빌드 시 복사)
if (typeof window !== "undefined") maplibregl.setWorkerUrl("/vendor/maplibre-gl-worker.mjs");

const LATE_COLORS: [number, string][] = [
  [0, "#16a34a"],
  [0.05, "#84cc16"],
  [0.1, "#f59e0b"],
  [0.2, "#ef4444"],
  [0.3, "#b91c1c"],
];

function storesGeo(stores: Store[]) {
  return {
    type: "FeatureCollection" as const,
    features: stores.map((s) => ({
      type: "Feature" as const,
      id: s.store_id,
      geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
      properties: {
        id: s.store_id,
        name: s.name ?? s.store_id,
        region: s.region ?? "",
        shipments: s.shipments ?? 0,
        late: s.late_rate ?? -1,
        cost: s.cost ?? null,
        cpo: s.cost_per_order ?? null,
      },
    })),
  };
}

export function NetworkMap({
  stores,
  idle,
  warehouses,
  selected,
  onToggle,
  height = 460,
}: {
  stores: Store[];
  idle: Store[];
  warehouses: Warehouse[];
  selected: string[];
  onToggle: (id: string) => void;
  height?: number;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);
  const toggleRef = useRef(onToggle);
  toggleRef.current = onToggle;
  const { resolvedTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  const [ready, setReady] = useState(0); // 스타일이 (재)로드될 때마다 증가 → 레이어 재구성
  const [basemapFailed, setBasemapFailed] = useState(false);
  const fitted = useRef(false);

  // 지도 생성 / 테마 변경 시 스타일 교체
  useEffect(() => {
    if (!el.current) return;
    if (!map.current) {
      const m = new maplibregl.Map({
        container: el.current,
        style: STYLE[dark ? "dark" : "light"],
        center: [127.8, 36.3],
        zoom: 5.6,
        attributionControl: { compact: true },
        cooperativeGestures: false,
        dragRotate: false,
        pitchWithRotate: false,
      });
      m.touchZoomRotate.disableRotation();
      m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      m.on("style.load", () => setReady((n) => n + 1));
      m.on("error", (e: ErrorEvent) => {
        // 배경 타일/스타일 오류 → 빈 배경으로 전환 (데이터 레이어는 유지)
        if (!m.isStyleLoaded() && !(e as { sourceId?: string }).sourceId) {
          setBasemapFailed(true);
          m.setStyle(BLANK(dark));
        }
      });
      map.current = m;
    } else {
      map.current.setStyle(basemapFailed ? BLANK(dark) : STYLE[dark ? "dark" : "light"]);
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

  // 레이어·이벤트 구성 (스타일 로드마다)
  useEffect(() => {
    const m = map.current;
    // style.load 이후(ready>0)면 배경 타일이 로딩 중이어도 레이어 추가 가능 (isStyleLoaded 는 타일 로딩 중 false)
    if (!m || !ready || !m.getStyle()) return;
    if (!m.getSource("stores")) {
      m.addSource("idle", { type: "geojson", data: storesGeo([]) });
      m.addSource("stores", { type: "geojson", data: storesGeo([]), promoteId: "id" });
      m.addLayer({
        id: "idle",
        type: "circle",
        source: "idle",
        paint: {
          "circle-radius": 4,
          "circle-color": dark ? "#475569" : "#cbd5e1",
          "circle-stroke-width": 1,
          "circle-stroke-color": dark ? "#1e293b" : "#ffffff",
        },
      });
      m.addLayer({
        id: "stores-sel",
        type: "circle",
        source: "stores",
        filter: ["in", ["get", "id"], ["literal", []]],
        paint: {
          "circle-radius": ["+", ["min", 22, ["+", 6, ["*", 1.5, ["sqrt", ["get", "shipments"]]]]], 6],
          "circle-color": "rgba(37,99,235,0.18)",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#2563eb",
        },
      });
      m.addLayer({
        id: "stores",
        type: "circle",
        source: "stores",
        paint: {
          "circle-radius": ["min", 22, ["+", 5, ["*", 1.5, ["sqrt", ["get", "shipments"]]]]],
          "circle-color": [
            "case",
            ["<", ["get", "late"], 0],
            "#94a3b8",
            ["interpolate", ["linear"], ["get", "late"], ...LATE_COLORS.flat()],
          ],
          "circle-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 1, 0.85],
          "circle-stroke-width": ["case", ["boolean", ["feature-state", "hover"], false], 2, 1],
          "circle-stroke-color": dark ? "#0f172a" : "#ffffff",
        },
      });

      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, maxWidth: "260px" });
      let hoverId: string | number | undefined;
      m.on("mousemove", "stores", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        m.getCanvas().style.cursor = "pointer";
        if (hoverId !== undefined) m.setFeatureState({ source: "stores", id: hoverId }, { hover: false });
        hoverId = f.id;
        if (hoverId !== undefined) m.setFeatureState({ source: "stores", id: hoverId }, { hover: true });
        const p = f.properties as Record<string, unknown>;
        const late = Number(p.late);
        popup
          .setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number])
          .setHTML(
            `<div style="padding:10px 12px;font-size:12.5px;line-height:1.5">
              <div style="font-weight:600;font-size:13px">${esc(String(p.name))}</div>
              <div style="color:var(--muted-foreground)">${esc(String(p.region))} · ${esc(String(p.id))}</div>
              <div style="margin-top:6px;display:grid;grid-template-columns:auto auto;gap:2px 14px">
                <span style="color:var(--muted-foreground)">배송</span><b style="text-align:right">${Number(p.shipments).toLocaleString()}건</b>
                <span style="color:var(--muted-foreground)">지연율</span><b style="text-align:right">${late < 0 ? "판정 불가" : pct(late)}</b>
                <span style="color:var(--muted-foreground)">운송비</span><b style="text-align:right">${p.cost == null ? "—" : `${won(Number(p.cost))}원`}</b>
              </div>
              <div style="margin-top:6px;color:var(--subtle-foreground);font-size:11px">클릭하여 선택 · 원장에 반영</div>
            </div>`,
          )
          .addTo(m);
      });
      m.on("mouseleave", "stores", () => {
        m.getCanvas().style.cursor = "";
        if (hoverId !== undefined) m.setFeatureState({ source: "stores", id: hoverId }, { hover: false });
        hoverId = undefined;
        popup.remove();
      });
      m.on("click", "stores", (e) => {
        const id = e.features?.[0]?.properties?.id;
        if (id) toggleRef.current(String(id));
      });
    }
    (m.getSource("stores") as GeoJSONSource).setData(storesGeo(stores));
    (m.getSource("idle") as GeoJSONSource).setData(storesGeo(idle));
    m.setFilter("stores-sel", ["in", ["get", "id"], ["literal", selected]]);
  }, [ready, stores, idle, selected, dark]);

  // 센터: HTML 마커 (한글 라벨 — 배경지도 글꼴 의존 없음)
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    markers.current.forEach((mk) => mk.remove());
    markers.current = warehouses
      .filter((w) => w.lat != null && w.lon != null)
      .map((w) => {
        const node = document.createElement("div");
        node.className =
          "flex items-center gap-1.5 rounded-full border border-white/70 bg-slate-900 py-0.5 pl-0.5 pr-2 text-[11px] font-semibold text-white shadow-md dark:border-slate-700";
        node.innerHTML = `<span style="display:inline-flex;width:18px;height:18px;border-radius:9999px;background:#2563eb;align-items:center;justify-content:center"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5"><path d="M3 21V9l9-6 9 6v12"/><path d="M9 21v-6h6v6"/></svg></span>${esc(w.name ?? w.warehouse_id)}`;
        node.setAttribute("role", "img");
        node.setAttribute("aria-label", `센터 ${w.name ?? w.warehouse_id}`);
        return new maplibregl.Marker({ element: node, anchor: "left", offset: [-9, 0] }).setLngLat([w.lon!, w.lat!]).addTo(m);
      });
  }, [warehouses]);

  // 데이터 범위로 맞춤 (최초 1회 + 데이터 집합이 바뀌었을 때)
  const sig = `${stores.length}:${idle.length}:${warehouses.length}`;
  useEffect(() => {
    const m = map.current;
    const pts = [...stores, ...idle].map((s) => [s.lon, s.lat] as [number, number]);
    warehouses.forEach((w) => w.lat != null && w.lon != null && pts.push([w.lon, w.lat]));
    if (!m || pts.length === 0) return;
    const b = pts.reduce((bb, p) => bb.extend(p), new maplibregl.LngLatBounds(pts[0], pts[0]));
    m.fitBounds(b, { padding: 48, maxZoom: 9, duration: fitted.current ? 400 : 0 });
    fitted.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);

  return (
    <div className="relative overflow-hidden rounded-lg border border-border" style={{ height }}>
      <div ref={el} className="h-full w-full" role="application" aria-label="배송 네트워크 지도" />
      <Legend />
      {basemapFailed && (
        <div className="absolute right-12 top-2 rounded-md bg-card/90 px-2 py-1 text-[11px] text-muted-foreground shadow">
          배경지도를 불러오지 못해 단순 배경으로 표시합니다
        </div>
      )}
    </div>
  );
}

function Legend() {
  return (
    <div className="pointer-events-none absolute bottom-2 left-2 rounded-lg border border-border bg-card/92 px-3 py-2 text-[11px] shadow-sm backdrop-blur">
      <div className="mb-1 font-medium text-foreground">배송지 지연율</div>
      <div className="flex items-center gap-1.5">
        <span className="tabular text-muted-foreground">0%</span>
        <span
          className="h-1.5 w-28 rounded-full"
          style={{ background: `linear-gradient(90deg, ${LATE_COLORS.map(([v, c]) => `${c} ${(v / 0.3) * 100}%`).join(",")})` }}
        />
        <span className="tabular text-muted-foreground">30%+</span>
      </div>
      <div className="mt-1.5 flex items-center gap-3 text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="size-2 rounded-full bg-slate-300 dark:bg-slate-600" /> 기간 내 배송 없음
        </span>
        <span>원 크기 = 배송 건수</span>
      </div>
    </div>
  );
}

function esc(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}
