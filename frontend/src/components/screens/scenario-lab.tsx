"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Check, Copy, Loader2, Save, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { KindBadge, Pill } from "@/components/common/badges";
import { FilterBar } from "@/components/common/filter-bar";
import { Callout, DownloadButton, Field, LineTabs, NumberField, STATUS_LABEL, StatTile, useUrlTab } from "@/components/common/kit";
import { PageHeader } from "@/components/common/page-header";
import { Section } from "@/components/common/section";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch } from "@/lib/api";
import { filterQuery, useFilters, type Filters } from "@/lib/filters";
import { dateTimeLabel, isNum, num, pct, won } from "@/lib/format";
import { navByKey } from "@/lib/nav";
import { useFilterMeta } from "@/lib/queries";
import type { Compare, EngineResult, Outage, ScenarioDetail, ScenarioInput, ScenarioRow, Sens } from "@/lib/types";
import { useApi, useApiMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

import { SimpleTable } from "./transportation";

const NAV = navByKey("scenario-lab");
const PRESETS: Record<string, Partial<ScenarioInput>> = {
  "경유가 +5%": { diesel_pct: 5 },
  "경유가 +10%": { diesel_pct: 10 },
  "경유가 +20%": { diesel_pct: 20 },
  "수요 +10%": { demand_pct: 10 },
  "수요 +30%": { demand_pct: 30 },
  "단가 +5%": { rate_pct: 5 },
  "차량 -2대": { fleet_change: -2 },
};
const BASE: ScenarioInput = { name: "Scenario", diesel_pct: 0, demand_pct: 0, rate_pct: 0, fleet_change: 0, trips_per_vehicle_day: 1 };
const KIND_LABEL: Record<string, string> = { cost_scenario: "비용·운행", warehouse_outage: "센터 중단", route_plan: "배송 계획", risk_weights: "위험 가중치" };
const CONTRIB_LABEL: Record<string, string> = { 경유가: "경유", "운송 단가": "단가", "물동량(운행 증가)": "물량", 상호작용: "상호" };

export function ScenarioLabScreen() {
  const [tab, setTab] = useUrlTab(["cost", "outage", "saved", "scope"]);
  return (
    <>
      <PageHeader nav={NAV} title="시나리오 분석 · 승인" description="Baseline(업로드 실적) 대비 단순 가정 기반 추정 — 저장·복제·승인까지 기록합니다." />
      <LineTabs
        value={tab}
        onChange={setTab}
        items={[
          { v: "cost", label: "비용 · 운행 시나리오" },
          { v: "outage", label: "센터 중단" },
          { v: "saved", label: "저장된 시나리오 · 승인" },
          { v: "scope", label: "지원 범위" },
        ]}
      />
      {tab === "cost" && <CostTab />}
      {tab === "outage" && <OutageTab />}
      {tab === "saved" && <SavedTab />}
      {tab === "scope" && <ScopeTab />}
    </>
  );
}

// ── 비용·운행 ─────────────────────────────────────────────────────────
function Editor({ tag, value, onChange, tone }: { tag: string; value: ScenarioInput; onChange: (v: ScenarioInput) => void; tone: string }) {
  const set = (k: keyof ScenarioInput, v: number) => onChange({ ...value, [k]: v });
  return (
    <section className="rounded-xl border border-border bg-card shadow-card">
      <header className="flex items-center gap-2 border-b border-border px-4 py-2.5">
        <span className={cn("flex size-6 items-center justify-center rounded-md text-[12px] font-bold text-white", tone)}>{tag}</span>
        <Input value={value.name} onChange={(e) => onChange({ ...value, name: e.target.value.slice(0, 100) })} className="h-8 flex-1 border-transparent px-1 text-[14px] font-semibold shadow-none hover:border-input focus-visible:border-input" aria-label={`시나리오 ${tag} 이름`} />
        <Select value="" onValueChange={(p) => onChange({ ...BASE, ...PRESETS[p], name: p })}>
          <SelectTrigger size="sm" className="w-28" aria-label={`시나리오 ${tag} 프리셋`}>
            <SelectValue placeholder="프리셋" />
          </SelectTrigger>
          <SelectContent>
            {Object.keys(PRESETS).map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </header>
      <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 xl:grid-cols-5">
        <NumberField id={`d${tag}`} label="경유가 변화" value={value.diesel_pct} onChange={(v) => set("diesel_pct", v)} min={-50} max={200} suffix="%" />
        <NumberField id={`r${tag}`} label="연료 외 단가" value={value.rate_pct} onChange={(v) => set("rate_pct", v)} min={-50} max={200} suffix="%" />
        <NumberField id={`q${tag}`} label="물동량 변화" value={value.demand_pct} onChange={(v) => set("demand_pct", v)} min={-50} max={300} suffix="%" />
        <NumberField id={`f${tag}`} label="가용 차량 증감" value={value.fleet_change} onChange={(v) => set("fleet_change", Math.round(v))} min={-100} max={100} suffix="대" />
        <NumberField id={`t${tag}`} label="1일 운행(가정)" value={value.trips_per_vehicle_day} onChange={(v) => set("trips_per_vehicle_day", Math.round(v))} min={1} max={5} suffix="회" />
      </div>
    </section>
  );
}

function useDebounce<T>(v: T, ms = 350) {
  const [d, setD] = useState(v);
  const k = JSON.stringify(v);
  useEffect(() => {
    const t = setTimeout(() => setD(v), ms);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [k, ms]);
  return d;
}

function CostTab() {
  const { filters } = useFilters();
  const { can } = useWorkspace();
  const [a, setA] = useState<ScenarioInput>({ ...BASE, name: "경유가 +10%", diesel_pct: 10 });
  const [b, setB] = useState<ScenarioInput>({ ...BASE, name: "경유가 +10% · 수요 +30%", diesel_pct: 10, demand_pct: 30 });
  const body = useDebounce({ a, b });
  const cmp = useCompare(body, filters);
  const sens = useApi<Sens[]>("/api/scenarios/sensitivity", { filters, staleTime: 120_000 });
  const save = useApiMutation<void, { ids: number[] }>(() => ({ path: "/api/scenarios/compare/save", body: { a, b }, query: filterQ(filters) }), {
    success: (r) => `시나리오 #${r.ids.join(", #")} 저장 — '저장된 시나리오'에서 확인`,
  });
  const d = cmp.data;

  return (
    <div className="space-y-4">
      <FilterBar />
      <Callout tone="info">
        결과는 <b>단순 가정 기반 추정</b>입니다 (선형 비례·운행 단위 용량 가정, 최적화 아님). Baseline 은 선택 기간의 업로드 실적이며, 절감률을 임의로 제시하지 않습니다.
      </Callout>
      <div className="grid gap-4 xl:grid-cols-2">
        <Editor tag="A" value={a} onChange={setA} tone="bg-blue-600" />
        <Editor tag="B" value={b} onChange={setB} tone="bg-violet-600" />
      </div>
      {cmp.isError && <ErrorState error={cmp.error} />}
      {!d ? (
        <Skeleton className="h-80" />
      ) : d.status !== "ok" ? (
        <EmptyState title="Baseline 이 될 배송 실적이 없습니다" description={d.reason} />
      ) : (
        <div className={cn("space-y-4", cmp.isFetching && "opacity-70 transition-opacity")}>
          <div className="grid gap-3 md:grid-cols-3">
            <StatTile label="Baseline 총 운송비 (실적)" value={won(d.a.baseline.total)} unit="원" sub={<KindBadge kind="observed" />} />
            <ScenarioTile r={d.a} tag="A" tone="text-blue-600 dark:text-blue-400" />
            <ScenarioTile r={d.b} tag="B" tone="text-violet-600 dark:text-violet-400" />
          </div>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
            <Section title="Baseline 대비 비교" bodyClassName="p-0">
              <table className="w-full text-[12.5px]">
                <thead className="text-[11.5px] text-muted-foreground">
                  <tr className="border-b border-border">
                    <th className="px-4 py-2 text-left font-medium">지표</th>
                    <th className="px-3 py-2 text-right font-medium">Baseline</th>
                    <th className="px-3 py-2 text-right font-medium text-blue-600 dark:text-blue-400">A</th>
                    <th className="px-4 py-2 text-right font-medium text-violet-600 dark:text-violet-400">B</th>
                  </tr>
                </thead>
                <tbody>
                  {d.rows.map((r) => (
                    <tr key={r.key} className="border-b border-border last:border-0">
                      <td className="px-4 py-2">
                        {r.label} <span className="text-[11px] text-subtle-foreground">{r.unit}</span>
                      </td>
                      <td className="px-3 py-2 text-right tabular">{fmt(r.baseline, r.unit)}</td>
                      <td className="px-3 py-2 text-right tabular">
                        {fmt(r.a, r.unit)} <Delta v={r.a_delta} unit={r.unit} />
                      </td>
                      <td className="px-4 py-2 text-right tabular">
                        {fmt(r.b, r.unit)} <Delta v={r.b_delta} unit={r.unit} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
            <Section title="원인 기여도" description="단일 요인 효과 + 상호작용 잔차 = 총 변화">
              <div className="grid gap-4 sm:grid-cols-2">
                <Waterfall r={d.a} title={`A · ${d.a.params.name}`} color="#2563eb" />
                <Waterfall r={d.b} title={`B · ${d.b.params.name}`} color="#7c3aed" />
              </div>
            </Section>
          </div>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <Section title="민감도" description="요인별 단일 변화(±10%, ±20%)의 총비용 영향">
              {!sens.data ? <Skeleton className="h-56" /> : <Tornado data={sens.data} />}
            </Section>
            <Section title="가정 · 데이터 품질" description="저장 시 계산 버전·데이터 버전과 함께 기록됩니다">
              <ul className="space-y-1.5 text-[12.5px] text-muted-foreground">
                {d.a.assumptions.map((x) => (
                  <li key={x}>• {x}</li>
                ))}
              </ul>
              <p className="mt-3 text-[12px] text-subtle-foreground tabular">
                용량 정보 있는 운행 {num(d.a.data_quality.trips_with_capacity)}/{num(d.a.data_quality.trips_total)} · 차량 미배정 배송 {num(d.a.data_quality.shipments_without_vehicle)}건
              </p>
            </Section>
          </div>
          {can("scenario.save") && (
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3 shadow-card">
              <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
                {save.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />} A · B 저장
              </Button>
              <span className="text-[12px] text-muted-foreground">초안으로 저장되며 승인 요청·복제·Excel 내보내기는 ‘저장된 시나리오’에서 합니다.</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function filterQ(f: Filters) {
  return filterQuery(f) as Record<string, string | string[]>;
}

function useCompare(body: { a: ScenarioInput; b: ScenarioInput }, f: Filters) {
  const { me } = useWorkspace();
  return useQuery({
    queryKey: ["compare", me?.workspace.id, body, f],
    queryFn: () => apiFetch<Compare>("/api/scenarios/compare", { method: "POST", body, query: filterQ(f) }),
    enabled: !!me,
    placeholderData: keepPreviousData,
  });
}

function fmt(v: number | null, unit: string) {
  if (!isNum(v)) return "—";
  return unit === "원" ? `${won(v)}` : num(v, Number.isInteger(v) ? 0 : 1);
}

function Delta({ v, unit }: { v: number | null; unit: string }) {
  if (!isNum(v) || Math.abs(v) < 1e-9) return null;
  return (
    <span className={cn("ml-1 text-[11px]", v > 0 ? "text-danger" : "text-success")}>
      ({v > 0 ? "+" : ""}
      {unit === "원" ? won(v) : num(v, 1)})
    </span>
  );
}

function ScenarioTile({ r, tag, tone }: { r: EngineResult; tag: string; tone: string }) {
  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3.5 shadow-card">
      <div className="flex items-center justify-between gap-2">
        <span className={cn("truncate text-[12px] font-semibold", tone)}>
          {tag} · {r.params.name}
        </span>
        <KindBadge kind="assumption" />
      </div>
      <div className="mt-1.5 flex items-baseline gap-2">
        <span className="text-[22px] font-semibold leading-none tracking-tight tabular">{won(r.scenario.total)}</span>
        <span className="text-[12.5px] text-muted-foreground">원</span>
        <span className={cn("ml-auto rounded-md px-1.5 py-0.5 text-[12px] font-semibold tabular", r.delta_pct > 0 ? "bg-danger/10 text-danger" : "bg-success/10 text-success")}>
          {r.delta_pct > 0 ? "+" : ""}
          {r.delta_pct.toFixed(2)}%
        </span>
      </div>
      <div className="mt-1.5 text-[11.5px] text-subtle-foreground tabular">Baseline 대비 {r.delta_total > 0 ? "+" : ""}{won(r.delta_total)}원</div>
    </div>
  );
}

function Waterfall({ r, title, color }: { r: EngineResult; title: string; color: string }) {
  const steps = Object.entries(r.contribution);
  let acc = r.baseline.total ?? 0;
  const data = [{ name: "기준", base: 0, val: acc, kind: "total" }];
  steps.forEach(([k, v]) => {
    const start = acc;
    acc += v;
    data.push({ name: CONTRIB_LABEL[k] ?? k, base: Math.min(start, acc), val: Math.abs(v), kind: v >= 0 ? "up" : "down" });
  });
  data.push({ name: "결과", base: 0, val: acc, kind: "total" });
  const min = Math.min(...data.filter((d) => d.kind !== "total").map((d) => d.base), r.baseline.total ?? 0) * 0.97;
  return (
    <div>
      <p className="mb-1 truncate text-[12px] font-medium text-muted-foreground">{title}</p>
      <div style={{ height: 200 }} role="img" aria-label={`${title} 기여도 워터폴`}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 6, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
            <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 10.5, fill: "var(--subtle-foreground)" }} interval={0} />
            <YAxis domain={[min, "auto"]} tickFormatter={(v) => won(v)} tickLine={false} axisLine={false} width={52} tick={{ fontSize: 10.5, fill: "var(--subtle-foreground)" }} />
            <Tooltip
              cursor={{ fill: "var(--muted)", opacity: 0.5 }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <div className="rounded-lg border border-border bg-popover px-3 py-2 text-[12px] shadow-lg">
                    <div className="font-medium">{(payload[0].payload as { name: string }).name}</div>
                    <div className="tabular text-muted-foreground">
                      {(payload[0].payload as { kind: string }).kind === "down" ? "−" : (payload[0].payload as { kind: string }).kind === "up" ? "+" : ""}
                      {won((payload[0].payload as { val: number }).val, { compact: false })}원
                    </div>
                  </div>
                ) : null
              }
            />
            <Bar dataKey="base" stackId="w" fill="transparent" />
            <Bar dataKey="val" stackId="w" radius={[3, 3, 0, 0]} maxBarSize={34}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.kind === "total" ? color : d.kind === "up" ? "var(--danger)" : "var(--success)"} fillOpacity={d.kind === "total" ? 0.85 : 0.75} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Tornado({ data }: { data: Sens[] }) {
  const factors = [...new Set(data.map((d) => d.factor))];
  const rows = factors.map((f) => {
    const o: Record<string, number | string> = { factor: f };
    data.filter((d) => d.factor === f).forEach((d) => (o[String(d.change_pct)] = d.delta_pct));
    return o;
  });
  const keys = ["-20", "-10", "10", "20"];
  const color: Record<string, string> = { "-20": "#16a34a", "-10": "#86efac", "10": "#fca5a5", "20": "#dc2626" };
  return (
    <div>
      <div style={{ height: 210 }} role="img" aria-label="민감도 토네이도 차트">
        <ResponsiveContainer>
          <BarChart data={rows} layout="vertical" barCategoryGap="28%" margin={{ left: 4, right: 12, top: 4, bottom: 0 }}>
            <CartesianGrid horizontal={false} stroke="var(--chart-grid)" />
            <XAxis type="number" tickFormatter={(v) => `${v}%`} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--subtle-foreground)" }} />
            <YAxis type="category" dataKey="factor" width={64} tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} />
            <ReferenceLine x={0} stroke="var(--border-strong)" />
            <Tooltip
              cursor={{ fill: "var(--muted)", opacity: 0.4 }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <div className="rounded-lg border border-border bg-popover px-3 py-2 text-[12px] shadow-lg">
                    <div className="mb-1 font-medium">{String((payload[0].payload as { factor: string }).factor)}</div>
                    {payload.map((p) => (
                      <div key={String(p.dataKey)} className="flex justify-between gap-4 tabular">
                        <span className="text-muted-foreground">{Number(p.dataKey) > 0 ? "+" : ""}{String(p.dataKey)}%</span>
                        <span>{(p.value as number).toFixed(2)}%</span>
                      </div>
                    ))}
                  </div>
                ) : null
              }
            />
            {keys.map((k) => (
              <Bar key={k} dataKey={k} fill={color[k]} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex flex-wrap justify-center gap-3 text-[11px] text-muted-foreground">
        {keys.map((k) => (
          <span key={k} className="flex items-center gap-1">
            <span className="size-2 rounded-sm" style={{ background: color[k] }} />
            {Number(k) > 0 ? "+" : ""}
            {k}%
          </span>
        ))}
      </div>
    </div>
  );
}

// ── 센터 중단 ─────────────────────────────────────────────────────────
function OutageTab() {
  const { filters } = useFilters();
  const { can } = useWorkspace();
  const fm = useFilterMeta();
  const whs = useMemo(() => fm.data?.options.warehouses ?? [], [fm.data]);
  const [wid, setWid] = useState("");
  useEffect(() => {
    if (!wid && whs.length) setWid(whs[0].value);
  }, [whs, wid]);
  const q = useApi<Outage>(wid ? "/api/scenarios/outage" : null, { filters, query: { warehouse_id: wid } });
  const save = useApiMutation<void, { id: number }>(() => ({ path: "/api/scenarios/outage/save", query: { ...filterQ(filters), warehouse_id: wid } }), {
    success: (r) => `센터 중단 분석 #${r.id} 저장`,
  });
  const d = q.data;
  if (fm.data && !whs.length) return <EmptyState title="센터 데이터가 없습니다" description="센터·배송지·주문 데이터가 있어야 중단 영향을 분석합니다." />;
  return (
    <div className="space-y-4">
      <FilterBar />
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-card px-4 py-3 shadow-card">
        <Field label="중단 센터">
          <Select value={wid} onValueChange={setWid}>
            <SelectTrigger size="sm" className="w-52" aria-label="중단 센터">
              <SelectValue placeholder="센터 선택" />
            </SelectTrigger>
            <SelectContent>
              {whs.map((w) => (
                <SelectItem key={w.value} value={w.value}>
                  {w.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        {can("scenario.save") && d?.status === "ok" && (
          <Button size="sm" variant="outline" className="ml-auto" onClick={() => save.mutate()} disabled={save.isPending}>
            <Save className="size-3.5" /> 분석 저장
          </Button>
        )}
      </div>
      {q.isError && <ErrorState error={q.error} />}
      {!d ? (
        <Skeleton className="h-80" />
      ) : d.status !== "ok" ? (
        <Callout tone="warn">{d.reason}</Callout>
      ) : (
        <>
          {d.assumptions.map((a) => (
            <Callout key={a} tone="info">
              {a}
            </Callout>
          ))}
          <div className="grid gap-3 md:grid-cols-3">
            <StatTile label="영향 배송지" value={num(d.stores.length)} unit="곳" />
            <StatTile label="이전 대상 주문" value={num(d.stores.reduce((s, x) => s + x.orders, 0))} unit="건" />
            <StatTile label="평균 거리 증가" value={num(d.stores.reduce((s, x) => s + x.dist_change_km, 0) / (d.stores.length || 1), 1)} unit="km" tone="warning" />
          </div>
          <Section title="대체 센터 처리용량" bodyClassName="p-0">
            <table className="w-full text-[12.5px]">
              <thead className="text-[11.5px] text-muted-foreground">
                <tr className="border-b border-border">
                  {["대체 센터", "현재 일 주문", "추가 일 주문", "일 처리용량", "중단 후 가동률"].map((h, i) => (
                    <th key={h} className={cn("px-4 py-2 font-medium", i ? "text-right" : "text-left")}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {d.capacity.map((c) => (
                  <tr key={c.warehouse_id} className="border-b border-border last:border-0">
                    <td className="px-4 py-2 font-medium">{c.warehouse_id}</td>
                    <td className="px-4 py-2 text-right tabular">{num(c.current_orders_per_day, 1)}</td>
                    <td className="px-4 py-2 text-right tabular">+{num(c.added_orders_per_day, 1)}</td>
                    <td className="px-4 py-2 text-right tabular">{num(c.daily_capacity_orders)}</td>
                    <td className="px-4 py-2 text-right">
                      {isNum(c.utilization_after) ? (
                        <span className="inline-flex items-center gap-2">
                          <span className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                            <span className={cn("block h-full rounded-full", c.utilization_after > 1 ? "bg-danger" : c.utilization_after > 0.85 ? "bg-warning" : "bg-success")} style={{ width: `${Math.min(100, c.utilization_after * 100)}%` }} />
                          </span>
                          <span className={cn("w-12 tabular", c.utilization_after > 1 && "font-semibold text-danger")}>{pct(c.utilization_after, 0)}</span>
                        </span>
                      ) : (
                        <span className="text-subtle-foreground">용량 미입력</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
          <Section title="배송지별 대체 배정" description="직선거리 최근접 기준 · 거리 증가 큰 순" bodyClassName="p-3">
            <SimpleTable
              rows={d.stores.map((s) => ({
                배송지: s.store_name,
                권역: s.region,
                주문: s.orders,
                "기존 거리(km)": s.dist_from_closed_km,
                "대체 센터": s.alt_warehouse,
                "대체 거리(km)": s.dist_from_alt_km,
                "증가(km)": s.dist_change_km,
              }))}
            />
          </Section>
        </>
      )}
    </div>
  );
}

// ── 저장된 시나리오 ───────────────────────────────────────────────────
function SavedTab() {
  const q = useApi<ScenarioRow[]>("/api/scenarios");
  const [open, setOpen] = useState<number | null>(null);
  const [kind, setKind] = useState("all");
  const rows = useMemo(() => (q.data ?? []).filter((r) => kind === "all" || r.kind === kind), [q.data, kind]);
  const pending = (q.data ?? []).filter((r) => r.status === "proposed").length;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-80" />;
  if (!q.data.length) return <EmptyState title="저장된 시나리오가 없습니다" description="비용 시나리오·센터 중단·배송 계획을 저장하면 여기에서 승인·복제·내보내기를 할 수 있습니다." />;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {["all", "cost_scenario", "route_plan", "warehouse_outage", "risk_weights"].map((k) => (
          <Button key={k} size="sm" variant={kind === k ? "secondary" : "ghost"} className="h-7" onClick={() => setKind(k)}>
            {k === "all" ? "전체" : KIND_LABEL[k]}
            <span className="text-[11px] text-subtle-foreground tabular">{k === "all" ? q.data.length : q.data.filter((r) => r.kind === k).length}</span>
          </Button>
        ))}
        {pending > 0 && <Pill tone="warning" dot className="ml-auto">승인 대기 {pending}</Pill>}
      </div>
      <Section bodyClassName="p-0">
        <ul className="divide-y divide-border">
          {rows.map((r) => {
            const st = STATUS_LABEL[r.status];
            return (
              <li key={r.id}>
                <button type="button" onClick={() => setOpen(r.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/40">
                  <span className="w-10 text-[12px] text-subtle-foreground tabular">#{r.id}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13.5px] font-medium">{r.name}</p>
                    <p className="text-[11.5px] text-muted-foreground">
                      {KIND_LABEL[r.kind] ?? r.kind} · {r.created_by} · {dateTimeLabel(r.created_at)}
                    </p>
                  </div>
                  <span className="hidden font-mono text-[11px] text-subtle-foreground md:inline">{r.calc_version}</span>
                  <Pill tone={st.tone}>{st.label}</Pill>
                </button>
              </li>
            );
          })}
        </ul>
      </Section>
      <ScenarioSheet id={open} onClose={() => setOpen(null)} />
    </div>
  );
}

function ScenarioSheet({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { can } = useWorkspace();
  const q = useApi<ScenarioDetail>(id ? `/api/scenarios/${id}` : null);
  const [note, setNote] = useState("");
  const [dupName, setDupName] = useState("");
  const status = useApiMutation<{ status: string }, unknown>((b) => ({ path: `/api/scenarios/${id}/status`, body: { status: b.status, note } }), {
    success: "상태가 기록되었습니다. 외부 TMS 배차는 자동 실행되지 않습니다.",
  });
  const dup = useApiMutation<void, { id: number }>(() => ({ path: `/api/scenarios/${id}/duplicate`, body: { name: dupName || `${q.data?.name} (복제)` } }), {
    success: (r) => `#${r.id} 로 복제했습니다`,
  });
  const s = q.data;
  return (
    <Sheet open={id !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full gap-0 p-0 sm:max-w-lg">
        <SheetHeader className="border-b border-border px-5 py-4">
          <SheetTitle>{s ? s.name : "불러오는 중"}</SheetTitle>
          <SheetDescription>{s ? `#${s.id} · ${KIND_LABEL[s.kind] ?? s.kind} · ${s.calc_version}` : ""}</SheetDescription>
          {s && <Pill tone={STATUS_LABEL[s.status].tone} className="w-fit">{STATUS_LABEL[s.status].label}</Pill>}
        </SheetHeader>
        {!s ? (
          <Skeleton className="m-5 h-64" />
        ) : (
          <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5 text-[13px]">
            {s.status === "proposed" && (
              <div className="space-y-2 rounded-lg border border-warning/30 bg-warning/[0.06] p-3">
                <p className="font-medium">승인 대기 중</p>
                {can("plan.approve") ? (
                  <>
                    <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="검토 의견 (선택)" className="min-h-16 bg-card text-[13px]" />
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => status.mutate({ status: "approved" })} disabled={status.isPending}>
                        <Check className="size-3.5" /> 승인
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => status.mutate({ status: "rejected" })} disabled={status.isPending}>
                        <X className="size-3.5" /> 반려
                      </Button>
                    </div>
                    <p className="text-[11.5px] text-muted-foreground">승인은 기록만 남깁니다. 실제 배차·발주는 기존 시스템에서 담당자가 확정합니다.</p>
                  </>
                ) : (
                  <p className="text-[12px] text-muted-foreground">승인/반려는 운영 관리자 이상 권한이 필요합니다.</p>
                )}
              </div>
            )}
            {s.status === "draft" && can("scenario.save") && (
              <Button size="sm" variant="outline" onClick={() => status.mutate({ status: "proposed" })} disabled={status.isPending}>
                승인 요청
              </Button>
            )}
            <Block title="입력값">
              <KV obj={s.params} />
            </Block>
            {s.assumptions && s.assumptions.length > 0 && (
              <Block title="가정">
                <ul className="space-y-1 text-[12.5px] text-muted-foreground">
                  {s.assumptions.map((a) => (
                    <li key={a}>• {a}</li>
                  ))}
                </ul>
              </Block>
            )}
            {s.data_versions && Object.keys(s.data_versions).length > 0 && (
              <Block title="데이터 버전">
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(s.data_versions).map(([k, v]) => (
                    <span key={k} className="rounded-md bg-muted px-1.5 py-0.5 text-[11.5px] tabular">
                      {k} v{v.version}
                    </span>
                  ))}
                </div>
              </Block>
            )}
            <div className="flex flex-wrap gap-2 border-t border-border pt-4">
              <DownloadButton path={`/api/scenarios/${s.id}/excel`} filename={`scenario_${s.id}.xlsx`} label="Excel" />
              {can("scenario.save") && (
                <div className="flex flex-1 gap-2">
                  <Input value={dupName} onChange={(e) => setDupName(e.target.value)} placeholder={`${s.name} (복제)`} className="h-8" aria-label="복제 이름" />
                  <Button size="sm" variant="outline" onClick={() => dup.mutate()} disabled={dup.isPending}>
                    <Copy className="size-3.5" /> 복제
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-[11.5px] font-semibold uppercase tracking-wide text-subtle-foreground">{title}</h3>
      {children}
    </div>
  );
}

function KV({ obj }: { obj: Record<string, unknown> }) {
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border">
      {Object.entries(obj).map(([k, v]) => (
        <div key={k} className="bg-card px-3 py-2">
          <dt className="text-[11px] text-muted-foreground">{k}</dt>
          <dd className="mt-0.5 break-words text-[12.5px] font-medium tabular">{typeof v === "object" ? JSON.stringify(v) : String(v ?? "—")}</dd>
        </div>
      ))}
    </dl>
  );
}

function ScopeTab() {
  const rows: [string, string, string][] = [
    ["경유가 +5/+10/+20%", "지원", "비용·운행 시나리오"],
    ["배송 수요 +10/+30%", "지원 (가정 기반)", "비용·운행 시나리오"],
    ["운송 단가 상승", "지원", "비용·운행 시나리오"],
    ["차량 수 축소/증차", "지원 (차량 부족 일수)", "비용·운행 시나리오"],
    ["특정 센터 중단", "지원 (직선거리 대체·용량)", "센터 중단"],
    ["센터 처리용량 감소", "부분 (용량 입력값 기반 가동률)", "센터 중단"],
    ["SKU 보충정책 변경", "부분 (서비스수준·검토주기)", "Demand & Inventory"],
    ["배송 계획 대안", "지원 (CVRP 휴리스틱)", "Transportation"],
    ["시간창 제약 배차", "미지원", "—"],
    ["실도로 거리 기반 계획", "미지원 (직선거리 × 우회계수)", "—"],
  ];
  return (
    <Section title="시나리오 지원 범위" description="미지원 항목은 화면에 버튼을 두지 않습니다." bodyClassName="p-0">
      <table className="w-full text-[13px]">
        <thead className="text-[11.5px] text-muted-foreground">
          <tr className="border-b border-border">
            <th className="px-4 py-2 text-left font-medium">시나리오</th>
            <th className="px-4 py-2 text-left font-medium">지원</th>
            <th className="px-4 py-2 text-left font-medium">화면</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([a, b, c]) => (
            <tr key={a} className="border-b border-border last:border-0">
              <td className="px-4 py-2.5 font-medium">{a}</td>
              <td className="px-4 py-2.5">
                <Pill tone={b.startsWith("미지원") ? "neutral" : b.startsWith("부분") ? "warning" : "success"}>{b}</Pill>
              </td>
              <td className="px-4 py-2.5 text-muted-foreground">{c}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

