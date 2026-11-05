"use client";

import type { ColumnDef } from "@tanstack/react-table";
import dynamic from "next/dynamic";

import { DataTable } from "@/components/common/data-table";
import { Section } from "@/components/common/section";
import { ErrorState } from "@/components/common/states";
import { Skeleton } from "@/components/ui/skeleton";
import type { Schemas } from "@/lib/api";
import type { Filters } from "@/lib/filters";
import { isNum, pct, won } from "@/lib/format";
import { useNetwork } from "@/lib/queries";
import { cn } from "@/lib/utils";

const NetworkMap = dynamic(() => import("./network-map").then((m) => m.NetworkMap), {
  ssr: false,
  loading: () => <Skeleton className="h-[460px] rounded-lg" />,
});

type Store = Schemas["StorePoint"];

function lateColor(v: number | null | undefined) {
  if (!isNum(v)) return "bg-slate-300";
  if (v < 0.05) return "bg-emerald-500";
  if (v < 0.1) return "bg-lime-500";
  if (v < 0.2) return "bg-amber-500";
  return "bg-red-500";
}

const COLUMNS: ColumnDef<Store, unknown>[] = [
  {
    accessorKey: "name",
    header: "배송지",
    cell: (c) => (
      <div className="max-w-44 leading-tight">
        <div className="truncate font-medium">{c.row.original.name ?? c.row.original.store_id}</div>
        <div className="truncate text-[11px] text-muted-foreground">{c.row.original.region}</div>
      </div>
    ),
  },
  { accessorKey: "shipments", header: "배송", meta: { align: "right" }, cell: (c) => (c.getValue() as number)?.toLocaleString() ?? "—" },
  { accessorKey: "cost", header: "운송비", meta: { align: "right" }, cell: (c) => won(c.getValue() as number) },
  {
    accessorKey: "late_rate",
    header: "지연율",
    meta: { align: "right" },
    sortUndefined: "last",
    cell: (c) => {
      const v = c.getValue() as number | null;
      return (
        <span className="inline-flex items-center justify-end gap-1.5">
          <span className={cn("size-2 rounded-full", lateColor(v))} aria-hidden />
          <span className={cn(isNum(v) && v >= 0.1 && "font-semibold text-danger")}>{isNum(v) ? pct(v) : "—"}</span>
        </span>
      );
    },
  },
];

export function NetworkSection({
  filters,
  selected,
  onSelected,
}: {
  filters: Filters;
  selected: string[];
  onSelected: (ids: string[]) => void;
}) {
  const q = useNetwork(filters);
  const d = q.data;
  const toggle = (id: string) => onSelected(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);

  return (
    <Section
      title="배송 네트워크"
      description="지도에서 배송지를 클릭하거나 표에서 선택하면 서로 강조되고 아래 원장이 좁혀집니다."
      actions={
        d && (
          <span className="text-[12px] text-muted-foreground tabular">
            배송지 {d.stores.length.toLocaleString()}곳
            {d.idle_stores.length > 0 && ` · 기간 내 배송 없음 ${d.idle_stores.length}곳`} · 센터 {d.warehouses.length}곳
          </span>
        )
      }
    >
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !d ? (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
          <Skeleton className="h-[460px] rounded-lg" />
          <Skeleton className="h-[460px] rounded-lg" />
        </div>
      ) : d.stores.length + d.idle_stores.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border-strong px-4 py-10 text-center text-[13px] text-muted-foreground">
          좌표가 있는 배송지가 없습니다. 배송지(stores) 데이터에 위도·경도를 포함해 업로드하세요.
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
          <NetworkMap stores={d.stores} idle={d.idle_stores} warehouses={d.warehouses} selected={selected} onToggle={toggle} />
          <DataTable
            data={d.stores}
            columns={COLUMNS}
            rowKey={(r) => r.store_id}
            selected={selected}
            onSelectedChange={onSelected}
            height={460}
            initialSort={[{ id: "late_rate", desc: true }]}
            ariaLabel="배송지 목록"
          />
        </div>
      )}
    </Section>
  );
}
