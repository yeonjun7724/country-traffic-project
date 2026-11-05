"use client";

import { Section } from "@/components/common/section";
import { ErrorState } from "@/components/common/states";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Filters } from "@/lib/filters";
import { isNum, pct, won } from "@/lib/format";
import { useCostToServe, type CtsDim } from "@/lib/queries";
import { cn } from "@/lib/utils";

const DIMS: { v: CtsDim; label: string }[] = [
  { v: "carrier", label: "운송사" },
  { v: "warehouse_id", label: "센터" },
  { v: "region", label: "권역" },
  { v: "customer_group", label: "거래처군" },
];

export function CostToServe({ filters, dim, onDim }: { filters: Filters; dim: CtsDim; onDim: (d: CtsDim) => void }) {
  const q = useCostToServe(filters, dim);
  const rows = q.data ?? [];
  const total = rows.reduce((s, r) => s + (r.cost ?? 0), 0);
  const maxLate = Math.max(0.0001, ...rows.map((r) => r.late_rate ?? 0));

  return (
    <Section
      title="Cost-to-Serve"
      description="기준별 운송비 비중·주문당 비용·지연율"
      actions={
        <ToggleGroup
          type="single"
          value={dim}
          onValueChange={(v) => v && onDim(v as CtsDim)}
          variant="outline"
          size="sm"
          aria-label="집계 기준"
        >
          {DIMS.map((d) => (
            <ToggleGroupItem key={d.v} value={d.v} className="px-2.5 text-[12px]">
              {d.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      }
      className="h-full"
      bodyClassName="p-0"
    >
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} className="m-4" />
      ) : q.isLoading ? (
        <div className="space-y-2 p-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-9" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <p className="px-4 py-10 text-center text-[13px] text-muted-foreground">해당 기간에 운송비가 있는 배송이 없습니다.</p>
      ) : (
        <div className={cn("overflow-auto", q.isFetching && "opacity-70 transition-opacity")} style={{ maxHeight: 300 }}>
          <table className="w-full text-[12.5px]">
            <thead className="sticky top-0 bg-card text-[11.5px] text-muted-foreground">
              <tr className="border-b border-border">
                <th className="px-4 py-2 text-left font-medium">{DIMS.find((d) => d.v === dim)?.label}</th>
                <th className="px-2 py-2 text-right font-medium">운송비 · 비중</th>
                <th className="px-2 py-2 text-right font-medium">주문당</th>
                <th className="px-4 py-2 text-right font-medium">지연율</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const share = total ? (r.cost ?? 0) / total : 0;
                return (
                  <tr key={String(r.key)} className="border-b border-border last:border-0 hover:bg-muted/40">
                    <td className="max-w-40 truncate px-4 py-2 font-medium">{r.key ?? "(미지정)"}</td>
                    <td className="px-2 py-2 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <span className="tabular">{won(r.cost)}</span>
                        <span className="relative h-1.5 w-14 overflow-hidden rounded-full bg-muted" aria-hidden>
                          <span className="absolute inset-y-0 left-0 rounded-full bg-chart-1" style={{ width: `${share * 100}%` }} />
                        </span>
                        <span className="w-10 text-right text-[11.5px] text-muted-foreground tabular">{pct(share, 0)}</span>
                      </div>
                    </td>
                    <td className="px-2 py-2 text-right tabular">{isNum(r.cost_per_order) ? `${won(r.cost_per_order)}원` : "—"}</td>
                    <td className="px-4 py-2 text-right">
                      <span
                        className={cn(
                          "tabular",
                          isNum(r.late_rate) && r.late_rate >= 0.1 && "font-medium text-danger",
                          isNum(r.late_rate) && r.late_rate === maxLate && "underline decoration-danger/40 underline-offset-2",
                        )}
                      >
                        {isNum(r.late_rate) ? pct(r.late_rate) : "—"}
                      </span>
                    </td>
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
