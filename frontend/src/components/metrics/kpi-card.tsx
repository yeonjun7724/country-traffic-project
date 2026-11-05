"use client";

import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import type { Metric } from "@/lib/api";
import { deltaText, isNum, metricParts, metricText } from "@/lib/format";
import { cn } from "@/lib/utils";

/** 좋아짐/나빠짐 판정 (색만으로 구분하지 않도록 아이콘·텍스트 병기) */
export function deltaTone(m: Metric): "good" | "bad" | "flat" | "none" {
  if (!isNum(m.delta_pct)) return "none";
  if (Math.abs(m.delta_pct) < 0.05) return "flat";
  return (m.delta_pct > 0) === m.higher_is_better ? "good" : "bad";
}

export function DeltaChip({ m, className }: { m: Metric; className?: string }) {
  const t = deltaTone(m);
  if (t === "none") return <span className={cn("text-[11.5px] text-subtle-foreground", className)}>직전 기간 없음</span>;
  const Icon = t === "flat" ? Minus : (m.delta_pct ?? 0) > 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 rounded-md px-1 py-px text-[12px] font-semibold tabular",
        t === "good" && "bg-success/10 text-success",
        t === "bad" && "bg-danger/10 text-danger",
        t === "flat" && "bg-muted text-muted-foreground",
        className,
      )}
      aria-label={`직전 기간 대비 ${deltaText(m.delta_pct)} (${t === "good" ? "개선" : t === "bad" ? "악화" : "변화 없음"})`}
    >
      <Icon className="size-3.5" strokeWidth={2.5} />
      {deltaText(m.delta_pct)}
    </span>
  );
}

export function KpiCard({
  m,
  onOpen,
  variant = "card",
}: {
  m: Metric;
  onOpen: () => void;
  /** card: 독립 카드 / cell: 그룹 패널 안의 칸 */
  variant?: "card" | "cell";
}) {
  const parts = metricParts(m.value, m.unit);
  const hasTarget = m.ok && isNum(m.target);
  const meets = hasTarget && (m.higher_is_better ? m.value! >= m.target! : m.value! <= m.target!);

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "group relative flex h-full min-w-0 flex-col p-4 text-left transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
        variant === "card"
          ? "rounded-xl border border-border bg-card shadow-card hover:border-border-strong"
          : "hover:bg-muted/40",
      )}
      aria-label={`${m.label}: ${m.ok ? metricText(m.value, m.unit) : "계산 불가"}. 정의·산식 보기`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-[12.5px] font-medium text-muted-foreground">{m.label}</span>
        <span className="text-[11px] text-subtle-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
          정의 보기
        </span>
      </div>

      {m.ok ? (
        <>
          <div className="mt-2 flex items-baseline gap-1">
            <span
              className={cn(
                "font-semibold leading-none tracking-tight text-foreground tabular",
                variant === "card" ? "text-[26px]" : "text-[23px]",
              )}
            >
              {parts.value}
            </span>
            <span className="text-[13px] font-medium text-muted-foreground">{parts.unit}</span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1">
            <DeltaChip m={m} />
            {hasTarget && (
              <span className={cn("text-[11.5px] font-medium", meets ? "text-success" : "text-danger")}>
                {meets ? "목표 달성" : "목표 미달"} · {metricText(m.target, m.unit)}
              </span>
            )}
          </div>
          {hasTarget && m.unit === "%" && <TargetBar value={m.value!} target={m.target!} good={!!meets} higher={m.higher_is_better} />}
          <div className="mt-auto pt-2 text-[11px] text-subtle-foreground tabular">
            n={m.n?.toLocaleString() ?? "—"}
            {(m.warnings?.length ?? 0) > 0 && <span className="ml-1.5 text-warning">· 주의 {m.warnings!.length}</span>}
          </div>
        </>
      ) : (
        <div className="mt-2 space-y-1.5">
          <div className="text-[15px] font-semibold text-warning">계산 불가</div>
          <p className="line-clamp-2 text-[12px] leading-snug text-muted-foreground">{m.reason}</p>
        </div>
      )}
    </button>
  );
}

function TargetBar({ value, target, good, higher }: { value: number; target: number; good: boolean; higher: boolean }) {
  const scale = Math.max(value, target, 0.0001) * (higher ? 1.05 : 1.6);
  const v = Math.min(100, (value / scale) * 100);
  const t = Math.min(100, (target / scale) * 100);
  return (
    <div className="relative mt-2.5 h-1.5 w-full rounded-full bg-muted" aria-hidden>
      <div className={cn("h-full rounded-full", good ? "bg-success/70" : "bg-danger/70")} style={{ width: `${v}%` }} />
      <div className="absolute -top-0.5 h-2.5 w-0.5 rounded bg-foreground/60" style={{ left: `calc(${t}% - 1px)` }} />
    </div>
  );
}

/** 그룹 패널 안의 지표 행 — 라벨(좌) · 값과 증감(우). 좁은 폭에서도 라벨·값이 잘리지 않는다. */
export function KpiRow({ m, onOpen }: { m: Metric; onOpen: () => void }) {
  const parts = metricParts(m.value, m.unit);
  const hasTarget = m.ok && isNum(m.target);
  const meets = hasTarget && (m.higher_is_better ? m.value! >= m.target! : m.value! <= m.target!);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="group flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/40 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
      aria-label={`${m.label}: ${m.ok ? metricText(m.value, m.unit) : "계산 불가"}. 정의·산식 보기`}
    >
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-medium text-foreground/85">{m.label}</div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[11.5px] text-subtle-foreground tabular">
          {m.ok ? (
            <>
              {hasTarget ? (
                <span className={cn("font-medium", meets ? "text-success" : "text-danger")}>
                  {meets ? "목표 달성" : "목표 미달"} · {metricText(m.target, m.unit)}
                </span>
              ) : (
                <span>n={m.n?.toLocaleString() ?? "—"}</span>
              )}
              {(m.warnings?.length ?? 0) > 0 && <span className="text-warning">· 주의 {m.warnings!.length}</span>}
            </>
          ) : (
            <span className="line-clamp-1 text-warning">{m.reason}</span>
          )}
        </div>
      </div>
      {m.ok ? (
        <div className="flex shrink-0 flex-col items-end gap-1">
          <div className="flex items-baseline gap-0.5">
            <span className="text-[21px] font-semibold leading-none tracking-tight text-foreground tabular">{parts.value}</span>
            <span className="text-[12px] font-medium text-muted-foreground">{parts.unit}</span>
          </div>
          <DeltaChip m={m} className="text-[11.5px]" />
        </div>
      ) : (
        <span className="shrink-0 text-[14px] font-semibold text-warning">계산 불가</span>
      )}
    </button>
  );
}
