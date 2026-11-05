"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { AlertOctagon, AlertTriangle, CheckCircle2, Fuel as FuelIcon, Info } from "lucide-react";
import { useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { KindBadge, Pill } from "@/components/common/badges";
import { DataTable } from "@/components/common/data-table";
import { FilterBar } from "@/components/common/filter-bar";
import { Callout, Field, LineTabs, StatTile, useUrlTab } from "@/components/common/kit";
import { PageHeader } from "@/components/common/page-header";
import { Section } from "@/components/common/section";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useFilters } from "@/lib/filters";
import { dateLabel, isNum, num, pct, won } from "@/lib/format";
import { navByKey } from "@/lib/nav";
import type { Audit, Diesel, Market, Traffic } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const NAV = navByKey("fuel-risk");
const PCTS = [-10, -5, 5, 10, 15, 20, 30];
const BY = { carrier: "운송사", vehicle_id: "차량", store_id: "배송지", warehouse_id: "센터" } as const;
const ax = { tickLine: false, axisLine: false, tick: { fontSize: 11, fill: "var(--subtle-foreground)" } } as const;

export function FuelRiskScreen() {
  const [tab, setTab] = useUrlTab(["impact", "market", "traffic", "audit"]);
  return (
    <>
      <PageHeader
        nav={NAV}
        title="유류비 · 외부 위험"
        description="기업 연료비 영향(관측 기반)과 외부 지표(전국 유가·고속도로 교통량)를 구분해 보여줍니다."
      />
      <LineTabs
        value={tab}
        onChange={setTab}
        items={[
          { v: "impact", label: "기업 연료비 충격" },
          { v: "market", label: "유가 · 예측 (외부)" },
          { v: "traffic", label: "교통량 · 기준 이벤트" },
          { v: "audit", label: "데이터 감사" },
        ]}
      />
      {tab === "impact" && <ImpactTab />}
      {tab === "market" && <MarketTab />}
      {tab === "traffic" && <TrafficTab />}
      {tab === "audit" && <AuditTab />}
    </>
  );
}

