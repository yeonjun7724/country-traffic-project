"use client";

import { Info } from "lucide-react";

import { dateTimeLabel } from "@/lib/format";
import type { NavItem } from "@/lib/nav";
import { useWorkspace } from "@/lib/workspace";

import { Pill, SampleDataBadge } from "./badges";

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
    <div className="mb-5 space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-1.5 text-xs font-medium text-subtle-foreground">
            <Icon className="size-3.5" />
            <span>{nav.title}</span>
          </div>
          <h1 className="text-[22px] font-semibold leading-tight tracking-tight text-foreground">{title}</h1>
          {description && <p className="text-[13px] text-muted-foreground">{description}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {me?.is_demo && <SampleDataBadge />}
          {me && (
            <Pill tone="neutral">
              {me.data_updated_at ? `데이터 갱신 ${dateTimeLabel(me.data_updated_at)}` : "운영 데이터 없음"}
            </Pill>
          )}
          {actions}
        </div>
      </div>
      {me?.is_demo && (
        <div className="flex items-start gap-2 rounded-lg border border-kind-demo/25 bg-kind-demo/[0.06] px-3 py-2 text-[12.5px] text-foreground/80">
          <Info className="mt-px size-3.5 shrink-0 text-kind-demo" />
          <span>
            샘플 워크스페이스입니다. 화면의 운영 수치는 시연용 가상 데이터로 계산한 값이며 실제 성과가 아닙니다. 실제 데이터는{" "}
            <b className="font-medium">내 워크스페이스</b>에 업로드하세요.
          </span>
        </div>
      )}
    </div>
  );
}
