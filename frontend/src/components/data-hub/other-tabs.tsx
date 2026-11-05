"use client";

import { AlertTriangle, ChevronRight, Download, Plug } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { KindBadge, Pill } from "@/components/common/badges";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Skeleton } from "@/components/ui/skeleton";
import { download, type Schemas } from "@/lib/api";
import { num, pct } from "@/lib/format";
import { useEntities, useIntegrations, useQuality, useSchema } from "@/lib/queries";
import { cn } from "@/lib/utils";

// ── 데이터 품질 ─────────────────────────────────────────────────────────
export function QualityTab() {
  const q = useQuality();
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (q.isLoading) return <Skeleton className="h-96" />;
  const d = q.data!;
  if (d.entities.length === 0)
    return <EmptyState title="활성 데이터가 없습니다" description="업로드 후 컬럼별 결측률·고유값·저장 시 경고가 표시됩니다." />;
  return (
    <div className="space-y-4">
      {d.linkage.length > 0 && (
        <section className="rounded-xl border border-border bg-card p-4 shadow-card">
          <h3 className="text-[13.5px] font-semibold">배송 원장 연결 품질</h3>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">KPI 계산에서 빠지거나 ‘계산 불가’가 되는 배송 건 수</p>
          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
            {d.linkage.map((l) => (
              <div key={l.check} className="rounded-lg border border-border px-3 py-2.5">
                <p className="text-[11.5px] text-muted-foreground">{l.check}</p>
                <p className={cn("mt-0.5 text-[18px] font-semibold tabular", l.count > 0 ? "text-warning" : "text-foreground")}>
                  {num(l.count)}
                  <span className="ml-1 text-[11.5px] font-normal text-subtle-foreground">/ {num(l.total)}</span>
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
      <div className="space-y-2">
        {d.entities.map((e) => (
          <EntityQualityRow key={e.entity} e={e} />
        ))}
      </div>
    </div>
  );
}

function EntityQualityRow({ e }: { e: Schemas["EntityQuality"] }) {
  const [open, setOpen] = useState(false);
  const worst = Math.max(0, ...e.columns.map((c) => c.missing_rate));
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="overflow-hidden rounded-xl border border-border bg-card shadow-card">
      <CollapsibleTrigger className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/40">
        <ChevronRight className={cn("size-4 text-subtle-foreground transition-transform", open && "rotate-90")} />
        <span className="text-[13.5px] font-semibold">{e.label}</span>
        <span className="text-[12px] text-muted-foreground tabular">{num(e.rows)}행 · {e.columns.length}열</span>
        <span className="ml-auto flex items-center gap-2">
          {e.warnings.length > 0 && <Pill tone="warning">경고 {e.warnings.length}</Pill>}
          <span className="text-[12px] text-muted-foreground">최대 결측 {pct(worst)}</span>
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent className="border-t border-border">
        {e.warnings.map((w) => (
          <p key={w} className="flex items-start gap-2 border-b border-border bg-warning/[0.06] px-4 py-2 text-[12.5px]">
            <AlertTriangle className="mt-px size-3.5 shrink-0 text-warning" /> {w}
          </p>
        ))}
        <table className="w-full text-[12.5px]">
          <thead className="text-[11.5px] text-muted-foreground">
            <tr className="border-b border-border">
              <th className="px-4 py-2 text-left font-medium">필드</th>
              <th className="px-4 py-2 text-left font-medium">결측률</th>
              <th className="px-4 py-2 text-right font-medium">결측</th>
              <th className="px-4 py-2 text-right font-medium">고유값</th>
            </tr>
          </thead>
          <tbody>
            {e.columns.map((c) => (
              <tr key={c.field} className="border-b border-border last:border-0">
                <td className="px-4 py-1.5 font-mono text-[12px]">{c.field}</td>
                <td className="px-4 py-1.5">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-32 overflow-hidden rounded-full bg-muted">
                      <span
                        className={cn("block h-full rounded-full", c.missing_rate > 0.2 ? "bg-danger" : c.missing_rate > 0 ? "bg-warning" : "bg-success")}
                        style={{ width: `${Math.max(c.missing_rate * 100, c.missing_rate > 0 ? 2 : 0)}%` }}
                      />
                    </span>
                    <span className="w-12 text-[11.5px] text-muted-foreground tabular">{pct(c.missing_rate)}</span>
                  </div>
                </td>
                <td className="px-4 py-1.5 text-right tabular">{num(c.missing)}</td>
                <td className="px-4 py-1.5 text-right tabular">{num(c.unique)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CollapsibleContent>
    </Collapsible>
  );
}

// ── 스키마·템플릿 ───────────────────────────────────────────────────────
export function SchemaTab() {
  const ents = useEntities();
  const [entity, setEntity] = useState("orders");
  const s = useSchema(entity);
  return (
    <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
      <nav className="space-y-0.5 rounded-xl border border-border bg-card p-1.5 shadow-card" aria-label="데이터 유형">
        {(ents.data ?? []).map((e) => (
          <button
            key={e.entity}
            type="button"
            onClick={() => setEntity(e.entity)}
            className={cn(
              "flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-left text-[13px]",
              entity === e.entity ? "bg-primary/[0.08] font-medium text-primary" : "hover:bg-muted/60",
            )}
          >
            {e.label}
            <span className="font-mono text-[10.5px] text-subtle-foreground">{e.entity}</span>
          </button>
        ))}
      </nav>
      <section className="rounded-xl border border-border bg-card shadow-card">
        {!s.data ? (
          <Skeleton className="m-4 h-72" />
        ) : (
          <>
            <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
              <div>
                <h3 className="text-[14px] font-semibold">{s.data.label}</h3>
                <p className="mt-0.5 text-[12.5px] text-muted-foreground">
                  기본키 <code className="font-mono">{s.data.primary_key.join(", ")}</code>
                  {s.data.foreign_keys.length > 0 &&
                    ` · 참조 ${s.data.foreign_keys.map((f) => `${f.column} → ${f.ref_entity}`).join(", ")}`}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => download(`/api/data/templates/${entity}.csv`, undefined, `template_${entity}.csv`).catch((e) => toast.error((e as Error).message))}
              >
                <Download className="size-3.5" /> 양식 CSV
              </Button>
            </header>
            <div className="overflow-x-auto">
              <table className="w-full text-[12.5px]">
                <thead className="text-[11.5px] text-muted-foreground">
                  <tr className="border-b border-border">
                    {["필드", "이름", "타입", "단위·허용값·범위", "자동 매핑 별칭"].map((h) => (
                      <th key={h} className="px-4 py-2 text-left font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {s.data.fields.map((f) => (
                    <tr key={f.name} className="border-b border-border last:border-0 align-top">
                      <td className="px-4 py-2 font-mono text-[12px]">
                        {f.name}
                        {f.required && <span className="ml-0.5 text-danger">*</span>}
                      </td>
                      <td className="px-4 py-2">{f.label}</td>
                      <td className="px-4 py-2 text-muted-foreground">{f.type}</td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {[f.unit, f.allowed?.length ? f.allowed.join(" / ") : "", f.min != null || f.max != null ? `${f.min ?? ""} ~ ${f.max ?? ""}` : ""]
                          .filter(Boolean)
                          .join(" · ") || "—"}
                      </td>
                      <td className="max-w-72 px-4 py-2 text-[11.5px] text-subtle-foreground">{f.aliases?.join(", ") || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

// ── 외부 연동 ───────────────────────────────────────────────────────────
export function IntegrationsTab() {
  const q = useIntegrations();
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (q.isLoading) return <Skeleton className="h-80" />;
  const d = q.data!;
  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-border bg-card shadow-card">
        <header className="border-b border-border px-4 py-3">
          <h3 className="text-[14px] font-semibold">시스템 연동</h3>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">
            ERP·WMS·TMS 실시간 연동은 아직 구현되지 않았습니다. 고객사 시스템 정보와 계정이 필요하며, 연동 데이터도 업로드와 같은 검증을 거치게 됩니다.
          </p>
        </header>
        <ul className="grid gap-px bg-border sm:grid-cols-2">
          {d.connectors.map((c) => (
            <li key={c.name} className="flex items-start gap-3 bg-card px-4 py-3">
              <span className="flex size-8 items-center justify-center rounded-md bg-muted">
                <Plug className="size-4 text-muted-foreground" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium">{c.name}</span>
                  <span className="rounded-sm bg-muted px-1 text-[10.5px] text-muted-foreground">{c.system}</span>
                </div>
                <p className="text-[12px] text-muted-foreground">{c.detail}</p>
              </div>
              <Pill tone={c.configured ? "success" : "neutral"}>{c.configured ? "연결됨" : "미구현"}</Pill>
            </li>
          ))}
        </ul>
      </section>
      <section className="rounded-xl border border-external/20 bg-card shadow-card">
        <header className="flex items-start justify-between gap-2 border-b border-border px-4 py-3">
          <div>
            <h3 className="text-[14px] font-semibold">외부 위험 데이터 (기존 분석 산출물)</h3>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">고속도로·전국 유가·교통량 — 기업 실적과 섞지 않습니다.</p>
          </div>
          <Pill tone="external">외부 지표</Pill>
        </header>
        {d.missing.length > 0 && (
          <p className="border-b border-border bg-danger/[0.06] px-4 py-2 text-[12.5px] text-danger">누락: {d.missing.join(", ")}</p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead className="text-[11.5px] text-muted-foreground">
              <tr className="border-b border-border">
                {["데이터", "성격", "기간", "표본", "방법", "주의"].map((h) => (
                  <th key={h} className="px-4 py-2 text-left font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.external.map((p) => (
                <tr key={p.key} className="border-b border-border last:border-0 align-top">
                  <td className="px-4 py-2">
                    <div className="font-medium">{p.key}</div>
                    <div className="max-w-64 truncate text-[11px] text-subtle-foreground">{p.source}</div>
                  </td>
                  <td className="px-4 py-2">
                    <KindBadge kind={p.kind} />
                  </td>
                  <td className="px-4 py-2 text-muted-foreground tabular">{p.period_start ? `${p.period_start} ~ ${p.period_end}` : "—"}</td>
                  <td className="px-4 py-2 tabular">{num(p.n)}</td>
                  <td className="max-w-56 px-4 py-2 text-muted-foreground">{p.method ?? "—"}</td>
                  <td className="max-w-72 px-4 py-2 text-[12px] text-warning">{p.warnings.join(" · ") || <span className="text-subtle-foreground">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
