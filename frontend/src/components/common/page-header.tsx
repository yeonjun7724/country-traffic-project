"use client";

import type { NavItem } from "@/lib/nav";
import { useWorkspace } from "@/lib/workspace";

import { SampleDataBadge } from "./badges";

/** 화면 제목 영역 — 제목·설명 + 우측 액션. 데이터 기준 시각·샘플 안내는 상단 바/배너가 담당. */
export function PageHeader({
  nav,
  title,
  description,
  actions,
}: {
  nav: NavItem;
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  const { me } = useWorkspace();
  const Icon = nav.icon;
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3 animate-in fade-in slide-in-from-bottom-1 duration-300">
      <div className="flex min-w-0 items-start gap-3.5">
        <span className="mt-0.5 hidden size-10 shrink-0 items-center justify-center rounded-xl border border-border bg-card text-primary shadow-card sm:flex">
          <Icon className="size-5" strokeWidth={1.75} />
        </span>
        <div className="min-w-0">
          <h1 className="text-[24px] font-semibold leading-tight tracking-[-0.02em] text-foreground">{title}</h1>
          {description && <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{description}</p>}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {me?.is_demo && <SampleDataBadge />}
        {actions}
      </div>
    </div>
  );
}
