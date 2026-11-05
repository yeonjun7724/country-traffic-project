"use client";

import { Globe2 } from "lucide-react";

import { Pill } from "@/components/common/badges";
import { Skeleton } from "@/components/ui/skeleton";
import { dateLabel, deltaText, isNum, num } from "@/lib/format";
import { useExternal } from "@/lib/queries";

/** 외부 위험 지표 — 기업 실적과 시각적으로 분리 (violet 계열, '기업 실적 아님' 명시) */
export function ExternalPanel() {
  const q = useExternal();
  const d = q.data;
  return (
    <section className="flex h-full flex-col rounded-xl border border-external/20 bg-gradient-to-b from-external/[0.05] to-card shadow-card">
      <header className="flex items-start justify-between gap-2 border-b border-external/15 px-4 py-3">
        <div className="space-y-0.5">
          <h2 className="flex items-center gap-1.5 text-[14px] font-semibold tracking-tight">
            <Globe2 className="size-4 text-external" /> 외부 위험 지표
          </h2>
          <p className="text-[12.5px] text-muted-foreground">고속도로 영업소·전국 유가 (공공 데이터 분석)</p>
        </div>
        <Pill tone="external">기업 실적 아님</Pill>
      </header>
      <div className="flex-1 p-4">
        {q.isLoading ? (
          <Skeleton className="h-24" />
        ) : !d?.available ? (
          <p className="text-[13px] text-muted-foreground">외부 위험 데이터 파일이 없습니다.</p>
        ) : (
          <dl className="grid grid-cols-3 gap-3">
            <Stat k="분석 영업소" v={`${num(d.units)}개`} sub="좌표 보유" />
            <Stat k="High-High 군집" v={`${num(d.lisa_hh)}개`} sub="LISA p<0.05" />
            <Stat
              k="전국평균 경유"
              v={d.diesel ? `${num(d.diesel.price)}원` : "—"}
              sub={
                d.diesel
                  ? `${dateLabel(d.diesel.date)} · 30일 ${isNum(d.diesel.change_30d_pct) ? deltaText(d.diesel.change_30d_pct) : "—"}`
                  : ""
              }
            />
          </dl>
        )}
        {d && d.audit_warnings > 0 && (
          <p className="mt-3 rounded-md bg-warning/[0.08] px-2.5 py-1.5 text-[12px] text-foreground/80">
            외부 데이터 감사 경고 {d.audit_warnings}건 — 저장된 유가 예측은 과거 기간이라 미래 전망으로 쓰지 않습니다.
          </p>
        )}
      </div>
    </section>
  );
}

function Stat({ k, v, sub }: { k: string; v: string; sub?: string }) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-[11.5px] text-muted-foreground">{k}</dt>
      <dd className="mt-0.5 text-[18px] font-semibold tracking-tight tabular">{v}</dd>
      {sub && <dd className="truncate text-[11px] text-subtle-foreground">{sub}</dd>}
    </div>
  );
}
