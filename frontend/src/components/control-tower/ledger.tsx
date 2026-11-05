"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Download, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { DataTable } from "@/components/common/data-table";
import { Section } from "@/components/common/section";
import { ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { download } from "@/lib/api";
import { filterSearchParams, type Filters } from "@/lib/filters";
import { dateLabel, isNum, num, won } from "@/lib/format";
import { useLedger, type LedgerKind } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

type Row = Record<string, unknown>;

const s = (v: unknown) => (v == null ? "—" : String(v));

const COLUMNS: ColumnDef<Row, unknown>[] = [
  { accessorKey: "shipment_id", header: "운송장", cell: (c) => <span className="font-mono text-[12px]">{s(c.getValue())}</span> },
  { accessorKey: "ship_date", header: "출고일", cell: (c) => dateLabel(c.getValue() as string) },
  {
    accessorKey: "store_name",
    header: "배송지",
    cell: (c) => (
      <div className="leading-tight">
        <div className="font-medium">{s(c.getValue())}</div>
        <div className="text-[11px] text-muted-foreground">{s(c.row.original.region)}</div>
      </div>
    ),
  },
  { accessorKey: "warehouse_id", header: "센터" },
  { accessorKey: "carrier", header: "운송사" },
  { accessorKey: "vehicle_id", header: "차량", cell: (c) => <span className="font-mono text-[12px]">{s(c.getValue())}</span> },
  { accessorKey: "planned_delivery_date", header: "약속일", cell: (c) => dateLabel(c.getValue() as string) },
  { accessorKey: "actual_delivery_date", header: "실제 배송", cell: (c) => dateLabel(c.getValue() as string) },
  {
    accessorKey: "delay_days",
    header: "지연",
    meta: { align: "right" },
    cell: (c) => {
      const v = c.getValue() as number | null;
      if (!isNum(v)) return "—";
      return <span className={cn(v > 0 && "font-semibold text-danger")}>{v > 0 ? `+${num(v)}일` : `${num(v)}일`}</span>;
    },
  },
  {
    id: "qty",
    header: "배송/주문 수량",
    meta: { align: "right" },
    accessorFn: (r) => r.delivered_qty,
    cell: (c) => {
      const d = c.row.original.delivered_qty as number | null;
      const o = c.row.original.ordered_qty as number | null;
      const short = isNum(d) && isNum(o) && d < o;
      return <span className={cn(short && "text-warning")}>{`${num(d)} / ${num(o)}`}</span>;
    },
  },
  { accessorKey: "distance_km", header: "거리(km)", meta: { align: "right" }, cell: (c) => num(c.getValue() as number) },
  {
    accessorKey: "cost",
    header: "운송비",
    meta: { align: "right" },
    cell: (c) => (isNum(c.getValue()) ? `${won(c.getValue() as number, { compact: false })}원` : "—"),
  },
  {
    accessorKey: "cost_source",
    header: "비용 출처",
    cell: (c) => <span className="text-[11.5px] text-muted-foreground">{s(c.getValue())}</span>,
  },
];

const TABS: { v: LedgerKind; label: string }[] = [
  { v: "late", label: "지연 배송" },
  { v: "cost", label: "비용 초과" },
  { v: "all", label: "전체 원장" },
];

export function Ledger({ filters, selected, onClearSelection }: { filters: Filters; selected: string[]; onClearSelection: () => void }) {
  const [kind, setKind] = useState<LedgerKind>("late");
  const { can } = useWorkspace();
  const active = useLedger(filters, kind, selected);
  // 탭 배지용 건수 (행은 1건만 받아 가볍게)
  const counts = {
    late: useLedger(filters, "late", selected, 1).data?.total,
    cost: useLedger(filters, "cost", selected, 1).data,
    all: useLedger(filters, "all", selected, 1).data?.total,
  };
  const [busy, setBusy] = useState(false);
  const d = active.data;

  const exportCsv = async () => {
    setBusy(true);
    try {
      await download("/api/control-tower/ledger.csv", filterSearchParams(filters, { kind, selected }), `ledger_${kind}.csv`);
      toast.success("CSV 를 내려받았습니다", { description: "내보내기 기록이 감사 로그에 남습니다." });
    } catch (e) {
      toast.error("내보내기 실패", { description: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section
      title="예외 · 배송 원장"
      description="KPI 에서 운송장 단위까지 추적합니다. 지도·표에서 배송지를 선택하면 원장이 함께 좁혀집니다."
      actions={
        <>
          {selected.length > 0 && (
            <Button variant="secondary" size="sm" onClick={onClearSelection} className="gap-1">
              배송지 {selected.length}곳 선택됨 <X className="size-3.5" />
            </Button>
          )}
          {can("data.export") ? (
            <Button variant="outline" size="sm" onClick={exportCsv} disabled={busy || !d?.available || !d?.total}>
              <Download className="size-3.5" /> CSV 내보내기
            </Button>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <span tabIndex={0}>
                  <Button variant="outline" size="sm" disabled>
                    <Download className="size-3.5" /> CSV 내보내기
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>분석가 이상 권한이 필요합니다</TooltipContent>
            </Tooltip>
          )}
        </>
      }
      bodyClassName="space-y-3"
    >
      <Tabs value={kind} onValueChange={(v) => setKind(v as LedgerKind)}>
        <TabsList>
          {TABS.map((t) => {
            const c = t.v === "cost" ? (counts.cost?.available ? counts.cost.total : undefined) : counts[t.v];
            return (
              <TabsTrigger key={t.v} value={t.v} className="gap-1.5 px-3">
                {t.label}
                {c !== undefined && (
                  <span className="rounded-full bg-background/80 px-1.5 text-[11px] text-muted-foreground tabular">{c.toLocaleString()}</span>
                )}
              </TabsTrigger>
            );
          })}
        </TabsList>
      </Tabs>
      {kind === "cost" && d?.rule && (
        <p className="text-[12px] text-muted-foreground">
          판정 규칙: <span className="font-medium text-foreground">{d.rule}</span>
        </p>
      )}
      {active.isError ? (
        <ErrorState error={active.error} onRetry={() => active.refetch()} />
      ) : active.isLoading ? (
        <Skeleton className="h-80" />
      ) : !d?.available ? (
        <p className="rounded-lg border border-dashed border-border-strong px-4 py-8 text-center text-[13px] text-muted-foreground">
          {d?.reason ?? "판정할 수 없습니다."}
        </p>
      ) : (
        <div className={cn(active.isFetching && "opacity-70 transition-opacity")}>
          <DataTable
            data={d.rows as Row[]}
            columns={COLUMNS}
            rowKey={(r) => String(r.shipment_id)}
            height={420}
            ariaLabel="배송 원장"
            empty={kind === "late" ? "지연된 배송이 없습니다." : "해당 조건의 배송이 없습니다."}
          />
          {d.total > d.rows.length && (
            <p className="mt-2 text-[12px] text-muted-foreground">
              {d.total.toLocaleString()}건 중 {d.rows.length.toLocaleString()}건 표시 · 전체는 CSV 로 내려받으세요.
            </p>
          )}
        </div>
      )}
    </Section>
  );
}
