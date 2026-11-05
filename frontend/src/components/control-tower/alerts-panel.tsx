"use client";

import { AlertOctagon, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import Link from "next/link";

import { Section } from "@/components/common/section";
import type { Schemas } from "@/lib/api";
import { cn } from "@/lib/utils";

type Alert = Schemas["AlertOut"];

const SEV = {
  high: { icon: AlertOctagon, cls: "text-danger", label: "긴급" },
  medium: { icon: AlertTriangle, cls: "text-warning", label: "주의" },
  low: { icon: Info, cls: "text-info", label: "참고" },
} as const;

const LINK: Record<string, string | undefined> = { "데이터 허브": "/data-hub/" };

export function AlertsPanel({ alerts, loading }: { alerts: Alert[]; loading?: boolean }) {
  const sorted = [...alerts].sort((a, b) => order(a.severity) - order(b.severity));
  return (
    <Section
      title={
        <span className="flex items-center gap-2">
          확인이 필요한 항목
          {alerts.length > 0 && (
            <span className="rounded-full bg-danger/10 px-1.5 text-[11px] font-semibold text-danger tabular">{alerts.length}</span>
          )}
        </span>
      }
      description="알림 규칙(목표·허용치) 기준 · 앱 내 표시 전용, 외부 발송 없음"
      className="h-full"
      bodyClassName="p-0"
    >
      {loading ? (
        <div className="h-28" />
      ) : sorted.length === 0 ? (
        <div className="flex items-center gap-2 px-4 py-6 text-[13px] text-muted-foreground">
          <CheckCircle2 className="size-4 text-success" /> 현재 기준을 벗어난 항목이 없습니다.
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {sorted.map((a, i) => {
            const s = SEV[a.severity];
            const Icon = s.icon;
            const href = LINK[a.source];
            return (
              <li key={i} className="flex items-start gap-3 px-4 py-2.5">
                <Icon className={cn("mt-0.5 size-4 shrink-0", s.cls)} aria-label={s.label} />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-foreground">{a.rule}</p>
                  <p className="text-[12.5px] text-muted-foreground tabular">{a.message}</p>
                </div>
                <span className="shrink-0 rounded-md bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">{a.source}</span>
                {href && (
                  <Link href={href} className="shrink-0 text-[12px] font-medium text-primary hover:underline">
                    열기
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

const order = (s: string) => (s === "high" ? 0 : s === "medium" ? 1 : 2);
