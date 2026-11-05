"use client";

import { useState } from "react";

import { KpiRow } from "@/components/metrics/kpi-card";
import { MetricSheet } from "@/components/metrics/metric-sheet";
import { Skeleton } from "@/components/ui/skeleton";
import type { Metric } from "@/lib/api";

const GROUPS: { title: string; keys: string[] }[] = [
  { title: "서비스 수준", keys: ["otif", "late_rate", "load_factor"] },
  { title: "운송 비용", keys: ["cost", "cost_per_order", "cost_per_km"] },
  { title: "물동량", keys: ["orders", "shipments", "volume_kg"] },
];

/** KPI 9종을 3개 그룹 패널로. 칸을 누르면 정의·산식 시트. */
export function KpiGroups({ kpis, loading }: { kpis: Metric[] | undefined; loading?: boolean }) {
  const [open, setOpen] = useState<Metric | null>(null);
  const by = new Map((kpis ?? []).map((k) => [k.key, k]));

  return (
    <>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {GROUPS.map((g) => (
          <section key={g.title} className="overflow-hidden rounded-xl border border-border bg-card shadow-card" aria-label={g.title}>
            <h2 className="border-b border-border bg-muted/30 px-4 py-2 text-[12px] font-semibold text-muted-foreground">{g.title}</h2>
            <div className="divide-y divide-border">
              {g.keys.map((k) => {
                const m = by.get(k);
                return loading || !m ? (
                  <div key={k} className="flex items-center justify-between px-4 py-3.5">
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-6 w-24" />
                  </div>
                ) : (
                  <KpiRow key={k} m={m} onOpen={() => setOpen(m)} />
                );
              })}
            </div>
          </section>
        ))}
      </div>
      <MetricSheet metric={open} onClose={() => setOpen(null)} />
    </>
  );
}
