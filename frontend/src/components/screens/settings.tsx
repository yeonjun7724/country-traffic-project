"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Lock, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { Pill } from "@/components/common/badges";
import { DataTable } from "@/components/common/data-table";
import { Callout, LineTabs, NumberField, useUrlTab } from "@/components/common/kit";
import { PageHeader } from "@/components/common/page-header";
import { Section } from "@/components/common/section";
import { ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { dateTimeLabel } from "@/lib/format";
import { navByKey } from "@/lib/nav";
import type { AuditRow, SettingsView, Targets } from "@/lib/types";
import { useApi, useApiMutation } from "@/lib/use-api";
import { useWorkspace } from "@/lib/workspace";

const NAV = navByKey("settings");
const ROLE_ORDER = ["viewer", "analyst", "manager", "admin"];
const ROLE_LABEL: Record<string, string> = { viewer: "조회자", analyst: "분석가", manager: "운영 관리자", admin: "관리자" };
const PERM_LABEL: Record<string, string> = {
  "data.read": "데이터 조회",
  "data.export": "내보내기 (CSV·Excel·리포트)",
  "data.upload": "데이터 업로드",
  "scenario.save": "시나리오 저장·조치 제안",
  "ai.use": "AI Copilot 사용",
  "action.manage": "조치 상태 관리",
  "plan.approve": "계획·시나리오 승인",
  "dataset.activate": "데이터 버전 활성화·롤백",
  "settings.manage": "목표·알림 규칙 변경",
  "audit.read": "감사 로그 조회",
};

export function SettingsScreen() {
  const [tab, setTab] = useUrlTab(["targets", "roles", "system", "audit"]);
  const q = useApi<SettingsView>("/api/settings");
  return (
    <>
      <PageHeader nav={NAV} title="설정 · 권한 · 감사" description="워크스페이스별 KPI 목표, 역할 권한, 시스템 상태, 감사 로그" />
      <LineTabs
        value={tab}
        onChange={setTab}
        items={[
          { v: "targets", label: "KPI 목표" },
          { v: "roles", label: "역할 · 권한" },
          { v: "system", label: "시스템" },
          { v: "audit", label: "감사 로그" },
        ]}
      />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {!q.data ? (
        <Skeleton className="h-80" />
      ) : (
        <>
          {tab === "targets" && <TargetsTab data={q.data} />}
          {tab === "roles" && <RolesTab data={q.data} />}
          {tab === "system" && <SystemTab data={q.data} />}
          {tab === "audit" && <AuditTab />}
        </>
      )}
    </>
  );
}

function TargetsTab({ data }: { data: SettingsView }) {
  const { can } = useWorkspace();
  const edit = can("settings.manage");
  const [t, setT] = useState<Targets>(data.targets);
  useEffect(() => setT(data.targets), [data.targets]);
  const save = useApiMutation<void, Targets>(() => ({ path: "/api/settings/targets", method: "PUT", body: t }), { success: "목표를 저장했습니다. KPI 카드·알림에 바로 반영됩니다." });
  const set = (k: keyof Targets, v: number | null) => setT({ ...t, [k]: v });
  return (
    <Section className="max-w-4xl" title="KPI 목표" description={edit ? "목표는 KPI 카드의 달성 여부와 비용 초과 판정에 쓰입니다." : "목표 변경은 관리자 권한이 필요합니다."} bodyClassName="space-y-5">
      <div className="grid gap-4 sm:grid-cols-3">
        <NumberField id="t-otif" label="OTIF 목표 (이상)" value={(t.otif ?? 0) * 100} onChange={(v) => set("otif", v / 100)} min={0} max={100} step={0.5} suffix="%" disabled={!edit} />
        <NumberField id="t-late" label="지연율 목표 (이하)" value={(t.late_rate ?? 0) * 100} onChange={(v) => set("late_rate", v / 100)} min={0} max={100} step={0.5} suffix="%" disabled={!edit} />
        <NumberField id="t-lf" label="적재율 목표 (이상)" value={(t.load_factor ?? 0) * 100} onChange={(v) => set("load_factor", v / 100)} min={0} max={100} step={1} suffix="%" disabled={!edit} />
        <NumberField id="t-cpo" label="주문당 운송비 목표 (0 = 미설정)" value={t.cost_per_order ?? 0} onChange={(v) => set("cost_per_order", v || null)} min={0} step={1000} suffix="원" disabled={!edit} />
        <NumberField
          id="t-max"
          label="배송당 비용 상한 (0 = 미설정)"
          value={t.max_cost_per_shipment ?? 0}
          onChange={(v) => set("max_cost_per_shipment", v || null)}
          min={0}
          step={1000}
          suffix="원"
          hint="미설정 시 비용 초과는 통계적 상위 5%(P95)로 판정"
          disabled={!edit}
        />
      </div>
      {edit && (
        <div className="flex gap-2">
          <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
            목표 저장
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setT(data.default_targets)}>
            기본값으로
          </Button>
        </div>
      )}
    </Section>
  );
}

