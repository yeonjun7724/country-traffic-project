"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Globe2, RotateCcw, Save } from "lucide-react";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Pill } from "@/components/common/badges";
import { DataTable } from "@/components/common/data-table";
import { popupHtml, type MapPoint } from "@/components/common/geo-map";
import { Callout, DownloadButton, Field } from "@/components/common/kit";
import { MultiSelect } from "@/components/common/multi-select";
import { PageHeader } from "@/components/common/page-header";
import { Section } from "@/components/common/section";
import { ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useFilters } from "@/lib/filters";
import { num, pct } from "@/lib/format";
import { navByKey } from "@/lib/nav";
import { useNetwork } from "@/lib/queries";
import type { Component, Proximity, Unit, UnitsView } from "@/lib/types";
import { useApi, useApiMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

const GeoMap = dynamic(() => import("@/components/common/geo-map").then((m) => m.GeoMap), {
  ssr: false,
  loading: () => <Skeleton className="h-[540px] rounded-lg" />,
});

const NAV = navByKey("network");
const GRADE_COLOR: Record<string, string> = { "Very High": "#dc2626", High: "#f97316", Moderate: "#eab308", Low: "#22c55e" };
const LISA_COLOR: Record<string, string> = {
  "High-High": "#dc2626",
  "Low-Low": "#2563eb",
  "High-Low": "#f97316",
  "Low-High": "#06b6d4",
  "Not significant": "#94a3b8",
};
const GRADE_ORDER = ["Very High", "High", "Moderate", "Low"];

function scoreColor(v: number, max: number) {
  const t = Math.max(0, Math.min(1, v / (max || 1)));
  const stops = [
    [0, [254, 240, 138]],
    [0.5, [249, 115, 22]],
    [1, [153, 27, 27]],
  ] as const;
  const i = t <= 0.5 ? 0 : 1;
  const [a, ca] = stops[i];
  const [b, cb] = stops[i + 1];
  const k = (t - a) / (b - a);
  const c = ca.map((x, j) => Math.round(x + (cb[j] - x) * k));
  return `rgb(${c.join(",")})`;
}

type ColorBy = "score" | "grade" | "lisa";
type Layer = "units" | "warehouses" | "stores";

export function NetworkScreen() {
  const { filters } = useFilters();
  const { can, me } = useWorkspace();
  const meta = useApi<{ components: Component[] }>("/api/network/meta", { staleTime: Infinity });
  const comps = useMemo(() => meta.data?.components ?? [], [meta.data]);
  const defaults = useMemo(() => Object.fromEntries(comps.map((c) => [c.key, c.default])), [comps]);
  const [w, setW] = useState<Record<string, number> | null>(null);
  const weights = w ?? defaults;
  const [routes, setRoutes] = useState<string[]>([]);
  const [colorBy, setColorBy] = useState<ColorBy>("grade");
  const [layers, setLayers] = useState<Layer[]>(["units", "warehouses"]);
  const [selected, setSelected] = useState<string[]>([]);
  const [radius, setRadius] = useState(20);

  const wq = w ? Object.fromEntries(Object.entries(w).map(([k, v]) => [k, String(v)])) : {};
  const units = useApi<UnitsView>("/api/network/units", { query: { ...wq, routes } });
  const prox = useApi<Proximity[]>("/api/network/proximity", { query: { ...wq, radius_km: radius } });
  const ops = useNetwork(filters);
  const save = useApiMutation<void, { id: number }>(() => ({ path: "/api/network/scenarios", body: weights }), {
    success: (r) => `가중치 시나리오 #${r.id} 저장 — Scenario Lab 에서 확인`,
  });

  const d = units.data;
  const shown = useMemo(() => d?.units ?? [], [d]);
  const maxScore = Math.max(0.0001, ...(d?.units ?? []).map((u) => u.score));

  const unitPoints: MapPoint[] = useMemo(
    () =>
      shown.map((u) => ({
        id: u.unitCode,
        lat: u.lat,
        lon: u.lon,
        color: colorBy === "score" ? scoreColor(u.score, maxScore) : colorBy === "grade" ? (GRADE_COLOR[u.grade] ?? "#94a3b8") : (LISA_COLOR[u.lisa_cluster] ?? "#94a3b8"),
        radius: colorBy === "grade" ? (u.grade === "Very High" ? 6.5 : u.grade === "High" ? 5.5 : 4.5) : u.lisa_cluster === "High-High" ? 6.5 : 4.5,
        html: popupHtml(u.unitName, `${u.routeName} · 외부 지표`, [
          ["취약성", u.score.toFixed(3)],
          ["등급", u.grade],
          ["LISA", u.lisa_cluster],
          ["순위", `${u.rank_sim}위${u.rank_change ? ` (${u.rank_change > 0 ? "▲" : "▼"}${Math.abs(u.rank_change)})` : ""}`],
        ]),
      })),
    [shown, colorBy, maxScore],
  );
  const storePoints: MapPoint[] = useMemo(
    () =>
      (ops.data?.stores ?? []).map((s) => ({
        id: s.store_id,
        lat: s.lat,
        lon: s.lon,
        color: "#0891b2",
        radius: 4.5,
        html: popupHtml(s.name ?? s.store_id, `${s.region ?? ""} · 배송지`, [["배송", `${num(s.shipments)}건`]]),
      })),
    [ops.data],
  );
  const mapLayers = [
    ...(layers.includes("stores") ? [{ id: "stores", points: storePoints }] : []),
    ...(layers.includes("units") ? [{ id: "units", points: unitPoints }] : []),
  ];
  const markers = layers.includes("warehouses")
    ? (ops.data?.warehouses ?? []).filter((x) => x.lat != null && x.lon != null).map((x) => ({ id: x.warehouse_id, lat: x.lat!, lon: x.lon!, label: x.name ?? x.warehouse_id }))
    : [];

  const toggle = (id: string) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const tableRows = selected.length ? (d?.units ?? []).filter((u) => selected.includes(u.unitCode)) : (d?.units ?? []);
  const sc = d?.scenario;
  const wsum = Object.values(weights).reduce((a, b) => a + b, 0);

  return (
    <>
      <PageHeader
        nav={NAV}
        title="물류 네트워크 · 외부 위험"
        description="고속도로 영업소 취약성(외부 지표)과 기업 센터·배송지를 별도 레이어로 겹쳐 봅니다."
        actions={<Pill tone="external">외부 지표 포함</Pill>}
      />
      {units.isError && <ErrorState error={units.error} onRetry={() => units.refetch()} className="mb-4" />}
      {d && !d.available && <Callout tone="danger" className="mb-4">{d.reason}</Callout>}

      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border bg-card px-3 py-2.5 shadow-card">
        <Field label="레이어">
          <ToggleGroup type="multiple" variant="outline" size="sm" value={layers} onValueChange={(v) => setLayers(v as Layer[])} aria-label="지도 레이어">
            <ToggleGroupItem value="units" className="px-2.5 text-[12px]">영업소(외부)</ToggleGroupItem>
            <ToggleGroupItem value="warehouses" className="px-2.5 text-[12px]" disabled={!me?.has_ops_data}>센터</ToggleGroupItem>
            <ToggleGroupItem value="stores" className="px-2.5 text-[12px]" disabled={!me?.has_ops_data}>배송지</ToggleGroupItem>
          </ToggleGroup>
        </Field>
        <Field label="영업소 색상">
          <Select value={colorBy} onValueChange={(v) => setColorBy(v as ColorBy)}>
            <SelectTrigger size="sm" className="w-40" aria-label="영업소 색상 기준">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="grade">취약성 4분위 등급</SelectItem>
              <SelectItem value="score">취약성 점수</SelectItem>
              <SelectItem value="lisa">LISA 클러스터</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="노선">
          <MultiSelect label="노선" options={(d?.routes ?? []).map((r) => ({ value: r, label: r }))} value={routes} onChange={setRoutes} />
        </Field>
        {selected.length > 0 && (
          <Button variant="secondary" size="sm" className="ml-auto" onClick={() => setSelected([])}>
            선택 {selected.length}개 해제
          </Button>
        )}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Section
          title="지도"
          description="영업소는 고속도로 TCS 영업소이며 기업 거점과 별개입니다. 클러스터 간 연결선은 물류 흐름이 아니므로 그리지 않습니다."
          bodyClassName="p-3"
        >
          {!d ? (
            <Skeleton className="h-[540px] rounded-lg" />
          ) : (
            <GeoMap
              layers={mapLayers}
              markers={markers}
              selected={selected}
              onPointClick={(layer, id) => layer === "units" && toggle(id)}
              height={540}
              fitKey={`${routes.join(",")}|${layers.join(",")}|${d.units.length}`}
              ariaLabel="영업소 위험 지도"
              legend={<Legend colorBy={colorBy} />}
            />
          )}
        </Section>

        <div className="space-y-4">
          <Section
            title="취약성 가중치 시뮬레이션"
            description="기본값 0.3/0.3/0.2/0.2 는 기존 산출물에서 역산·검증된 값입니다."
            bodyClassName="space-y-4"
          >
            {comps.map((c) => (
              <div key={c.key} className="space-y-1.5">
                <div className="flex items-center justify-between text-[12.5px]">
                  <span className="font-medium">{c.label}</span>
                  <span className="tabular text-muted-foreground">
                    {weights[c.key]?.toFixed(2)} <span className="text-subtle-foreground">→ {wsum ? pct((weights[c.key] ?? 0) / wsum, 0) : "—"}</span>
                  </span>
                </div>
                <Slider
                  value={[weights[c.key] ?? 0]}
                  min={0}
                  max={1}
                  step={0.05}
                  onValueChange={([v]) => setW({ ...weights, [c.key]: v })}
                  aria-label={`${c.label} 가중치`}
                />
              </div>
            ))}
            {wsum <= 0 && <p className="text-[12px] font-medium text-danger">가중치 합이 0 보다 커야 합니다.</p>}
            {sc && (
              <div className="space-y-2 rounded-lg bg-muted/50 px-3 py-2.5 text-[12px]">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-mono text-[11.5px]">{sc.id}</span>
                  {sc.is_base ? <Pill tone="success">기존 결과 재현</Pill> : <Pill tone="warning">시뮬레이션</Pill>}
                </div>
                <p className="text-muted-foreground tabular">
                  순위 변동 {num(sc.rank_changed)}개 · 등급 변경 {num(sc.grade_changed)}개 (정규화 후 합 = 1)
                </p>
              </div>
            )}
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setW(null)} disabled={!w}>
                <RotateCcw className="size-3.5" /> 기본값
              </Button>
              {can("scenario.save") && (
                <Button size="sm" onClick={() => save.mutate()} disabled={!sc || sc.is_base || save.isPending || wsum <= 0}>
                  <Save className="size-3.5" /> 시나리오 저장
                </Button>
              )}
            </div>
          </Section>

          <Section
            title="센터 주변 고위험 영업소"
            description="직선거리 근접성 지표 · 실제 이용 경로 아님"
            actions={
              <Select value={String(radius)} onValueChange={(v) => setRadius(Number(v))}>
                <SelectTrigger size="sm" className="w-32" aria-label="반경">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[10, 20, 30, 50].map((r) => (
                    <SelectItem key={r} value={String(r)}>
                      반경 {r}km
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            }
            bodyClassName="p-0"
          >
            {!prox.data ? (
              <Skeleton className="m-4 h-24" />
            ) : prox.data.length === 0 ? (
              <p className="px-4 py-6 text-[12.5px] text-muted-foreground">센터 데이터가 있어야 계산합니다.</p>
            ) : (
              <ul className="divide-y divide-border">
                {prox.data.map((p) => (
                  <li key={p.warehouse_id} className="px-4 py-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-[13px] font-medium">{p.name}</span>
                      <span className="text-[12px] text-muted-foreground tabular">영업소 {p.units_in_radius}개</span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1.5 text-[11.5px]">
                      <Pill tone={p.very_high ? "danger" : "neutral"}>Very High {p.very_high}</Pill>
                      <Pill tone={p.high_high ? "warning" : "neutral"}>High-High {p.high_high}</Pill>
                      <span className="text-subtle-foreground">
                        최근접 {p.nearest_unit} {num(p.nearest_km, 1)}km
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <Section title="노선별 평균 취약성" description="상위 15개 노선 · 막대 옆 숫자는 영업소 수" className="h-full">
            {!d ? (
              <Skeleton className="h-80" />
            ) : (
              <div style={{ height: 380 }} role="img" aria-label="노선별 평균 취약성 막대 차트">
                <ResponsiveContainer>
                  <BarChart data={d.route_summary} layout="vertical" margin={{ left: 8, right: 36, top: 4, bottom: 4 }}>
                    <XAxis type="number" hide domain={[0, "dataMax"]} />
                    <YAxis type="category" dataKey="routeName" width={96} tickLine={false} axisLine={false} tick={{ fontSize: 11.5, fill: "var(--muted-foreground)" }} />
                    <Tooltip
                      cursor={{ fill: "var(--muted)", opacity: 0.5 }}
                      content={({ active, payload }) =>
                        active && payload?.length ? (
                          <div className="rounded-lg border border-border bg-popover px-3 py-2 text-[12px] shadow-lg">
                            <div className="font-medium">{(payload[0].payload as { routeName: string }).routeName}</div>
                            <div className="text-muted-foreground tabular">
                              평균 {(payload[0].payload as { mean_score: number }).mean_score.toFixed(3)} · 영업소 {(payload[0].payload as { units: number }).units}개 · HH{" "}
                              {(payload[0].payload as { hh: number }).hh}
                            </div>
                          </div>
                        ) : null
                      }
                    />
                    <Bar dataKey="mean_score" fill="var(--chart-1)" radius={[0, 4, 4, 0]} barSize={14} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Section>
        </div>
        <div className="lg:col-span-5">
          <Section title="LISA 클러스터" description="국지적 공간 자기상관 (p<0.05)" className="h-full">
            {!d ? <Skeleton className="h-80" /> : <LisaDonut counts={d.lisa_counts} />}
          </Section>
        </div>
      </div>

      <Section
        className="mt-4"
        title={
          <span className="flex items-center gap-2">
            <Globe2 className="size-4 text-external" /> 영업소 위험 테이블
          </span>
        }
        description={`외부 지표 · ${num(tableRows.length)}개${selected.length ? " (지도 선택)" : ""} · 행을 선택하면 지도에 강조됩니다`}
        actions={
          <DownloadButton
            path="/api/network/units.csv"
            params={new URLSearchParams([...routes.map((r) => ["routes", r] as [string, string]), ...Object.entries(wq)])}
            filename="units_risk.csv"
            label="CSV"
          />
        }
      >
        {!d ? <Skeleton className="h-80" /> : <UnitsTable rows={tableRows} selected={selected} onSelected={setSelected} />}
      </Section>
    </>
  );
}

function Legend({ colorBy }: { colorBy: ColorBy }) {
  const items = colorBy === "lisa" ? Object.entries(LISA_COLOR) : colorBy === "grade" ? GRADE_ORDER.map((g) => [g, GRADE_COLOR[g]] as [string, string]) : null;
  return (
    <div>
      <div className="mb-1 font-medium text-foreground">{colorBy === "lisa" ? "LISA 클러스터" : colorBy === "grade" ? "취약성 등급" : "취약성 점수"}</div>
      {items ? (
        <div className="flex flex-wrap gap-x-2.5 gap-y-1 text-muted-foreground">
          {items.map(([k, c]) => (
            <span key={k} className="flex items-center gap-1">
              <span className="size-2 rounded-full" style={{ background: c }} />
              {k}
            </span>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-1.5 text-muted-foreground">
          낮음
          <span className="h-1.5 w-24 rounded-full" style={{ background: "linear-gradient(90deg,#fef08a,#f97316,#991b1b)" }} />
          높음
        </div>
      )}
      <div className="mt-1 flex items-center gap-1 text-muted-foreground">
        <span className="size-2 rounded-full bg-cyan-600" /> 배송지(선택 시)
      </div>
    </div>
  );
}

function LisaDonut({ counts }: { counts: Record<string, number> }) {
  const data = Object.entries(counts).map(([k, v]) => ({ name: k, value: v }));
  const total = data.reduce((a, b) => a + b.value, 0);
  return (
    <div className="flex flex-col items-center gap-3 sm:flex-row">
      <div className="relative h-56 w-56 shrink-0" role="img" aria-label="LISA 클러스터 비중 도넛 차트">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={62} outerRadius={92} paddingAngle={1.5} stroke="none" isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.name} fill={LISA_COLOR[d.name] ?? "#94a3b8"} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[22px] font-semibold tabular">{total}</span>
          <span className="text-[11px] text-muted-foreground">영업소</span>
        </div>
      </div>
      <ul className="w-full space-y-1.5 text-[12.5px]">
        {data
          .sort((a, b) => b.value - a.value)
          .map((d) => (
            <li key={d.name} className="flex items-center gap-2">
              <span className="size-2.5 rounded-sm" style={{ background: LISA_COLOR[d.name] ?? "#94a3b8" }} />
              <span className="flex-1">{d.name}</span>
              <span className="tabular font-medium">{d.value}</span>
              <span className="w-12 text-right text-muted-foreground tabular">{pct(d.value / (total || 1), 0)}</span>
            </li>
          ))}
      </ul>
    </div>
  );
}

const COLS: ColumnDef<Unit, unknown>[] = [
  {
    accessorKey: "unitName",
    header: "영업소",
    cell: (c) => (
      <div className="leading-tight">
        <div className="font-medium">{c.row.original.unitName}</div>
        <div className="text-[11px] text-muted-foreground">{c.row.original.routeName}</div>
      </div>
    ),
  },
  { accessorKey: "score", header: "취약성", meta: { align: "right" }, cell: (c) => (c.getValue() as number).toFixed(3) },
  {
    accessorKey: "grade",
    header: "등급",
    cell: (c) => {
      const g = c.getValue() as string;
      return (
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full" style={{ background: GRADE_COLOR[g] ?? "#94a3b8" }} />
          {g}
        </span>
      );
    },
  },
  {
    accessorKey: "lisa_cluster",
    header: "LISA",
    cell: (c) => <span className={cn((c.getValue() as string) === "High-High" && "font-medium text-danger")}>{c.getValue() as string}</span>,
  },
  { accessorKey: "rank_sim", header: "순위", meta: { align: "right" } },
  {
    accessorKey: "rank_change",
    header: "변동",
    meta: { align: "right" },
    cell: (c) => {
      const v = c.getValue() as number;
      return v ? <span className={v > 0 ? "text-danger" : "text-success"}>{v > 0 ? `▲${v}` : `▼${-v}`}</span> : <span className="text-subtle-foreground">—</span>;
    },
  },
  { accessorKey: "mean_freight_345_share", header: "화물 비율", meta: { align: "right" }, cell: (c) => pct(c.getValue() as number) },
  { accessorKey: "mean_freight_345_traffic", header: "화물량(일)", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
  { accessorKey: "traffic_volatility", header: "변동계수", meta: { align: "right" }, cell: (c) => num(c.getValue() as number, 3) },
];

function UnitsTable({ rows, selected, onSelected }: { rows: Unit[]; selected: string[]; onSelected: (v: string[]) => void }) {
  return <DataTable data={rows} columns={COLS} rowKey={(r) => r.unitCode} selected={selected} onSelectedChange={onSelected} height={420} ariaLabel="영업소 위험 목록" />;
}
