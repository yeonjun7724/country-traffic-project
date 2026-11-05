"use client";

import { AlertOctagon, AlertTriangle, CheckCircle2, FileSpreadsheet, FileText, Info, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { Pill } from "@/components/common/badges";
import { FilterBar } from "@/components/common/filter-bar";
import { Callout, DownloadButton, LineTabs, NumberField, STATUS_LABEL, useUrlTab } from "@/components/common/kit";
import { PageHeader } from "@/components/common/page-header";
import { Section } from "@/components/common/section";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { filterSearchParams, useFilters } from "@/lib/filters";
import { dateTimeLabel, num } from "@/lib/format";
import { navByKey } from "@/lib/nav";
import type { Action, Alert, Rules } from "@/lib/types";
import { useApi, useApiMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

const NAV = navByKey("reports");

export function ReportsScreen() {
  const [tab, setTab] = useUrlTab(["report", "alerts", "actions"]);
  const actions = useApi<Action[]>("/api/actions");
  const open = (actions.data ?? []).filter((a) => a.status === "open" || a.status === "in_progress").length;
  return (
    <>
      <PageHeader nav={NAV} title="보고서 · 알림 · 조치" description="현재 필터가 그대로 적용된 리포트와 알림, 조치 워크플로" />
      <LineTabs
        value={tab}
        onChange={setTab}
        items={[
          { v: "report", label: "리포트" },
          { v: "alerts", label: "알림 규칙" },
          {
            v: "actions",
            label: (
              <span className="inline-flex items-center gap-1.5">
                조치 워크플로{open > 0 && <span className="rounded-full bg-warning/15 px-1.5 text-[11px] font-semibold text-warning tabular">{open}</span>}
              </span>
            ),
          },
        ]}
      />
      {tab === "report" && <ReportTab />}
      {tab === "alerts" && <AlertsTab />}
      {tab === "actions" && <ActionsTab />}
    </>
  );
}

function ReportTab() {
  const { filters } = useFilters();
  const meta = useApi<{ sections: string[]; default: string[] }>("/api/reports/meta", { staleTime: Infinity });
  const [secs, setSecs] = useState<string[] | null>(null);
  const sections = secs ?? meta.data?.default ?? [];
  const preview = useApi<{ sheet: string; rows: number }[]>(meta.data ? "/api/reports/preview" : null, { filters, query: { sections } });
  const params = filterSearchParams(filters, { sections });
  return (
    <div className="space-y-4">
      <FilterBar />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <Section title="포함 섹션" description="선택한 섹션이 Excel 시트와 요약 리포트에 들어갑니다.">
          {!meta.data ? (
            <Skeleton className="h-40" />
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {meta.data.sections.map((s) => {
                const on = sections.includes(s);
                return (
                  <label
                    key={s}
                    className={cn(
                      "flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2.5 text-[13px] transition-colors",
                      on ? "border-primary/40 bg-primary/[0.04]" : "border-border hover:bg-muted/40",
                    )}
                  >
                    <Checkbox checked={on} onCheckedChange={(v) => setSecs(v ? [...sections, s] : sections.filter((x) => x !== s))} />
                    {s}
                    {s.startsWith("외부") && <Pill tone="external" className="ml-auto">외부</Pill>}
                  </label>
                );
              })}
            </div>
          )}
        </Section>
        <Section title="미리보기" description="시트별 행 수" bodyClassName="space-y-3">
          {!preview.data ? (
            <Skeleton className="h-40" />
          ) : (
            <ul className="divide-y divide-border rounded-lg border border-border">
              {preview.data.map((p) => (
                <li key={p.sheet} className="flex items-center justify-between px-3 py-2 text-[12.5px]">
                  <span className="flex items-center gap-2">
                    <FileSpreadsheet className="size-3.5 text-success" />
                    {p.sheet}
                  </span>
                  <span className="text-muted-foreground tabular">{num(p.rows)}행</span>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-2">
            <DownloadButton path="/api/reports/excel" params={params} filename="logisrisk_report.xlsx" label="Excel 리포트" variant="default" disabled={!sections.length} />
            <DownloadButton path="/api/reports/summary.html" params={params} filename="executive_summary.html" label="경영진 요약 (HTML)" />
          </div>
          <p className="flex items-start gap-1.5 text-[11.5px] text-subtle-foreground">
            <FileText className="mt-px size-3.5 shrink-0" />
            PDF: 내려받은 HTML 을 브라우저로 열고 인쇄 → ‘PDF로 저장’. 서버에서 PDF 를 직접 만들지는 않습니다 (한글 글꼴 번들 필요).
          </p>
        </Section>
      </div>
    </div>
  );
}

const SEV = {
  high: { icon: AlertOctagon, cls: "text-danger", label: "긴급" },
  medium: { icon: AlertTriangle, cls: "text-warning", label: "주의" },
  low: { icon: Info, cls: "text-info", label: "참고" },
} as const;

function AlertsTab() {
  const { filters } = useFilters();
  const { can } = useWorkspace();
  const q = useApi<{ rules: Rules; alerts: Alert[]; period: string }>("/api/alerts", { filters });
  const [rules, setRules] = useState<Rules | null>(null);
  useEffect(() => {
    if (q.data && !rules) setRules(q.data.rules);
  }, [q.data, rules]);
  const saveRules = useApiMutation<void, Rules>(() => ({ path: "/api/alerts/rules", method: "PUT", body: rules }), { success: "알림 규칙을 저장했습니다" });
  const createAction = useApiMutation<Alert, { id: number }>((a) => ({ path: "/api/actions", body: { title: `[${a.rule}] ${a.message}`, source: `알림:${a.source}`, detail: q.data?.period ?? "" } }), {
    success: (r) => `조치 #${r.id} 를 만들었습니다`,
  });
  const edit = can("settings.manage");
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data || !rules) return <Skeleton className="h-96" />;
  const set = (k: keyof Rules, v: number) => setRules({ ...rules, [k]: v });
  return (
    <div className="space-y-4">
      <FilterBar />
      <Callout tone="info">알림은 앱 안에서만 표시됩니다. 이메일·메신저 등 외부 발송 기능은 구현하지 않았으며, 추가하려면 별도 설정·승인이 필요합니다.</Callout>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <Section title={`현재 발생 알림 ${q.data.alerts.length}`} description={q.data.period} bodyClassName="p-0">
          {q.data.alerts.length === 0 ? (
            <p className="flex items-center gap-2 px-4 py-6 text-[13px] text-muted-foreground">
              <CheckCircle2 className="size-4 text-success" /> 기준을 벗어난 항목이 없습니다.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {q.data.alerts.map((a, i) => {
                const s = SEV[a.severity];
                return (
                  <li key={i} className="flex items-start gap-3 px-4 py-3">
                    <s.icon className={cn("mt-0.5 size-4 shrink-0", s.cls)} aria-label={s.label} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium">{a.rule}</p>
                      <p className="text-[12.5px] text-muted-foreground tabular">{a.message}</p>
                    </div>
                    {can("scenario.save") && (
                      <Button size="xs" variant="outline" onClick={() => createAction.mutate(a)} disabled={createAction.isPending}>
                        <Plus className="size-3" /> 조치 생성
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Section>
        <Section title="알림 규칙" description={edit ? "워크스페이스별로 저장됩니다" : "변경은 관리자 권한이 필요합니다"} bodyClassName="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <NumberField id="otif" label="OTIF 하한" value={(rules.otif_min ?? 0) * 100} onChange={(v) => set("otif_min", v / 100)} min={0} max={100} step={0.5} suffix="%" disabled={!edit} />
            <NumberField id="late" label="지연율 상한" value={(rules.late_rate_max ?? 0) * 100} onChange={(v) => set("late_rate_max", v / 100)} min={0} max={100} step={0.5} suffix="%" disabled={!edit} />
            <NumberField id="stock" label="결품 허용 건수" value={rules.stockout_max ?? 0} onChange={(v) => set("stockout_max", Math.round(v))} min={0} disabled={!edit} />
            <NumberField id="stale" label="데이터 갱신 허용" value={rules.data_stale_days ?? 7} onChange={(v) => set("data_stale_days", Math.round(v))} min={1} max={365} suffix="일" disabled={!edit} />
          </div>
          <NumberField
            id="budget"
            label="월 운송비 예산 (0 = 미설정)"
            value={rules.monthly_cost_budget ?? 0}
            onChange={(v) => set("monthly_cost_budget", v)}
            min={0}
            step={1_000_000}
            suffix="원"
            hint="선택 기간 일수로 일할 환산해 비교합니다."
            disabled={!edit}
          />
          {edit && (
            <Button size="sm" onClick={() => saveRules.mutate()} disabled={saveRules.isPending}>
              규칙 저장
            </Button>
          )}
        </Section>
      </div>
    </div>
  );
}

const COLUMNS: { status: Action["status"]; title: string }[] = [
  { status: "open", title: "열림" },
  { status: "in_progress", title: "진행 중" },
  { status: "done", title: "완료" },
  { status: "dismissed", title: "보류" },
];

function ActionsTab() {
  const { can } = useWorkspace();
  const q = useApi<Action[]>("/api/actions");
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const create = useApiMutation<void, { id: number }>(() => ({ path: "/api/actions", body: { title, source } }), { success: (r) => `조치 #${r.id} 생성` });
  const update = useApiMutation<{ id: number; status: string; owner?: string | null }, unknown>((b) => ({ path: `/api/actions/${b.id}`, method: "PATCH", body: { status: b.status, owner: b.owner } }), {
    success: "상태를 변경했습니다",
  });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-96" />;
  const manage = can("action.manage");
  return (
    <div className="space-y-4">
      {can("scenario.save") && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim()) create.mutate(undefined, { onSuccess: () => (setTitle(""), setSource("")) });
          }}
          className="flex flex-wrap gap-2 rounded-xl border border-border bg-card p-3 shadow-card"
        >
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="새 조치 후보 (예: 호남 권역 지연 원인 점검)" className="h-8 min-w-64 flex-1" aria-label="조치 제목" />
          <Input value={source} onChange={(e) => setSource(e.target.value)} placeholder="근거 (화면·시나리오 ID 등)" className="h-8 w-64" aria-label="근거" />
          <Button size="sm" type="submit" disabled={!title.trim() || create.isPending}>
            <Plus className="size-3.5" /> 생성
          </Button>
        </form>
      )}
      {!manage && <p className="text-[12px] text-muted-foreground">상태 변경은 운영 관리자 이상 권한이 필요합니다.</p>}
      {q.data.length === 0 ? (
        <EmptyState title="조치 항목이 없습니다" description="알림에서 ‘조치 생성’을 누르거나 위 입력란으로 조치를 만들 수 있습니다." />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((c) => {
            const items = q.data!.filter((a) => a.status === c.status);
            return (
              <section key={c.status} className="flex flex-col rounded-xl border border-border bg-muted/30">
                <header className="flex items-center justify-between px-3 py-2.5">
                  <span className="text-[12.5px] font-semibold">{c.title}</span>
                  <span className="rounded-full bg-card px-1.5 text-[11px] text-muted-foreground tabular ring-1 ring-border">{items.length}</span>
                </header>
                <div className="flex-1 space-y-2 px-2 pb-2">
                  {items.map((a) => (
                    <article key={a.id} className="rounded-lg border border-border bg-card p-3 shadow-card">
                      <p className="text-[13px] font-medium leading-snug">{a.title}</p>
                      <p className="mt-1 text-[11.5px] text-muted-foreground">
                        #{a.id} · {a.source || "근거 없음"} · {dateTimeLabel(a.created_at)}
                      </p>
                      <div className="mt-2.5 flex items-center gap-2">
                        {a.owner && <Pill>{a.owner}</Pill>}
                        {manage ? (
                          <Select value={a.status} onValueChange={(s) => update.mutate({ id: a.id, status: s, owner: a.owner })}>
                            <SelectTrigger size="sm" className="ml-auto h-7 w-28 text-[12px]" aria-label="상태 변경">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {COLUMNS.map((x) => (
                                <SelectItem key={x.status} value={x.status}>
                                  {STATUS_LABEL[x.status].label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <Pill tone={STATUS_LABEL[a.status].tone} className="ml-auto">
                            {STATUS_LABEL[a.status].label}
                          </Pill>
                        )}
                      </div>
                    </article>
                  ))}
                  {items.length === 0 && <p className="px-2 py-4 text-center text-[12px] text-subtle-foreground">없음</p>}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
