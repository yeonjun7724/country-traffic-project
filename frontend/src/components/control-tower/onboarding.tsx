"use client";

import { ArrowRight, CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";

import { Section } from "@/components/common/section";
import { Skeleton } from "@/components/ui/skeleton";
import { useEntities } from "@/lib/queries";
import { cn } from "@/lib/utils";

/** KPI 계산에 꼭 필요한 데이터 (없으면 KPI 대부분이 '계산 불가') */
const CORE = ["warehouses", "stores", "orders", "shipments"];

/**
 * 업로드 순서 체크리스트 — 업로드 상태(/api/data/entities)만 보여준다. 수치를 추정하거나 만들지 않는다.
 * '다음'은 참조 데이터가 모두 올라간 첫 미업로드 항목. compact 는 일부만 올린 워크스페이스용 한 줄 안내.
 */
export function Onboarding({ compact = false }: { compact?: boolean }) {
  const q = useEntities();
  if (!q.data) return compact ? null : <Skeleton className="h-64 rounded-xl" />;
  const items = [...q.data].sort((a, b) => a.order - b.order);
  const loaded = new Set(items.filter((i) => i.loaded).map((i) => i.entity));
  const next = items.find((i) => !i.loaded && i.required_refs.every((r) => loaded.has(r)));
  const done = items.filter((i) => i.loaded).length;
  const missingCore = items.filter((i) => CORE.includes(i.entity) && !i.loaded);

  if (compact) {
    if (!missingCore.length) return null;
    return (
      <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-warning/30 bg-warning/[0.06] px-4 py-2.5 text-[12.5px]">
        <span className="font-medium">KPI 계산에 필요한 데이터가 아직 없습니다</span>
        <span className="text-muted-foreground">미업로드: {missingCore.map((i) => i.label).join(" · ")}</span>
        {next && (
          <Link href={`/data-hub/?entity=${next.entity}`} className="ml-auto inline-flex items-center gap-0.5 font-medium text-primary-text hover:underline">
            다음: {next.label} 업로드 <ArrowRight className="size-3" />
          </Link>
        )}
      </div>
    );
  }

  return (
    <Section title={`데이터 준비 ${done}/${items.length}`} description="참조 관계 때문에 위에서부터 순서대로 올립니다. 각 단계는 양식 다운로드·자동 컬럼 매핑·검증을 거쳐 저장됩니다." bodyClassName="p-0">
      <ol className="divide-y divide-border" aria-label="업로드 순서">
        {items.map((i) => {
          const isNext = next?.entity === i.entity;
          const blocked = !i.loaded && !i.required_refs.every((r) => loaded.has(r));
          return (
            <li key={i.entity} className={cn("flex items-center gap-3 px-4 py-2.5", isNext && "bg-primary/[0.04]")}>
              {i.loaded ? (
                <CheckCircle2 className="size-4 shrink-0 text-success" aria-label="완료" />
              ) : (
                <Circle className={cn("size-4 shrink-0", isNext ? "text-primary" : "text-border-strong")} aria-label="미완료" />
              )}
              <span className="w-5 text-[12px] text-subtle-foreground tabular">{i.order}</span>
              <div className="min-w-0 flex-1">
                <p className={cn("text-[13px]", i.loaded ? "text-muted-foreground" : "font-medium")}>
                  {i.label}
                  {CORE.includes(i.entity) && <span className="ml-1.5 text-[11px] font-normal text-subtle-foreground">KPI 필수</span>}
                </p>
                {blocked && <p className="text-[11.5px] text-subtle-foreground">먼저 필요: {i.required_refs.filter((r) => !loaded.has(r)).map((r) => items.find((x) => x.entity === r)?.label ?? r).join(" · ")}</p>}
                {i.loaded && i.rows != null && <p className="text-[11.5px] text-subtle-foreground tabular">{i.rows.toLocaleString()}행 · v{i.version}</p>}
              </div>
              {!i.loaded && !blocked && (
                <Link href={`/data-hub/?entity=${i.entity}`} className={cn("inline-flex shrink-0 items-center gap-0.5 text-[12.5px] font-medium hover:underline", isNext ? "text-primary-text" : "text-muted-foreground")}>
                  업로드 <ArrowRight className="size-3" />
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </Section>
  );
}
