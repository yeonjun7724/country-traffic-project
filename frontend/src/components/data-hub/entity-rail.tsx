"use client";

import { CheckCircle2, Circle } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import type { Schemas } from "@/lib/api";
import { num } from "@/lib/format";
import { cn } from "@/lib/utils";

type E = Schemas["EntityStatus"];

/** 업로드 순서(외래키 의존)대로 엔터티 적재 현황 — 선택하면 오른쪽 업로드 대상이 바뀜 */
export function EntityRail({ items, value, onChange }: { items: E[] | undefined; value: string; onChange: (e: string) => void }) {
  if (!items)
    return (
      <div className="space-y-1.5 p-2">
        {Array.from({ length: 10 }).map((_, i) => (
          <Skeleton key={i} className="h-12" />
        ))}
      </div>
    );
  const loaded = new Set(items.filter((i) => i.loaded).map((i) => i.entity));
  return (
    <ol className="space-y-0.5 p-1.5" aria-label="데이터 유형 (업로드 순서)">
      {items.map((e) => {
        const missingRefs = e.required_refs.filter((r) => !loaded.has(r));
        const active = e.entity === value;
        return (
          <li key={e.entity}>
            <button
              type="button"
              onClick={() => onChange(e.entity)}
              aria-current={active ? "step" : undefined}
              className={cn(
                "flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors",
                active ? "bg-primary/[0.07] ring-1 ring-primary/25" : "hover:bg-muted/60",
              )}
            >
              <span className="mt-0.5 flex w-4 justify-center">
                {e.loaded ? <CheckCircle2 className="size-4 text-success" /> : <Circle className="size-4 text-border-strong" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5">
                  <span className="text-[11px] text-subtle-foreground tabular">{e.order}</span>
                  <span className={cn("truncate text-[13px] font-medium", active && "text-primary")}>{e.label}</span>
                  {e.demo && <span className="rounded-sm bg-kind-demo/10 px-1 text-[10px] font-semibold text-kind-demo">샘플</span>}
                </span>
                <span className="block truncate text-[11.5px] text-muted-foreground tabular">
                  {e.loaded ? `v${e.version} · ${num(e.rows)}행${e.period ? ` · ${e.period}` : ""}` : missingRefs.length ? `먼저 필요: ${missingRefs.join(", ")}` : "미적재"}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
