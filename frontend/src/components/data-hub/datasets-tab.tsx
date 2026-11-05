"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { History, Loader2, PowerOff, RotateCcw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Pill } from "@/components/common/badges";
import { EmptyState, ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { client, unwrap, type Schemas } from "@/lib/api";
import { dateTimeLabel, num } from "@/lib/format";
import { useDatasets } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

type D = Schemas["DatasetOut"];
type Pending = { kind: "activate"; ds: D } | { kind: "deactivate"; entity: string; label: string } | null;

export function DatasetsTab() {
  const q = useDatasets();
  const { can } = useWorkspace();
  const admin = can("dataset.activate");
  const qc = useQueryClient();
  const [pending, setPending] = useState<Pending>(null);

  const m = useMutation({
    mutationFn: async (p: NonNullable<Pending>) =>
      p.kind === "activate"
        ? unwrap(client.POST("/api/data/datasets/{dataset_id}/activate", { params: { path: { dataset_id: p.ds.id } } }))
        : unwrap(client.POST("/api/data/entities/{entity}/deactivate", { params: { path: { entity: p.entity } } })),
    onSuccess: (_, p) => {
      qc.invalidateQueries();
      setPending(null);
      toast.success(p.kind === "activate" ? `${p.ds.label} v${p.ds.version} 활성화` : `${p.label} 비활성화`, {
        description: "모든 화면이 새 기준으로 다시 계산됩니다.",
      });
    },
    onError: (e) => toast.error((e as Error).message),
  });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (q.isLoading) return <Skeleton className="h-96" />;
  const rows = q.data ?? [];
  if (rows.length === 0)
    return <EmptyState icon={History} title="저장된 데이터셋이 없습니다" description="업로드 탭에서 데이터를 저장하면 버전 이력이 여기에 쌓입니다." />;

  const groups = rows.reduce<Record<string, D[]>>((acc, r) => ((acc[r.entity] ??= []).push(r), acc), {});

  return (
    <div className="space-y-3">
      {!admin && (
        <p className="rounded-lg bg-muted px-3 py-2 text-[12.5px] text-muted-foreground">버전 활성화(롤백)·비활성화는 관리자 권한이 필요합니다.</p>
      )}
      {Object.entries(groups).map(([entity, list]) => {
        const active = list.find((d) => d.is_active);
        return (
          <section key={entity} className="overflow-hidden rounded-xl border border-border bg-card shadow-card">
            <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
              <div className="flex items-center gap-2">
                <h3 className="text-[13.5px] font-semibold">{list[0].label}</h3>
                <span className="font-mono text-[11.5px] text-subtle-foreground">{entity}</span>
                {active ? <Pill tone="success" dot>v{active.version} 사용 중</Pill> : <Pill>비활성</Pill>}
              </div>
              {admin && active && (
                <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => setPending({ kind: "deactivate", entity, label: list[0].label })}>
                  <PowerOff className="size-3.5" /> 비활성화
                </Button>
              )}
            </header>
            <div className="overflow-x-auto">
              <table className="w-full text-[12.5px]">
                <thead className="text-[11.5px] text-muted-foreground">
                  <tr className="border-b border-border">
                    {["버전", "파일", "출처", "행", "제외", "기간", "업로드", ""].map((h, i) => (
                      <th key={i} className={cn("px-4 py-2 font-medium", i >= 3 && i <= 4 ? "text-right" : "text-left")}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {list.map((d) => (
                    <tr key={d.id} className={cn("border-b border-border last:border-0", d.is_active && "bg-success/[0.04]")}>
                      <td className="px-4 py-2 font-medium tabular">
                        v{d.version}
                        {d.is_demo && <span className="ml-1.5 rounded-sm bg-kind-demo/10 px-1 text-[10px] font-semibold text-kind-demo">샘플</span>}
                      </td>
                      <td className="max-w-56 truncate px-4 py-2">{d.filename ?? "—"}</td>
                      <td className="px-4 py-2 text-muted-foreground">{d.source === "demo_fixture" ? "샘플" : d.source === "upload" ? "업로드" : d.source}</td>
                      <td className="px-4 py-2 text-right tabular">{num(d.row_count)}</td>
                      <td className={cn("px-4 py-2 text-right tabular", (d.rejected_rows ?? 0) > 0 && "text-warning")}>{num(d.rejected_rows)}</td>
                      <td className="px-4 py-2 text-muted-foreground tabular">{d.period_start ? `${d.period_start} ~ ${d.period_end}` : "—"}</td>
                      <td className="px-4 py-2 text-muted-foreground tabular">
                        {dateTimeLabel(d.uploaded_at)} · {d.uploaded_by}
                      </td>
                      <td className="px-4 py-2 text-right">
                        {!d.is_active && admin && (
                          <Button variant="outline" size="xs" onClick={() => setPending({ kind: "activate", ds: d })}>
                            <RotateCcw className="size-3" /> 이 버전으로
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}

      <Dialog open={!!pending} onOpenChange={(o) => !o && setPending(null)}>
        <DialogContent className="sm:max-w-md">
          {pending && (
            <>
              <DialogHeader>
                <DialogTitle>
                  {pending.kind === "activate" ? `${pending.ds.label} v${pending.ds.version} 으로 되돌릴까요?` : `${pending.label} 데이터를 비활성화할까요?`}
                </DialogTitle>
                <DialogDescription className="leading-relaxed">
                  {pending.kind === "activate"
                    ? "현재 사용 중인 버전은 삭제되지 않고 비활성으로 보존됩니다. 모든 KPI·분석이 선택한 버전 기준으로 다시 계산됩니다."
                    : "데이터는 삭제되지 않습니다. 이 유형을 사용하는 KPI·분석은 다시 활성화할 때까지 계산 불가로 표시됩니다."}
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onClick={() => setPending(null)}>
                  취소
                </Button>
                <Button variant={pending.kind === "deactivate" ? "destructive" : "default"} onClick={() => m.mutate(pending)} disabled={m.isPending}>
                  {m.isPending && <Loader2 className="size-4 animate-spin" />}
                  {pending.kind === "activate" ? "이 버전 활성화" : "비활성화"}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