function ImpactTab() {
  const { filters } = useFilters();
  const [pcts, setPcts] = useState<string[]>(["5", "10", "20"]);
  const [by, setBy] = useState<keyof typeof BY>("carrier");
  const q = useApi<Diesel>("/api/fuel/diesel", { filters, query: { pcts: pcts.length ? pcts : ["10"], by }, enabled: true });
  const d = q.data;
  const sorted = [...pcts].map(Number).sort((a, b) => a - b);
  const cols: ColumnDef<Record<string, number | string | null>, unknown>[] = useMemo(
    () => [
      { accessorKey: by, header: BY[by], cell: (c) => <span className="font-medium">{String(c.getValue() ?? "(미지정)")}</span> },
      { accessorKey: "shipments", header: "배송", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
      { accessorKey: "fuel_l", header: "연료(L)", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
      { accessorKey: "base_fuel_cost", header: "기준 연료비", meta: { align: "right" }, cell: (c) => `${won(c.getValue() as number)}원` },
      ...sorted.map(
        (p): ColumnDef<Record<string, number | string | null>, unknown> => ({
          id: `d${p}`,
          header: `경유 ${p > 0 ? "+" : ""}${p}%`,
          meta: { align: "right" },
          accessorFn: (r) => r[`delta_${p > 0 ? "+" : ""}${p}%`],
          cell: (c) => {
            const v = c.getValue() as number;
            return <span className={cn(v > 0 ? "text-danger" : "text-success")}>{`${v > 0 ? "+" : ""}${won(v)}원`}</span>;
          },
        }),
      ),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [by, pcts.join(",")],
  );

  return (
    <div className="space-y-4">
      <FilterBar />
      <div className="flex flex-wrap items-end gap-4 rounded-xl border border-border bg-card px-4 py-3 shadow-card">
        <Field label="경유가 변화율">
          <ToggleGroup type="multiple" variant="outline" size="sm" value={pcts} onValueChange={(v) => v.length && setPcts(v)} aria-label="경유가 변화율">
            {PCTS.map((p) => (
              <ToggleGroupItem key={p} value={String(p)} className="px-2.5 text-[12px] tabular">
                {p > 0 ? "+" : ""}
                {p}%
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </Field>
        <Field label="분해 기준">
          <Select value={by} onValueChange={(v) => setBy(v as keyof typeof BY)}>
            <SelectTrigger size="sm" className="w-32" aria-label="분해 기준">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(BY).map(([k, v]) => (
                <SelectItem key={k} value={k}>
                  {v}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {!d ? (
        <Skeleton className="h-96" />
      ) : d.status !== "ok" ? (
        <EmptyState icon={FuelIcon} title="기업 배송 데이터가 없습니다" description="운행거리·연료량·연비 데이터가 있어야 경유가 변화의 비용 영향을 계산합니다." />
      ) : (
        <div className={cn("space-y-4", q.isFetching && "opacity-70 transition-opacity")}>
          <div className="grid gap-3 md:grid-cols-3">
            <StatTile label="기준 연료비" value={won(d.base_fuel_cost)} unit="원" />
            <StatTile label="기간 총 운송비" value={won(d.base_total_cost)} unit="원" />
            <StatTile label="계산 커버리지" value={pct(d.coverage, 0)} sub={`${num(d.n_computable)} / ${num(d.n_total)}건`} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {d.rows.map((r) => (
              <div key={r.diesel_pct} className="rounded-xl border border-border bg-card p-4 shadow-card">
                <div className="flex items-center justify-between">
                  <span className="text-[12.5px] font-medium text-muted-foreground">경유가 {r.diesel_pct > 0 ? "+" : ""}{r.diesel_pct}%</span>
                  <KindBadge kind="assumption" />
                </div>
                <div className={cn("mt-2 text-[22px] font-semibold tracking-tight tabular", r.fuel_cost_delta > 0 ? "text-danger" : "text-success")}>
                  {r.fuel_cost_delta > 0 ? "+" : ""}
                  {won(r.fuel_cost_delta)}
                  <span className="ml-0.5 text-[13px] font-medium text-muted-foreground">원</span>
                </div>
                <div className="mt-1 text-[11.5px] text-subtle-foreground tabular">
                  총 운송비 대비 {isNum(r.total_cost_delta_pct) ? `${r.total_cost_delta_pct > 0 ? "+" : ""}${r.total_cost_delta_pct.toFixed(2)}%` : "—"}
                </div>
              </div>
            ))}
          </div>
          <Section title={`${BY[by]}별 영향`} description="연료 사용량 불변 가정 · 상위 200" bodyClassName="p-3">
            <DataTable data={d.by} columns={cols} rowKey={(r) => String(r[by])} height={380} ariaLabel="경유가 민감도 상세" />
          </Section>
          <div className="grid gap-3 md:grid-cols-2">
            <Section title="데이터 출처">
              <dl className="space-y-1.5 text-[12.5px]">
                {Object.entries(d.fuel_l_sources).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2">
                    <dt className="text-muted-foreground">연료량 · {k}</dt>
                    <dd className="tabular">{num(v)}건</dd>
                  </div>
                ))}
                {Object.entries(d.price_sources).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2">
                    <dt className="text-muted-foreground">경유가 · {k}</dt>
                    <dd className="tabular">{num(v)}건</dd>
                  </div>
                ))}
              </dl>
            </Section>
            <Section title="가정">
              <ul className="space-y-1.5 text-[12.5px] text-muted-foreground">
                {d.assumptions.map((a) => (
                  <li key={a}>• {a}</li>
                ))}
                <li>• 복합 시나리오(운송단가·물동량·차량 수)는 Scenario Lab 에서 비교·저장할 수 있습니다.</li>
              </ul>
            </Section>
          </div>
        </div>
      )}
    </div>
  );
}

function MarketTab() {
  const [w, setW] = useState<number | null>(null);
  const [comp, setComp] = useState(true);
  const q = useApi<Market>("/api/fuel/market", { query: { prophet_weight: w ?? undefined }, staleTime: 300_000 });
  const d = q.data;
  const data = useMemo(() => {
    if (!d?.available) return [];
    const rows = new Map<string, Record<string, number | string>>();
    (d.history ?? []).slice(-240).forEach((h) => rows.set(h.date, { date: h.date, diesel: h.diesel_price, gasoline: h.gasoline_price }));
    (d.forecast ?? []).forEach((f) =>
      rows.set(f.date, {
        ...(rows.get(f.date) ?? { date: f.date }),
        band: [f.diesel_price_prophet_lower, f.diesel_price_prophet_upper] as unknown as number,
        reweighted: f.reweighted,
        prophet: f.diesel_price_prophet,
        lstm: f.diesel_price_lstm,
      }),
    );
    return [...rows.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [d]);

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!d) return <Skeleton className="h-96" />;
  if (!d.available) return <EmptyState title="유가 이력 파일이 없습니다" />;
  const weight = w ?? d.inferred_weight ?? 0.4;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Pill tone="external">외부 위험 지표</Pill>
        <Pill>전국 평균 — 기업 구매가 아님</Pill>
      </div>
      {(d.warnings ?? []).map((x) => (
        <Callout key={x} tone="warn" title="예측 최신성">
          {x}
        </Callout>
      ))}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <Section title="경유가 관측 · 저장된 예측 (원/L)" description="최근 240일 관측 + 저장된 예측 구간 · 빨간 점선은 기준 이벤트">
          <div style={{ height: 380 }} role="img" aria-label="경유가 관측 및 예측 차트">
            <ResponsiveContainer>
              <ComposedChart data={data} margin={{ top: 10, right: 8, left: 4, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                <XAxis dataKey="date" {...ax} minTickGap={40} tickFormatter={(v) => String(v).slice(2, 7).replace("-", ".")} />
                <YAxis {...ax} width={48} domain={["auto", "auto"]} tickFormatter={(v) => num(v)} />
                <Tooltip
                  content={({ active, payload, label }) =>
                    active && payload?.length ? (
                      <div className="rounded-lg border border-border bg-popover px-3 py-2 text-[12px] shadow-lg">
                        <div className="mb-1 font-medium">{dateLabel(String(label))}</div>
                        {payload
                          .filter((p) => p.dataKey !== "band" && isNum(p.value as number))
                          .map((p) => (
                            <div key={String(p.dataKey)} className="flex justify-between gap-4">
                              <span className="flex items-center gap-1.5 text-muted-foreground">
                                <span className="size-2 rounded-full" style={{ background: p.color }} />
                                {p.name}
                              </span>
                              <span className="tabular font-medium">{num(p.value as number)}원</span>
                            </div>
                          ))}
                      </div>
                    ) : null
                  }
                />
                <Legend verticalAlign="bottom" height={28} iconType="plainline" wrapperStyle={{ fontSize: 11.5 }} />
                <Area dataKey="band" name="Prophet 구간" stroke="none" fill="var(--chart-1)" fillOpacity={0.12} legendType="square" />
                <Line dataKey="diesel" name="경유(관측)" stroke="var(--foreground)" strokeWidth={2} dot={false} />
                <Line dataKey="gasoline" name="휘발유(관측)" stroke="var(--subtle-foreground)" strokeWidth={1} dot={false} />
                <Line dataKey="reweighted" name={`앙상블(재가중 ${weight.toFixed(2)})`} stroke="var(--chart-1)" strokeWidth={2} strokeDasharray="5 4" dot={false} />
                {comp && <Line dataKey="prophet" name="Prophet" stroke="var(--chart-5)" strokeWidth={1} dot={false} />}
                {comp && <Line dataKey="lstm" name="LSTM" stroke="var(--chart-4)" strokeWidth={1} dot={false} />}
                <ReferenceLine x={d.event_date} stroke="var(--danger)" strokeDasharray="3 3" label={{ value: d.event_label, position: "insideTopLeft", fontSize: 10.5, fill: "var(--danger)" }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Section>
        <div className="space-y-3">
          <Section title="앙상블 재가중" description="저장된 Prophet·LSTM 예측을 다시 가중합합니다. 모델을 재학습하지 않습니다." bodyClassName="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-[12.5px]">
                <span className="font-medium">Prophet 가중치</span>
                <span className="tabular text-muted-foreground">
                  {weight.toFixed(2)} / LSTM {(1 - weight).toFixed(2)}
                </span>
              </div>
              <Slider value={[weight]} min={0} max={1} step={0.05} onValueChange={([v]) => setW(v)} aria-label="Prophet 가중치" />
              {isNum(d.inferred_weight) && (
                <p className="text-[11.5px] text-subtle-foreground">저장된 앙상블 가중치(역산): Prophet {d.inferred_weight.toFixed(2)}</p>
              )}
            </div>
            <label className="flex items-center justify-between gap-2 text-[12.5px]">
              구성 모델 표시
              <Switch checked={comp} onCheckedChange={setComp} />
            </label>
          </Section>
          {d.change_range && (
            <Callout tone="warn" title="Shock Index 해석">
              Shock Index·위험등급은 예측 구간 30일 변화율의 min-max 상대값입니다. 이 예측의 변화율은 {d.change_range[0].toFixed(1)}% ~ {d.change_range[1].toFixed(1)}%
              (마지막 관측가 대비 하락)이라 ‘CRITICAL’ 이 절대적 급등을 뜻하지 않습니다.
            </Callout>
          )}
        </div>
      </div>
    </div>
  );
}

function TrafficTab() {
  const q = useApi<Traffic>("/api/fuel/traffic", { staleTime: 300_000 });
  const d = q.data;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!d) return <Skeleton className="h-96" />;
  if (!d.available || !d.comparison) return <EmptyState title="교통량 파일이 없습니다" />;
  const c = d.comparison;
  return (
    <div className="space-y-4">
      <Callout tone="warn" title="해석 주의">
        {c.caveat} 기준일 명칭은 원인이 검증되지 않아 중립적으로 표기합니다.
      </Callout>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label={`이전 일평균 화물 (${c.pre_days}일)`} value={num(c.pre_mean)} unit="대" tone="external" />
        <StatTile label={`이후 일평균 화물 (${c.post_days}일)`} value={num(c.post_mean)} unit="대" tone="external" sub={isNum(c.change_pct) ? `단순 비교 ${c.change_pct > 0 ? "+" : ""}${c.change_pct.toFixed(1)}%` : undefined} />
        <StatTile label="요일 구성 보정 변화" value={isNum(c.change_pct_dow_adj) ? `${c.change_pct_dow_adj > 0 ? "+" : ""}${c.change_pct_dow_adj.toFixed(1)}%` : "—"} />
        <StatTile label="전년 동기간 대비" value={isNum(c.yoy_pct) ? `${c.yoy_pct > 0 ? "+" : ""}${c.yoy_pct.toFixed(1)}%` : "비교 불가"} />
      </div>
      <Section title="전국 고속도로 일교통량 (주 평균)" description={`이전 ${c.pre_period} · 이후 ${c.post_period} — 기간 길이·계절 구성이 다릅니다.`}>
        <div style={{ height: 340 }} role="img" aria-label="주별 교통량 차트">
          <ResponsiveContainer>
            <ComposedChart data={d.weekly} margin={{ top: 10, right: 8, left: 4, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
              <XAxis dataKey="date" {...ax} minTickGap={40} tickFormatter={(v) => String(v).slice(2, 7).replace("-", ".")} />
              <YAxis yAxisId="f" {...ax} width={56} tickFormatter={(v) => num(v)} />
              <YAxis yAxisId="p" orientation="right" {...ax} width={64} tickFormatter={(v) => num(v)} />
              <Tooltip
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-[12px] shadow-lg">
                      <div className="mb-1 font-medium">{dateLabel(String(label))} 주</div>
                      {payload.map((p) => (
                        <div key={String(p.dataKey)} className="flex justify-between gap-4">
                          <span className="text-muted-foreground">{p.name}</span>
                          <span className="tabular font-medium">{num(p.value as number)}대</span>
                        </div>
                      ))}
                    </div>
                  ) : null
                }
              />
              <Legend verticalAlign="bottom" height={28} iconType="plainline" wrapperStyle={{ fontSize: 11.5 }} />
              <Line yAxisId="f" dataKey="freight_345_traffic" name="화물(3·4·5종)" stroke="var(--external)" strokeWidth={2} dot={false} />
              <Line yAxisId="p" dataKey="passenger_126_traffic" name="승용(1·2·6종, 우축)" stroke="var(--subtle-foreground)" strokeWidth={1.5} dot={false} />
              <ReferenceLine yAxisId="f" x={d.weekly?.find((w) => w.date >= "2026-02-28")?.date} stroke="var(--danger)" strokeDasharray="3 3" label={{ value: d.event_label, position: "insideTopLeft", fontSize: 10.5, fill: "var(--danger)" }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Section>
    </div>
  );
}

const LV = {
  ok: { icon: CheckCircle2, cls: "text-success", label: "확인" },
  info: { icon: Info, cls: "text-info", label: "참고" },
  warn: { icon: AlertTriangle, cls: "text-warning", label: "주의" },
  error: { icon: AlertOctagon, cls: "text-danger", label: "오류" },
} as const;

function AuditTab() {
  const q = useApi<Audit>("/api/fuel/audit", { staleTime: 300_000 });
  const d = q.data;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!d) return <Skeleton className="h-96" />;
  const counts = d.findings.reduce<Record<string, number>>((a, f) => ((a[f.level] = (a[f.level] ?? 0) + 1), a), {});
  return (
    <div className="space-y-4">
      <p className="text-[13px] text-muted-foreground">기존 공모전 산출물을 파일에서 매번 다시 계산해 점검한 결과입니다.</p>
      <div className="flex flex-wrap gap-2">
        {(["error", "warn", "info", "ok"] as const).map((l) => (
          <Pill key={l} tone={l === "error" ? "danger" : l === "warn" ? "warning" : l === "ok" ? "success" : "info"}>
            {LV[l].label} {counts[l] ?? 0}
          </Pill>
        ))}
      </div>
      <Section bodyClassName="p-0">
        <ul className="divide-y divide-border">
          {d.findings.map((f, i) => {
            const L = LV[f.level] ?? LV.info;
            return (
              <li key={i} className="flex items-start gap-3 px-4 py-3">
                <L.icon className={cn("mt-0.5 size-4 shrink-0", L.cls)} aria-label={L.label} />
                <div className="min-w-0">
                  <p className="text-[13px] font-medium">{f.title}</p>
                  <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted-foreground">{f.detail}</p>
                </div>
              </li>
            );
          })}
        </ul>
      </Section>
      <Section title="데이터 출처" bodyClassName="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead className="text-[11.5px] text-muted-foreground">
              <tr className="border-b border-border">
                {["데이터", "성격", "기간", "표본", "주의"].map((h) => (
                  <th key={h} className="px-4 py-2 text-left font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.provenance.map((p) => (
                <tr key={p.key} className="border-b border-border align-top last:border-0">
                  <td className="px-4 py-2">
                    <div className="font-medium">{p.key}</div>
                    <div className="max-w-72 truncate text-[11px] text-subtle-foreground">{p.source}</div>
                  </td>
                  <td className="px-4 py-2">
                    <KindBadge kind={p.kind} />
                  </td>
                  <td className="px-4 py-2 text-muted-foreground tabular">{p.period_start ? `${p.period_start} ~ ${p.period_end}` : "—"}</td>
                  <td className="px-4 py-2 tabular">{num(p.n)}</td>
                  <td className="max-w-96 px-4 py-2 text-[12px] text-warning">{p.warnings.join(" · ") || <span className="text-subtle-foreground">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