function RolesTab({ data }: { data: SettingsView }) {
  const { me } = useWorkspace();
  return (
    <div className="space-y-4">
      <Callout tone="warn" title="로그인 없는 공개 모드">
        현재 계정 체계 없이 모든 방문자가 같은 로컬 사용자({me?.role_label})로 동작합니다. 역할 기반 권한은 서버와 AI 도구 계층에서 강제되며, 실제 다중 사용자 운영에는 SSO/OIDC 연동이 필요합니다 (미구현).
      </Callout>
      <Section title="역할별 권한" description="권한마다 필요한 최소 역할 — 상위 역할은 하위 권한을 모두 포함" bodyClassName="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead className="text-[11.5px] text-muted-foreground">
              <tr className="border-b border-border">
                <th className="px-4 py-2 text-left font-medium">권한</th>
                {ROLE_ORDER.map((r) => (
                  <th key={r} className="px-4 py-2 text-center font-medium">
                    {ROLE_LABEL[r]}
                    {me?.role === r && <span className="ml-1 text-primary">(현재)</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.permissions.map((p) => (
                <tr key={p.permission} className="border-b border-border last:border-0">
                  <td className="px-4 py-2">
                    <div className="font-medium">{PERM_LABEL[p.permission] ?? p.permission}</div>
                    <div className="font-mono text-[11px] text-subtle-foreground">{p.permission}</div>
                  </td>
                  {ROLE_ORDER.map((r) => {
                    const ok = ROLE_ORDER.indexOf(r) >= ROLE_ORDER.indexOf(p.min_role);
                    return (
                      <td key={r} className="px-4 py-2 text-center">
                        {ok ? <ShieldCheck className="mx-auto size-4 text-success" aria-label="허용" /> : <Lock className="mx-auto size-3.5 text-subtle-foreground/60" aria-label="불가" />}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

function SystemTab({ data }: { data: SettingsView }) {
  return (
    <Section title="시스템 상태" bodyClassName="p-0">
      <dl className="divide-y divide-border">
        {data.system.map((s) => (
          <div key={s.item} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-[13px]">
            <dt className="text-muted-foreground">{s.item}</dt>
            <dd className="font-medium">
              {s.value.includes("미구현") ? <Pill>{s.value}</Pill> : s.value.includes("미설정") ? <Pill tone="warning">{s.value}</Pill> : s.value}
            </dd>
          </div>
        ))}
      </dl>
      <p className="border-t border-border px-4 py-3 text-[11.5px] text-subtle-foreground">API 키는 서버 환경변수로만 설정하며 화면·로그에 노출하지 않습니다.</p>
    </Section>
  );
}

const ACOLS: ColumnDef<AuditRow, unknown>[] = [
  { accessorKey: "at", header: "시각", cell: (c) => <span className="tabular">{dateTimeLabel(c.getValue() as string)}</span> },
  { accessorKey: "user_id", header: "사용자" },
  { accessorKey: "action", header: "작업", cell: (c) => <span className="font-mono text-[12px]">{String(c.getValue())}</span> },
  { accessorKey: "target", header: "대상", cell: (c) => <span className="block max-w-72 truncate">{String(c.getValue() ?? "")}</span> },
  { accessorKey: "detail_json", header: "상세", cell: (c) => <span className="block max-w-96 truncate font-mono text-[11px] text-muted-foreground" title={String(c.getValue() ?? "")}>{String(c.getValue() ?? "")}</span> },
];

function AuditTab() {
  const { can } = useWorkspace();
  const q = useApi<AuditRow[]>(can("audit.read") ? "/api/audit" : null);
  if (!can("audit.read")) return <Callout tone="warn">감사 로그 조회는 운영 관리자 이상 권한이 필요합니다.</Callout>;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-80" />;
  return (
    <Section title="감사 로그" description="업로드·저장·승인·내보내기·설정 변경 기록 (최근 300건)" bodyClassName="p-3">
      <DataTable data={q.data} columns={ACOLS} rowKey={(r) => String(r.id)} height={520} ariaLabel="감사 로그" />
    </Section>
  );
}
