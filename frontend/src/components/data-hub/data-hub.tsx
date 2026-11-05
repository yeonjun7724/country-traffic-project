"use client";

import { Lock } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { PageHeader } from "@/components/common/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { navByKey } from "@/lib/nav";
import { useEntities } from "@/lib/queries";
import { useWorkspace } from "@/lib/workspace";

import { DatasetsTab } from "./datasets-tab";
import { EntityRail } from "./entity-rail";
import { IntegrationsTab, QualityTab, SchemaTab } from "./other-tabs";
import { UploadWizard } from "./upload-wizard";

const NAV = navByKey("data-hub");
const TABS = [
  { v: "upload", label: "업로드" },
  { v: "datasets", label: "데이터셋 · 버전" },
  { v: "quality", label: "데이터 품질" },
  { v: "schema", label: "스키마 · 양식" },
  { v: "integrations", label: "외부 연동" },
];

export function DataHub() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab = TABS.some((t) => t.v === sp.get("tab")) ? sp.get("tab")! : "upload";
  const setTab = (v: string) => {
    const q = new URLSearchParams(sp.toString());
    if (v === "upload") q.delete("tab");
    else q.set("tab", v);
    router.replace(`${pathname}${q.toString() ? `?${q}` : ""}`, { scroll: false });
  };

  return (
    <>
      <PageHeader nav={NAV} title="데이터 허브" description="업로드 → 컬럼 매핑 → 검증 → 원자적 저장 · 버전 관리와 롤백" />
      <Tabs value={tab} onValueChange={setTab} className="gap-4">
        <TabsList variant="line" className="h-9 w-full justify-start gap-4 rounded-none border-b border-border p-0">
          {TABS.map((t) => (
            <TabsTrigger
              key={t.v}
              value={t.v}
              className="h-9 flex-none rounded-none border-0 border-b-2 border-transparent px-0.5 text-[13px] data-[state=active]:border-primary data-[state=active]:text-foreground data-[state=active]:shadow-none"
            >
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="upload">
          <UploadTab />
        </TabsContent>
        <TabsContent value="datasets">
          <DatasetsTab />
        </TabsContent>
        <TabsContent value="quality">
          <QualityTab />
        </TabsContent>
        <TabsContent value="schema">
          <SchemaTab />
        </TabsContent>
        <TabsContent value="integrations">
          <IntegrationsTab />
        </TabsContent>
      </Tabs>
    </>
  );
}

function UploadTab() {
  const { can, me } = useWorkspace();
  const ents = useEntities();
  const [entity, setEntity] = useState("warehouses");
  const label = ents.data?.find((e) => e.entity === entity)?.label ?? entity;

  if (!can("data.upload"))
    return (
      <div className="flex items-start gap-3 rounded-xl border border-border bg-card p-5 shadow-card">
        <Lock className="mt-0.5 size-4 text-muted-foreground" />
        <div>
          <p className="text-[13.5px] font-medium">업로드 권한이 없습니다</p>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">데이터 업로드는 분석가 이상 권한이 필요합니다. 현재 역할: {me?.role_label}</p>
        </div>
      </div>
    );

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="h-fit rounded-xl border border-border bg-card shadow-card lg:sticky lg:top-[72px]">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-[13.5px] font-semibold">데이터 유형</h2>
          <p className="mt-0.5 text-[12px] text-muted-foreground">참조 관계 때문에 위에서부터 순서대로 올리세요.</p>
        </div>
        <EntityRail items={ents.data} value={entity} onChange={setEntity} />
      </aside>
      <section className="min-w-0 rounded-xl border border-border bg-card p-5 shadow-card">
        <div className="mb-4">
          <h2 className="text-[15px] font-semibold">{label} 업로드</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">
            {me?.is_demo ? "샘플 워크스페이스 — 올린 데이터도 샘플로 표시되며 내 워크스페이스와 분리됩니다." : "저장하면 새 버전으로 활성화되고, 이전 버전은 보존됩니다."}
          </p>
        </div>
        <UploadWizard key={`${me?.workspace.id}-${entity}`} entity={entity} label={label} isDemo={!!me?.is_demo} />
      </section>
    </div>
  );
}
