"use client";

import { MapPin, Target, Wallet } from "lucide-react";

import type { Metric } from "@/lib/api";
import type { Filters } from "@/lib/filters";
import { deltaText, isNum, metricText, pct } from "@/lib/format";
import { useCostToServe } from "@/lib/queries";
import { cn } from "@/lib/utils";

type Insight = { icon: typeof Target; tone: "good" | "bad" | "neutral"; title: string; body: string };

/** 이번 기간 요약 — 계산된 KPI·집계에서 규칙으로 만든 문장 (추정·생성 없음) */
export function Insights({ kpis, filters }: { kpis: Metric[] | undefined; filters: Filters }) {
  const region = useCostToServe(filters, "region");
  if (!kpis) return null;
  const by = new Map(kpis.map((k) => [k.key, k]));
  const out: Insight[] = [];

  const otif = by.get("otif");
  if (otif?.ok && isNum(otif.target)) {
    const gap = (otif.value! - otif.target) * 100;
    out.push({
      icon: Target,
      tone: gap >= 0 ? "good" : "bad",
      title: gap >= 0 ? "OTIF 목표 달성" : "OTIF 목표 미달",
      body: `${metricText(otif.value, "%")} · 목표 대비 ${gap >= 0 ? "+" : ""}${gap.toFixed(1)}%p${isNum(otif.delta_pct) ? ` · 직전 기간 ${deltaText(otif.delta_pct)}` : ""}`,
    });
  }
  const cost = by.get("cost");
  const cpo = by.get("cost_per_order");
  if (cost?.ok) {
    const up = (cost.delta_pct ?? 0) > 0;
    out.push({
      icon: Wallet,
      tone: !isNum(cost.delta_pct) ? "neutral" : up ? "bad" : "good",
      title: `총 운송비 ${metricText(cost.value, "원")}`,
      body: `${isNum(cost.delta_pct) ? `직전 기간 대비 ${deltaText(cost.delta_pct)}` : "직전 기간 비교 불가"}${cpo?.ok ? ` · 주문당 ${metricText(cpo.value, "원")}` : ""}`,
    });
  }
  const rows = (region.data ?? []).filter((r) => isNum(r.late_rate) && r.shipments >= 10);
  if (rows.length) {
    const worst = [...rows].sort((a, b) => (b.late_rate ?? 0) - (a.late_rate ?? 0))[0];
    const late = by.get("late_rate");
    out.push({
      icon: MapPin,
      tone: (worst.late_rate ?? 0) > (late?.target ?? 0.05) ? "bad" : "neutral",
      title: `지연율 최고 권역: ${worst.key ?? "(미지정)"}`,
      body: `지연율 ${pct(worst.late_rate)} · 배송 ${worst.shipments.toLocaleString()}건${late?.ok ? ` (전체 ${pct(late.value)})` : ""}`,
    });
  }
  if (!out.length) return null;

  return (
    <section aria-label="이번 기간 요약" className="mb-4 grid gap-3 md:grid-cols-3">
      {out.map((i) => (
        <div
          key={i.title}
          className={cn(
            "relative overflow-hidden rounded-xl border bg-card px-4 py-3.5 shadow-card",
            i.tone === "bad" ? "border-danger/20" : i.tone === "good" ? "border-success/25" : "border-border",
          )}
        >
          <span
            className={cn("absolute inset-y-0 left-0 w-1", i.tone === "bad" ? "bg-danger/70" : i.tone === "good" ? "bg-success/70" : "bg-border-strong")}
            aria-hidden
          />
          <div className="flex items-start gap-3">
            <span
              className={cn(
                "flex size-8 shrink-0 items-center justify-center rounded-lg",
                i.tone === "bad" ? "bg-danger/10 text-danger" : i.tone === "good" ? "bg-success/10 text-success" : "bg-muted text-muted-foreground",
              )}
            >
              <i.icon className="size-4" />
            </span>
            <div className="min-w-0">
              <p className="text-[13.5px] font-semibold">{i.title}</p>
              <p className="mt-0.5 text-[12.5px] text-muted-foreground tabular">{i.body}</p>
            </div>
          </div>
        </div>
      ))}
    </section>
  );
}
