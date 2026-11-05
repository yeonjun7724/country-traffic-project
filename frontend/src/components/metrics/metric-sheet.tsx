"use client";

import { AlertTriangle } from "lucide-react";

import { KindBadge } from "@/components/common/badges";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import type { Metric } from "@/lib/api";
import { isNum, metricText, num } from "@/lib/format";

import { DeltaChip } from "./kpi-card";

/** KPI 정의·산식·분자·분모·표본·기간·경고 — 수치의 근거를 숨기지 않는다 */
export function MetricSheet({ metric, onClose }: { metric: Metric | null; onClose: () => void }) {
  const m = metric;
  return (
    <Sheet open={!!m} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full gap-0 p-0 sm:max-w-md">
        {m && (
          <>
            <SheetHeader className="border-b border-border px-5 py-4">
              <div className="flex items-center gap-2">
                <KindBadge kind={m.kind} />
                <span className="text-[11.5px] text-subtle-foreground">{m.period ? `기간 ${m.period}` : ""}</span>
              </div>
              <SheetTitle className="text-lg">{m.label}</SheetTitle>
              <SheetDescription className="sr-only">{m.label} 지표의 정의와 산식</SheetDescription>
              {m.ok ? (
                <div className="flex items-baseline gap-3 pt-1">
                  <span className="text-3xl font-semibold tracking-tight tabular">{metricText(m.value, m.unit)}</span>
                  <DeltaChip m={m} />
                </div>
              ) : (
                <p className="pt-1 text-sm">
                  <span className="font-semibold text-warning">계산 불가</span>
                  <span className="text-muted-foreground"> · {m.reason}</span>
                </p>
              )}
            </SheetHeader>
            <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5 text-[13px]">
              <Block title="정의">
                <p className="leading-relaxed text-foreground/90">{m.definition || "—"}</p>
              </Block>
              {m.formula && (
                <Block title="산식">
                  <code className="block rounded-md border border-border bg-muted/60 px-3 py-2 font-mono text-[12px] leading-relaxed">
                    {m.formula}
                  </code>
                </Block>
              )}
              <Block title="계산 근거">
                <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border">
                  <Cell k="분자" v={isNum(m.numerator) ? num(m.numerator, m.numerator % 1 ? 2 : 0) : "—"} />
                  <Cell k="분모" v={isNum(m.denominator) ? num(m.denominator, m.denominator % 1 ? 2 : 0) : "—"} />
                  <Cell k="표본(n)" v={m.n?.toLocaleString() ?? "—"} />
                  <Cell k="단위" v={m.unit || "—"} />
                  <Cell k="직전 동일 기간" v={metricText(m.previous, m.unit)} />
                  <Cell k="목표" v={isNum(m.target) ? `${metricText(m.target, m.unit)} (${m.higher_is_better ? "이상" : "이하"})` : "미설정"} />
                </dl>
              </Block>
              {(m.warnings?.length ?? 0) > 0 && (
                <Block title="데이터 주의사항">
                  <ul className="space-y-1.5">
                    {m.warnings!.map((w) => (
                      <li key={w} className="flex gap-2 rounded-md bg-warning/[0.07] px-2.5 py-2 text-[12.5px]">
                        <AlertTriangle className="mt-px size-3.5 shrink-0 text-warning" />
                        <span>{w}</span>
                      </li>
                    ))}
                  </ul>
                </Block>
              )}
              <p className="text-[11.5px] leading-relaxed text-subtle-foreground">
                값은 업로드된 데이터로 계산한 {m.kind_label} 수치입니다. 직전 기간은 선택 기간과 같은 길이의 바로 앞 기간입니다.
              </p>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-[11.5px] font-semibold uppercase tracking-wide text-subtle-foreground">{title}</h3>
      {children}
    </div>
  );
}

function Cell({ k, v }: { k: string; v: string }) {
  return (
    <div className="bg-card px-3 py-2.5">
      <dt className="text-[11.5px] text-muted-foreground">{k}</dt>
      <dd className="mt-0.5 font-medium tabular">{v}</dd>
    </div>
  );
}
