"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { Loader2, Route, Send } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { DataTable } from "@/components/common/data-table";
import { FilterBar } from "@/components/common/filter-bar";
import { popupHtml, type MapLine, type MapPoint } from "@/components/common/geo-map";
import { Callout, DownloadButton, Field, LineTabs, NumberField, StatTile, useUrlTab } from "@/components/common/kit";
import { PageHeader } from "@/components/common/page-header";
import { Section } from "@/components/common/section";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { apiFetch } from "@/lib/api";
import { filterSearchParams, useFilters } from "@/lib/filters";
import { isNum, num, pct, won } from "@/lib/format";
import { navByKey } from "@/lib/nav";
import type { CtsRow, Fuel, Plan, PlanningMeta } from "@/lib/types";
import { useApi, useApiMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

const GeoMap = dynamic(() => import("@/components/common/geo-map").then((m) => m.GeoMap), {
  ssr: false,
  loading: () => <Skeleton className="h-[460px] rounded-lg" />,
});

const NAV = navByKey("transportation");
const DIMS = { carrier: "운송사", vehicle_id: "차량", store_id: "배송지", region: "권역", warehouse_id: "센터", customer_group: "거래처군" } as const;
type Dim = keyof typeof DIMS;
const ROUTE_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2", "#db2777", "#4b5563", "#65a30d", "#ea580c"];

export function TransportationScreen() {
  const { me } = useWorkspace();
  const [tab, setTab] = useUrlTab(["cts", "fuel", "plan"]);
  if (me && !me.has_ops_data)
    return (
      <>
        <PageHeader nav={NAV} title="배송 · 배차 · 운송비" />
        <EmptyState icon={Route} title="배송 데이터가 없습니다" description="운송장 단위 배송 실적을 업로드하면 Cost-to-Serve·연료비·배차 대안을 분석합니다." />
      </>
    );
  return (
    <>
      <PageHeader nav={NAV} title="배송 · 배차 · 운송비" description="Cost-to-Serve, 차량별 연비, 휴리스틱 배송 계획 대안" />
      <LineTabs
        value={tab}
        onChange={setTab}
        items={[
          { v: "cts", label: "Cost-to-Serve" },
          { v: "fuel", label: "연료비 · 연비" },
          { v: "plan", label: "배송 계획 대안" },
        ]}
      />
      {tab !== "plan" && <FilterBar className="mb-4" />}
      {tab === "cts" && <CtsTab />}
      {tab === "fuel" && <FuelTab />}
      {tab === "plan" && <PlanTab />}
    </>
  );
}

// ── Cost-to-Serve ─────────────────────────────────────────────────────
function CtsTab() {
  const { filters } = useFilters();
  const [dim, setDim] = useState<Dim>("carrier");
  const q = useApi<{ rows: CtsRow[]; total_cost: number | null }>("/api/transportation/cts", { filters, query: { dim } });
  const rows = q.data?.rows ?? [];
  const label = (r: CtsRow) => (dim === "store_id" ? (r.name ?? r.key) : r.key) ?? "(미지정)";
  const cols: ColumnDef<CtsRow, unknown>[] = [
    { id: "key", header: DIMS[dim], accessorFn: (r) => label(r), cell: (c) => <span className="font-medium">{String(c.getValue())}</span> },
    { accessorKey: "shipments", header: "배송", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
    { accessorKey: "orders", header: "주문", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
    { accessorKey: "cost", header: "운송비", meta: { align: "right" }, cell: (c) => `${won(c.getValue() as number)}원` },
    { accessorKey: "cost_per_order", header: "주문당", meta: { align: "right" }, cell: (c) => `${won(c.getValue() as number)}원` },
    { accessorKey: "cost_per_kg", header: "kg당", meta: { align: "right" }, cell: (c) => `${num(c.getValue() as number, 1)}원` },
    { accessorKey: "cost_per_km", header: "km당", meta: { align: "right" }, cell: (c) => `${num(c.getValue() as number)}원` },
    { accessorKey: "distance_km", header: "거리(km)", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
    {
      accessorKey: "late_rate",
      header: "지연율",
      meta: { align: "right" },
      cell: (c) => {
        const v = c.getValue() as number | null;
        return <span className={cn(isNum(v) && v >= 0.1 && "font-medium text-danger")}>{pct(v)}</span>;
      },
    },
  ];
  const top = rows.slice(0, 20).map((r) => ({ ...r, label: label(r) }));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ToggleGroup type="single" variant="outline" size="sm" value={dim} onValueChange={(v) => v && setDim(v as Dim)} aria-label="집계 기준">
          {(Object.keys(DIMS) as Dim[]).map((k) => (
            <ToggleGroupItem key={k} value={k} className="px-3 text-[12.5px]">
              {DIMS[k]}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <DownloadButton path="/api/transportation/cts.csv" params={filterSearchParams(filters, { dim })} filename={`cost_to_serve_${dim}.csv`} label="CSV" />
      </div>
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
        <Section title={`${DIMS[dim]}별 운송비 · 주문당 운송비`} description="상위 20 · 막대: 운송비(좌), 선: 주문당(우)">
          {!q.data ? (
            <Skeleton className="h-72" />
          ) : top.length === 0 ? (
            <p className="py-16 text-center text-[13px] text-muted-foreground">대상 배송이 없습니다.</p>
          ) : (
            <div style={{ height: 300 }} role="img" aria-label="운송비 차트">
              <ResponsiveContainer>
                <ComposedChart data={top} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--subtle-foreground)" }} interval={0} angle={top.length > 8 ? -30 : 0} textAnchor={top.length > 8 ? "end" : "middle"} height={top.length > 8 ? 56 : 28} />
                  <YAxis yAxisId="c" tickFormatter={(v) => (v ? won(v) : "0")} tickLine={false} axisLine={false} width={44} tick={{ fontSize: 11, fill: "var(--subtle-foreground)" }} />
                  <YAxis yAxisId="o" orientation="right" tickFormatter={(v) => won(v)} tickLine={false} axisLine={false} width={40} tick={{ fontSize: 11, fill: "var(--subtle-foreground)" }} />
                  <Tooltip
                    cursor={{ fill: "var(--muted)", opacity: 0.5 }}
                    content={({ active, payload }) =>
                      active && payload?.length ? (
                        <div className="rounded-lg border border-border bg-popover px-3 py-2 text-[12px] shadow-lg">
                          <div className="font-medium">{String((payload[0].payload as { label: string }).label)}</div>
                          <div className="tabular text-muted-foreground">
                            운송비 {won((payload[0].payload as CtsRow).cost, { compact: false })}원 · 주문당 {won((payload[0].payload as CtsRow).cost_per_order)}원
                          </div>
                        </div>
                      ) : null
                    }
                  />
                  <Bar yAxisId="c" dataKey="cost" fill="var(--chart-1)" fillOpacity={0.8} radius={[3, 3, 0, 0]} maxBarSize={36} />
                  <Line yAxisId="o" dataKey="cost_per_order" stroke="var(--chart-4)" strokeWidth={2} dot={{ r: 2.5 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </Section>
        <div className="space-y-3">
          <StatTile label="기간 운송비 합" value={won(q.data?.total_cost)} unit="원" sub={`${num(rows.length)}개 ${DIMS[dim]}`} />
          <Callout tone="info">
            Cost-to-Serve 는 배송 단위 운송비를 기준별로 합산합니다. 주문당·kg당·km당 단가는 각 분모가 있는 건 기준이며, 창고 운영비 등 공통비 배분은 포함하지 않습니다.
          </Callout>
        </div>
      </div>
      <Section title="상세" bodyClassName="p-3">
        {!q.data ? <Skeleton className="h-64" /> : <DataTable data={rows} columns={cols} rowKey={(r) => String(r.key)} height={420} initialSort={[{ id: "cost", desc: true }]} ariaLabel="Cost-to-Serve 상세" />}
      </Section>
    </div>
  );
}

// ── 연료비 · 연비 ──────────────────────────────────────────────────────
type V = NonNullable<Fuel["vehicles"]>[number];
const VCOLS: ColumnDef<V, unknown>[] = [
  { accessorKey: "vehicle_id", header: "차량", cell: (c) => <span className="font-mono text-[12px]">{String(c.getValue() ?? "미배정")}</span> },
  { accessorKey: "carrier", header: "운송사" },
  { accessorKey: "vehicle_type", header: "차종" },
  { accessorKey: "shipments", header: "배송", meta: { align: "right" } },
  { accessorKey: "distance_km", header: "거리(km)", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
  { accessorKey: "fuel_l", header: "연료(L)", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
  { accessorKey: "fuel_cost", header: "연료비", meta: { align: "right" }, cell: (c) => `${won(c.getValue() as number)}원` },
  { accessorKey: "km_per_l_spec", header: "제원 연비", meta: { align: "right" }, cell: (c) => num(c.getValue() as number, 1) },
  { accessorKey: "km_per_l_actual", header: "실측 연비", meta: { align: "right" }, cell: (c) => num(c.getValue() as number, 1) },
  {
    accessorKey: "eff_gap_pct",
    header: "제원 대비",
    meta: { align: "right" },
    cell: (c) => {
      const v = c.getValue() as number | null;
      if (!isNum(v)) return "—";
      return <span className={cn("font-medium", v <= -15 ? "text-danger" : v < 0 ? "text-warning" : "text-success")}>{`${v > 0 ? "+" : ""}${v.toFixed(1)}%`}</span>;
    },
  },
];

function FuelTab() {
  const { filters } = useFilters();
  const q = useApi<Fuel>("/api/transportation/fuel", { filters });
  const d = q.data;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!d) return <Skeleton className="h-96" />;
  if (!d.available) return <EmptyState title="대상 배송이 없습니다" description="필터 조건을 확인하세요." />;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile label="연료비 (실제 + 추정)" value={won(d.fuel_cost)} unit="원" />
        <StatTile label="연료량" value={num(d.fuel_l)} unit="L" />
        <StatTile label="운송비 중 연료비 비중" value={pct(d.fuel_share)} />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <SourceList title="연료량 출처" data={d.fuel_l_sources ?? {}} />
        <SourceList title="경유가 출처" data={d.price_sources ?? {}} />
      </div>
      {d.uses_external_price && (
        <Callout tone="warn" title="외부 참고값 사용">
          일부 건은 기업 구매 단가가 없어 전국평균 경유가(외부 지표)를 참고값으로 썼습니다. 실제 구매 단가와 다를 수 있습니다.
        </Callout>
      )}
      <Section title="차량별 연료 효율" description="실측 연비가 제원보다 크게 낮은 차량은 운행 패턴·정비 점검 후보 (낮은 순)" bodyClassName="p-3">
        <DataTable data={d.vehicles ?? []} columns={VCOLS} rowKey={(r) => String(r.vehicle_id)} height={420} ariaLabel="차량별 연료 효율" />
      </Section>
    </div>
  );
}

function SourceList({ title, data }: { title: string; data: Record<string, number> }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-card">
      <h3 className="mb-2.5 text-[13px] font-semibold">{title}</h3>
      <ul className="space-y-2">
        {Object.entries(data).map(([k, v]) => (
          <li key={k} className="text-[12.5px]">
            <div className="flex justify-between gap-2">
              <span className="truncate">{k}</span>
              <span className="tabular text-muted-foreground">{num(v)}건</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-chart-1" style={{ width: `${(v / total) * 100}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── 배송 계획 대안 ────────────────────────────────────────────────────
function PlanTab() {
  const { can } = useWorkspace();
  const meta = useApi<PlanningMeta>("/api/transportation/planning");
  const [source, setSource] = useState<"orders" | "shipments">("orders");
  const [day, setDay] = useState<string>("");
  const [wh, setWh] = useState<string>("");
  const [p, setP] = useState({ road_factor: 1.0, avg_speed_kmh: 40, default_service_min: 15, default_max_hours: 10 });
  const [price, setPrice] = useState<number | null>(null);
  const [name, setName] = useState("");
  const m = meta.data;
  const days = useMemo(() => (m ? (source === "shipments" ? [...m.days.shipments].reverse() : m.days.orders) : []), [m, source]);

  useEffect(() => {
    if (days.length && !days.includes(day)) setDay(days[0]);
  }, [days, day]);
  useEffect(() => {
    if (m?.warehouses.length && !wh) setWh(m.warehouses[0].value);
  }, [m, wh]);

  const body = { source, day, warehouse_id: wh, ...p, diesel_price: price };
  const run = usePlan(day && wh ? body : null);
  const save = useApiMutation<void, { id: number }>(() => ({ path: "/api/transportation/plan/save", body: { ...body, name: name || `배송계획 ${day} ${wh}` } }), {
    success: (r) => `제안 #${r.id} 저장 — Scenario Lab '저장된 시나리오'에서 승인/반려할 수 있습니다.`,
  });

  if (meta.isError) return <ErrorState error={meta.error} onRetry={() => meta.refetch()} />;
  if (!m) return <Skeleton className="h-96" />;
  if (m.missing.length) return <EmptyState title="배송 계획에 필요한 데이터가 부족합니다" description={`필요: ${m.missing.join(", ")}`} />;

  const r = run.data;
  return (
    <div className="space-y-4">
      <Callout tone="info" title="휴리스틱 계획 대안">
        Clarke-Wright Savings + 2-opt 로 중량·용적·운행시간·차량 수 제약을 검토합니다. 시간창은 강제하지 않으며, 거리는 직선거리 근사(우회계수 조정 가능)입니다. 결과는 ‘제안’이며 배차 확정은 운영 관리자 승인 후 기존 TMS 에서 수행합니다.
      </Callout>
      <Section title="계획 조건" bodyClassName="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="계획 대상" className="sm:col-span-2">
          <ToggleGroup type="single" variant="outline" size="sm" value={source} onValueChange={(v) => v && setSource(v as typeof source)} className="w-full">
            <ToggleGroupItem value="orders" className="flex-1 text-[12px]">미출고 주문</ToggleGroupItem>
            <ToggleGroupItem value="shipments" className="flex-1 text-[12px]">과거 실적 재계획</ToggleGroupItem>
          </ToggleGroup>
        </Field>
        <Field label={source === "orders" ? "납기일" : "출고일"}>
          <Select value={day} onValueChange={setDay} disabled={!days.length}>
            <SelectTrigger size="sm" className="w-full" aria-label="일자">
              <SelectValue placeholder="없음" />
            </SelectTrigger>
            <SelectContent className="max-h-72">
              {days.map((d) => (
                <SelectItem key={d} value={d}>
                  {d}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="센터">
          <Select value={wh} onValueChange={setWh}>
            <SelectTrigger size="sm" className="w-full" aria-label="센터">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {m.warehouses.map((w) => (
                <SelectItem key={w.value} value={w.value}>
                  {w.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <NumberField id="pf" label="경유가(원/L)" value={price ?? NaN} onChange={setPrice} min={0} step={10} hint="미입력 시 기업 유가표 적용" />
        <NumberField id="rf" label="우회계수" value={p.road_factor} onChange={(v) => setP({ ...p, road_factor: v })} min={1} max={2} step={0.05} />
        <NumberField id="sp" label="평균 속도" value={p.avg_speed_kmh} onChange={(v) => setP({ ...p, avg_speed_kmh: v })} min={10} max={90} step={5} suffix="km/h" />
        <NumberField id="mh" label="최대 운행" value={p.default_max_hours} onChange={(v) => setP({ ...p, default_max_hours: v })} min={1} max={16} step={0.5} suffix="h" />
      </Section>
      {!days.length && (
        <Callout tone="warn">
          {source === "orders" ? "납기일이 지정된 미출고 주문이 없습니다. 미래 주문을 업로드하거나 ‘과거 실적 재계획’을 선택하세요." : "출고 실적이 없습니다."}
        </Callout>
      )}
      {run.isError && <ErrorState error={run.error} />}
      {run.isFetching && !r && <Skeleton className="h-96" />}
      {r?.status === "empty" && <Callout tone="warn">{r.reason}</Callout>}
      {r?.status === "ok" && (
        <div className={cn("space-y-4", run.isFetching && "opacity-70 transition-opacity")}>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <StatTile label="대상 배송지" value={num(r.inputs.stops)} unit="곳" sub={`주문 ${num(r.inputs.orders)}건`} />
            <StatTile label="가용 차량" value={num(r.inputs.vehicles)} unit="대" />
            <StatTile label="총 수요" value={num(r.inputs.demand_kg)} unit="kg" sub={r.inputs.unknown_weight_stops ? `중량 미상 ${r.inputs.unknown_weight_stops}곳` : undefined} />
            <StatTile label="제안 투입 차량" value={num(r.proposed.summary.vehicles_used)} unit="대" tone="info" />
            <StatTile label="제안 거리" value={num(r.proposed.summary.distance_km)} unit="km" sub={r.proposed.summary.distance_basis} />
            <StatTile label="추정 비용" value={won(r.proposed.summary.est_cost)} unit="원" sub={r.proposed.summary.cost_complete ? "변동+고정비" : "일부 단가 누락"} />
          </div>
          {r.proposed.violations.map((v) => (
            <Callout key={v} tone="danger" title="제안 계획 제약 위반">{v}</Callout>
          ))}
          {[...r.proposed.warnings, ...(r.baseline?.warnings ?? [])].map((w) => (
            <Callout key={w} tone="warn">{w}</Callout>
          ))}
          <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
            <Section title="제안 경로" description="방문 순서 · 직선 연결 (실도로 경로 아님)" bodyClassName="p-3">
              <RouteMap plan={r} />
            </Section>
            <Section title={r.comparison ? "현행(재구성) vs 제안" : "경로별 요약"} description={r.comparison ? "동일 거리 기준 추정치 — 실측 절감액 아님" : "미출고 주문이라 비교할 현행 배차가 없습니다"} bodyClassName="p-0">
              {r.comparison ? <CompareTable rows={r.comparison} /> : <RoutesTable plan={r} />}
            </Section>
          </div>
          {r.comparison && (
            <Section title="경로별 요약" bodyClassName="p-0">
              <RoutesTable plan={r} />
            </Section>
          )}
          {r.proposed.unassigned.length > 0 && (
            <Section title={`미배정 배송지 ${r.proposed.unassigned.length}곳`} description="대안: 차량 추가 · 2회전 운행 · 납기 조정 · 분할 배송" bodyClassName="p-3">
              <SimpleTable rows={r.proposed.unassigned} />
            </Section>
          )}
          {can("scenario.save") && (
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3 shadow-card">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={`배송계획 ${day} ${wh}`} className="h-8 max-w-72" aria-label="제안명" />
              <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
                {save.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />} 승인 요청으로 저장
              </Button>
              <span className="text-[12px] text-muted-foreground">배차 확정이 아닙니다. 승인해도 외부 TMS 는 자동 실행되지 않습니다.</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function usePlan(body: Record<string, unknown> | null) {
  const { me } = useWorkspace();
  const [debounced, setDebounced] = useState(body);
  const key = JSON.stringify(body);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(body), 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return useQuery({
    queryKey: ["plan", me?.workspace.id, JSON.stringify(debounced)],
    queryFn: () => apiFetch<Plan>("/api/transportation/plan", { method: "POST", body: debounced }),
    enabled: !!me && !!debounced,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}

function RouteMap({ plan }: { plan: Plan }) {
  const byRoute = new Map<number, typeof plan.proposed.stops>();
  plan.proposed.stops.forEach((s) => byRoute.set(s.route, [...(byRoute.get(s.route) ?? []), s]));
  const routes = [...byRoute.keys()].sort((a, b) => a - b);
  const color = (r: number) => ROUTE_COLORS[(r - 1) % ROUTE_COLORS.length];
  const lines: MapLine[] = routes.map((r) => {
    const st = byRoute.get(r)!.sort((a, b) => a.seq - b.seq);
    return { id: `r${r}`, color: color(r), coords: [[plan.depot.lon, plan.depot.lat], ...st.map((s) => [s.lon, s.lat] as [number, number]), [plan.depot.lon, plan.depot.lat]] };
  });
  const pts: MapPoint[] = plan.proposed.stops.map((s) => ({
    id: `${s.route}-${s.seq}`,
    lat: s.lat,
    lon: s.lon,
    color: color(s.route),
    radius: 5.5,
    html: popupHtml(s.name, `경로 R${s.route} · ${s.seq}번째`, [["차량", s.vehicle_id], ["수요", `${num(s.demand_kg)}kg`]]),
  }));
  return (
    <GeoMap
      layers={[{ id: "stops", points: pts }]}
      lines={lines}
      markers={[{ id: "depot", lat: plan.depot.lat, lon: plan.depot.lon, label: plan.depot.name }]}
      height={460}
      fitKey={`${plan.day}|${plan.warehouse_id}|${plan.source}|${pts.length}`}
      ariaLabel="제안 경로 지도"
      legend={
        <div className="flex flex-wrap gap-x-2.5 gap-y-1">
          {routes.map((r) => (
            <span key={r} className="flex items-center gap-1 text-muted-foreground">
              <span className="h-0.5 w-3 rounded" style={{ background: color(r) }} /> R{r} {byRoute.get(r)![0].vehicle_id}
            </span>
          ))}
        </div>
      }
    />
  );
}

function CompareTable({ rows }: { rows: Record<string, number | string | null>[] }) {
  return (
    <table className="w-full whitespace-nowrap text-[12.5px]">
      <thead className="text-[11.5px] text-muted-foreground">
        <tr className="border-b border-border">
          <th className="px-4 py-2 text-left font-medium">지표</th>
          <th className="px-3 py-2 text-right font-medium">현행(재구성)</th>
          <th className="px-3 py-2 text-right font-medium">제안</th>
          <th className="px-4 py-2 text-right font-medium">차이</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => {
          const d = r["차이(%)"] as number | null;
          return (
            <tr key={i} className="border-b border-border last:border-0">
              <td className="px-4 py-2">
                {String(r["지표"])} <span className="text-[11px] text-subtle-foreground">{String(r["단위"] ?? "")}</span>
              </td>
              <td className="px-3 py-2 text-right tabular">{num(r["현행(재구성)"] as number, 1)}</td>
              <td className="px-3 py-2 text-right font-medium tabular">{num(r["제안"] as number, 1)}</td>
              <td className={cn("px-4 py-2 text-right tabular", isNum(d) && d < 0 && "text-success", isNum(d) && d > 0 && "text-warning")}>
                {isNum(d) ? `${d > 0 ? "+" : ""}${d.toFixed(1)}%` : "—"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function RoutesTable({ plan }: { plan: Plan }) {
  return (
    <div className="overflow-x-auto">
    <table className="w-full whitespace-nowrap text-[12.5px]">
      <thead className="text-[11.5px] text-muted-foreground">
        <tr className="border-b border-border">
          {["경로", "차량", "배송지", "적재", "적재율", "거리", "시간", "추정 비용"].map((h, i) => (
            <th key={h} className={cn("px-3 py-2 font-medium", i >= 2 ? "text-right" : "text-left", i === 0 && "pl-4", i === 7 && "pr-4")}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {plan.proposed.routes.map((r) => {
          const lf = r.load_factor as number | null;
          return (
            <tr key={String(r.route)} className="border-b border-border last:border-0">
              <td className="py-2 pl-4 pr-3">
                <span className="inline-flex items-center gap-1.5 font-medium">
                  <span className="size-2 rounded-full" style={{ background: ROUTE_COLORS[((r.route as number) - 1) % ROUTE_COLORS.length] }} />R{String(r.route)}
                </span>
              </td>
              <td className="px-3 py-2 font-mono text-[12px]">{String(r.vehicle_id)}</td>
              <td className="px-3 py-2 text-right tabular">{num(r.stops as number)}</td>
              <td className="px-3 py-2 text-right tabular">{num(r.load_kg as number)}kg</td>
              <td className="px-3 py-2 text-right">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-1.5 w-12 overflow-hidden rounded-full bg-muted">
                    <span className={cn("block h-full rounded-full", (lf ?? 0) > 1 ? "bg-danger" : "bg-chart-1")} style={{ width: `${Math.min(100, (lf ?? 0) * 100)}%` }} />
                  </span>
                  <span className="w-10 text-right tabular">{pct(lf, 0)}</span>
                </span>
              </td>
              <td className="px-3 py-2 text-right tabular">{num(r.distance_km as number)}km</td>
              <td className="px-3 py-2 text-right tabular">{num(r.duration_h as number, 1)}h</td>
              <td className="py-2 pl-3 pr-4 text-right tabular">{won(r.est_cost as number)}원</td>
            </tr>
          );
        })}
      </tbody>
    </table>
    </div>
  );
}

export function SimpleTable({ rows }: { rows: Record<string, unknown>[] }) {
  const cols = Object.keys(rows[0] ?? {});
  return (
    <div className="max-h-72 overflow-auto rounded-lg border border-border">
      <table className="w-full text-[12.5px]">
        <thead className="sticky top-0 bg-muted text-[11.5px] text-muted-foreground">
          <tr>
            {cols.map((c) => (
              <th key={c} className="whitespace-nowrap px-3 py-1.5 text-left font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border">
              {cols.map((c) => (
                <td key={c} className="whitespace-nowrap px-3 py-1.5">
                  {typeof r[c] === "number" ? num(r[c] as number, Number.isInteger(r[c]) ? 0 : 1) : String(r[c] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

