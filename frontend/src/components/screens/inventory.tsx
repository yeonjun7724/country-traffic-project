"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Boxes, Trophy } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Pill } from "@/components/common/badges";
import { DataTable } from "@/components/common/data-table";
import { Callout, DownloadButton, Field, NumberField, StatTile } from "@/components/common/kit";
import { PageHeader } from "@/components/common/page-header";
import { Section } from "@/components/common/section";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { dateLabel, isNum, num, pct, shortDate } from "@/lib/format";
import { navByKey } from "@/lib/nav";
import { useFilterMeta } from "@/lib/queries";
import type { Forecast, InventoryView, InvRow, Opt } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const NAV = navByKey("inventory");
const RISKS = ["결품", "높음", "낮음", "판정 불가"] as const;
const RISK_TONE: Record<string, "danger" | "warning" | "success" | "neutral"> = { 결품: "danger", 높음: "warning", 낮음: "success", "판정 불가": "neutral" };

const COLS: ColumnDef<InvRow, unknown>[] = [
  {
    accessorKey: "sku_id",
    header: "SKU",
    cell: (c) => (
      <div className="max-w-52 leading-tight">
        <div className="truncate font-medium">{c.row.original.sku_name ?? c.row.original.sku_id}</div>
        <div className="font-mono text-[11px] text-muted-foreground">{c.row.original.sku_id}</div>
      </div>
    ),
  },
  { accessorKey: "warehouse_id", header: "센터" },
  { accessorKey: "stockout_risk", header: "위험", cell: (c) => <Pill tone={RISK_TONE[c.getValue() as string]}>{String(c.getValue())}</Pill> },
  {
    accessorKey: "available",
    header: "가용",
    meta: { align: "right" },
    cell: (c) => <span className={cn((c.getValue() as number) <= 0 && "font-semibold text-danger")}>{num(c.getValue() as number)}</span>,
  },
  { accessorKey: "inbound_qty", header: "입고 예정", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
  { accessorKey: "avg_daily_demand", header: "일평균 수요", meta: { align: "right" }, cell: (c) => num(c.getValue() as number, 2) },
  {
    accessorKey: "days_of_supply",
    header: "재고일수",
    meta: { align: "right" },
    sortUndefined: "last",
    cell: (c) => {
      const v = c.getValue() as number | null;
      return isNum(v) ? <span className={cn(v < 7 && "font-medium text-warning")}>{num(v, 1)}일</span> : "—";
    },
  },
  { accessorKey: "lead_time_days", header: "리드타임", meta: { align: "right" }, cell: (c) => (isNum(c.getValue()) ? `${num(c.getValue() as number)}일` : "—") },
  { accessorKey: "safety_stock", header: "안전재고", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
  { accessorKey: "reorder_point", header: "재주문점", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
  {
    accessorKey: "recommended_qty",
    header: "보충 추천",
    meta: { align: "right" },
    cell: (c) => {
      const v = c.getValue() as number | null;
      return v ? <span className="font-semibold text-primary">{num(v)}</span> : <span className="text-subtle-foreground">0</span>;
    },
  },
  { accessorKey: "basis", header: "근거", cell: (c) => <span className="block max-w-80 truncate text-[11.5px] text-muted-foreground" title={String(c.getValue() ?? "")}>{String(c.getValue() ?? "—")}</span> },
];

export function InventoryScreen() {
  const [sl, setSl] = useState("0.95");
  const [win, setWin] = useState("28");
  const [rev, setRev] = useState(7);
  const [risks, setRisks] = useState<string[]>(["결품", "높음"]);
  const q = useApi<InventoryView>("/api/inventory/replenishment", { query: { service_level: sl, window_days: win, review_days: rev } });
  const d = q.data;
  const params = new URLSearchParams({ service_level: sl, window_days: win, review_days: String(rev) });

  return (
    <>
      <PageHeader nav={NAV} title="수요 · 재고 · 보충" description="기업 재고·주문 이력으로 안전재고·재주문점·보충 수량을 계산합니다." />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {d && d.status !== "ok" ? (
        <EmptyState
          icon={Boxes}
          title="재고 분석에 필요한 데이터가 없습니다"
          description={<>{d.reason}. 기업 재고 데이터 없이 재고 위험을 추정하거나 표시하지 않습니다.</>}
        />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-end gap-4 rounded-xl border border-border bg-card px-4 py-3 shadow-card">
            <Field label="목표 서비스 수준">
              <ToggleGroup type="single" variant="outline" size="sm" value={sl} onValueChange={(v) => v && setSl(v)}>
                {["0.9", "0.95", "0.975", "0.99"].map((v) => (
                  <ToggleGroupItem key={v} value={v} className="px-2.5 text-[12px] tabular">
                    {pct(Number(v), Number(v) === 0.975 ? 1 : 0)}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </Field>
            <Field label="수요 산정 기간">
              <ToggleGroup type="single" variant="outline" size="sm" value={win} onValueChange={(v) => v && setWin(v)}>
                {["14", "28", "56", "84"].map((v) => (
                  <ToggleGroupItem key={v} value={v} className="px-2.5 text-[12px] tabular">
                    {v}일
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </Field>
            <div className="w-28">
              <NumberField id="rev" label="검토 주기" value={rev} onChange={setRev} min={1} max={60} suffix="일" />
            </div>
            {d?.status === "ok" && (
              <p className="ml-auto text-[11.5px] text-subtle-foreground tabular">
                재고 기준일 {dateLabel(d.snapshot_date)} · 수요 기간 {d.demand_window} · z = {d.z.toFixed(3)}
              </p>
            )}
          </div>
          {!d ? (
            <Skeleton className="h-96" />
          ) : (
            d.status === "ok" && (
              <div className={cn("space-y-4", q.isFetching && "opacity-70 transition-opacity")}>
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                  <StatTile label="SKU × 센터" value={num(d.summary.sku_locations)} />
                  <StatTile label="결품 (가용 ≤ 0)" value={num(d.summary.stockout)} tone={d.summary.stockout ? "danger" : undefined} sub={`비율 ${pct(d.summary.stockout_rate)}`} />
                  <StatTile label="재주문점 이하" value={num(d.summary.high_risk)} tone={d.summary.high_risk ? "warning" : undefined} />
                  <StatTile label="보충 추천 합계" value={num(d.summary.recommended_total)} unit="EA" tone="info" />
                </div>
                <Section
                  title="보충 추천"
                  description="발주 확정이 아닙니다 — 발주는 ERP 에서 담당자 승인 후 진행하세요."
                  actions={
                    <>
                      <ToggleGroup type="multiple" variant="outline" size="sm" value={risks} onValueChange={setRisks} aria-label="위험 구분 필터">
                        {RISKS.map((r) => (
                          <ToggleGroupItem key={r} value={r} className="px-2.5 text-[12px]">
                            {r} <span className="ml-1 text-subtle-foreground tabular">{d.rows.filter((x) => x.stockout_risk === r).length}</span>
                          </ToggleGroupItem>
                        ))}
                      </ToggleGroup>
                      <DownloadButton path="/api/inventory/replenishment.csv" params={params} filename="replenishment.csv" label="CSV" />
                    </>
                  }
                  bodyClassName="space-y-3 p-3"
                >
                  <DataTable
                    data={risks.length ? d.rows.filter((r) => risks.includes(r.stockout_risk)) : d.rows}
                    columns={COLS}
                    rowKey={(r) => `${r.sku_id}|${r.warehouse_id}`}
                    height={440}
                    ariaLabel="보충 추천 목록"
                    empty="선택한 위험 구분에 해당하는 SKU 가 없습니다."
                  />
                  <ul className="grid gap-1 text-[11.5px] text-muted-foreground md:grid-cols-2">
                    {d.assumptions.map((a) => (
                      <li key={a} className="flex gap-1.5">
                        <span className="text-subtle-foreground">•</span>
                        {a}
                      </li>
                    ))}
                  </ul>
                </Section>
                <ForecastSection />
              </div>
            )
          )}
        </>
      )}
    </>
  );
}

function ForecastSection() {
  const skus = useApi<Opt[]>("/api/inventory/skus", { staleTime: 300_000 });
  const fm = useFilterMeta();
  const [sku, setSku] = useState("");
  const [wh, setWh] = useState("all");
  useEffect(() => {
    if (!sku && skus.data?.length) setSku(skus.data[0].value);
  }, [skus.data, sku]);
  const f = useApi<Forecast>(sku ? "/api/inventory/forecast" : null, { query: { sku, warehouse_id: wh === "all" ? undefined : wh } });
  const series = useMemo(() => (f.data?.status === "ok" ? f.data.series : []), [f.data]);

  return (
    <Section
      title="수요예측 모델 비교"
      description="최근 14일 holdout 백테스트 · WAPE 낮은 순 · MAPE 는 실적 0인 날 제외"
      actions={
        <>
          <Select value={sku} onValueChange={setSku}>
            <SelectTrigger size="sm" className="w-56" aria-label="SKU">
              <SelectValue placeholder="SKU" />
            </SelectTrigger>
            <SelectContent className="max-h-72">
              {(skus.data ?? []).map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label} <span className="text-subtle-foreground">· {s.value}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={wh} onValueChange={setWh}>
            <SelectTrigger size="sm" className="w-40" aria-label="센터">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">전체 센터</SelectItem>
              {(fm.data?.options.warehouses ?? []).map((w) => (
                <SelectItem key={w.value} value={w.value}>
                  {w.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </>
      }
    >
      {!f.data ? (
        <Skeleton className="h-72" />
      ) : f.data.status !== "ok" ? (
        <Callout tone="warn">{f.data.reason}</Callout>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div style={{ height: 260 }} role="img" aria-label="일별 수요 차트">
            <ResponsiveContainer>
              <AreaChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="dem" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                <XAxis dataKey="date" tickFormatter={shortDate} tickLine={false} axisLine={false} minTickGap={28} tick={{ fontSize: 11, fill: "var(--subtle-foreground)" }} />
                <YAxis tickLine={false} axisLine={false} width={36} tick={{ fontSize: 11, fill: "var(--subtle-foreground)" }} />
                <Tooltip
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <div className="rounded-lg border border-border bg-popover px-3 py-2 text-[12px] shadow-lg">
                        <div className="font-medium">{dateLabel((payload[0].payload as { date: string }).date)}</div>
                        <div className="tabular text-muted-foreground">주문수량 {num((payload[0].payload as { qty: number }).qty)}</div>
                      </div>
                    ) : null
                  }
                />
                <Area dataKey="qty" stroke="var(--chart-1)" strokeWidth={2} fill="url(#dem)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <table className="w-full self-start text-[12.5px]">
            <thead className="text-[11.5px] text-muted-foreground">
              <tr className="border-b border-border">
                {["모델", "WAPE", "MAE", "Bias", "MAPE"].map((h, i) => (
                  <th key={h} className={cn("py-2 font-medium", i ? "text-right" : "text-left")}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {f.data.backtest.map((b) => {
                const best = b.model === (f.data as { best: string }).best;
                return (
                  <tr key={b.model} className={cn("border-b border-border last:border-0", best && "bg-success/[0.05]")}>
                    <td className="py-2 pr-2">
                      <span className="inline-flex items-center gap-1.5 font-medium">
                        {best && <Trophy className="size-3.5 text-success" />}
                        {b.model}
                      </span>
                    </td>
                    <td className={cn("py-2 text-right tabular", best && "font-semibold text-success")}>{pct(b.WAPE)}</td>
                    <td className="py-2 text-right tabular">{num(b.MAE, 1)}</td>
                    <td className="py-2 text-right tabular">{num(b.Bias, 2)}</td>
                    <td className="py-2 text-right tabular">{pct(b["MAPE(0제외)"])}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}
