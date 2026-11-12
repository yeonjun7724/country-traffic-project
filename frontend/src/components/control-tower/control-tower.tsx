"use client";

import { Database, FlaskConical } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Deferred } from "@/components/common/deferred";
import { FilterBar } from "@/components/common/filter-bar";
import { PageHeader } from "@/components/common/page-header";
import { Section } from "@/components/common/section";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useFilters, type Filters } from "@/lib/filters";
import { navByKey } from "@/lib/nav";
import { useDaily, useOverview, type CtsDim } from "@/lib/queries";
import { useWorkspace } from "@/lib/workspace";

import { AlertsPanel } from "./alerts-panel";
import { CostToServe } from "./cost-to-serve";
import { DailyChart, DailyLegend } from "./daily-chart";
import { ExternalPanel } from "./external-panel";
import { Insights } from "./insights";
import { KpiGroups } from "./kpi-groups";
import { Ledger } from "./ledger";
import { NetworkSection } from "./network-section";
import { Onboarding } from "./onboarding";

const NAV = navByKey("control-tower");

export function ControlTower() {
  const { me } = useWorkspace();
  const { filters } = useFilters();
  const [selected, setSelected] = useState<string[]>([]);
  const [dim, setDim] = useState<CtsDim>("carrier");
  const overview = useOverview(filters);

  // 워크스페이스가 바뀌면 지도·표 선택 초기화
  const ws = me?.workspace.id;
  useEffect(() => setSelected([]), [ws]);

  if (me && !me.has_ops_data) return <NoData isDemo={me.is_demo} />;

  return (
    <>
      <PageHeader nav={NAV} title="통합 운영 현황" description={overview.data?.period ?? "기간·센터·권역·운송사 기준 KPI와 예외를 한 화면에서"} />
      <FilterBar className="mb-4" />
      <Onboarding compact />
      <Insights kpis={overview.data?.kpis} filters={filters} />

      {overview.isError ? (
        <ErrorState error={overview.error} onRetry={() => overview.refetch()} className="mb-4" />
      ) : (
        <KpiGroups kpis={overview.data?.kpis} loading={overview.isLoading} />
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7 xl:col-span-8">
          <AlertsPanel alerts={overview.data?.alerts ?? []} loading={overview.isLoading} />
        </div>
        <div className="lg:col-span-5 xl:col-span-4">
          <ExternalPanel />
        </div>
      </div>

      <div className="mt-4">
        <NetworkSection filters={filters} selected={selected} onSelected={setSelected} />
      </div>

      {/* 첫 화면 아래 영역은 가까워질 때 렌더 (차트·원장 API 4건과 렌더 비용을 첫 화면에서 제외). 높이는 실제 렌더 높이 */}
      <Deferred minHeight={359} className="mt-4" label="일별 추이·Cost-to-Serve">
        <div className="mt-4 grid gap-4 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <DailySection filters={filters} />
          </div>
          <div className="lg:col-span-5">
            <CostToServe filters={filters} dim={dim} onDim={setDim} />
          </div>
        </div>
      </Deferred>

      <div className="mt-4">
        <Deferred id="ledger" minHeight={563} label="예외·배송 원장">
          <Ledger filters={filters} selected={selected} onClearSelection={() => setSelected([])} />
        </Deferred>
      </div>
    </>
  );
}

/** 일별 추이 — Deferred 안에서만 마운트되므로 화면에 가까워질 때 API 를 부른다 */
function DailySection({ filters }: { filters: Filters }) {
  const daily = useDaily(filters);
  return (
    <Section title="일별 운송비 · 지연율" description="막대: 운송비(좌) · 선: 지연율(우, 판정 가능한 배송 기준)" actions={<DailyLegend />} className="h-full">
      {daily.isError ? (
        <ErrorState error={daily.error} onRetry={() => daily.refetch()} />
      ) : daily.isLoading ? (
        <Skeleton className="h-[260px]" />
      ) : (daily.data ?? []).length === 0 ? (
        <p className="py-20 text-center text-body text-muted-foreground">해당 기간에 출고된 배송이 없습니다.</p>
      ) : (
        <DailyChart data={daily.data!} />
      )}
    </Section>
  );
}

function NoData({ isDemo }: { isDemo: boolean }) {
  const { me, switchWorkspace } = useWorkspace();
  const demo = me?.workspaces.find((w) => w.is_demo);
  return (
    <>
      <PageHeader nav={NAV} title="통합 운영 현황" description="운영 데이터 업로드 대기" />
      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <EmptyState
            icon={Database}
            title="운영 데이터가 아직 없습니다"
            description={
              <>
                주문·배송·차량·거점 데이터를 업로드하면 OTIF, 운송비, 적재율 등 KPI 가 실제 데이터로 계산됩니다.
                <br />
                데이터가 없는 동안에는 가상의 성과 수치를 보여주지 않습니다.
              </>
            }
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button asChild>
                  <Link href="/data-hub/">
                    <Database className="size-4" /> 데이터 업로드
                  </Link>
                </Button>
                {!isDemo && demo && (
                  <Button variant="outline" onClick={() => switchWorkspace(demo.id)}>
                    <FlaskConical className="size-4" /> 샘플 워크스페이스 둘러보기
                  </Button>
                )}
              </div>
            }
          />
          <div className="mt-4">
            <Onboarding />
          </div>
        </div>
        <div className="lg:col-span-4">
          <ExternalPanel />
        </div>
      </div>
    </>
  );
}
