"use client";

import { Construction } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { navByKey } from "@/lib/nav";

/** 아직 새 UI 로 옮기지 않은 화면 — 동작하는 척하지 않고 현재 상태를 그대로 안내 */
export function ComingSoon({ navKey, features }: { navKey: string; features: string[] }) {
  const nav = navByKey(navKey);
  return (
    <>
      <PageHeader nav={nav} title={nav.subtitle} />
      <div className="mx-auto max-w-2xl rounded-xl border border-border bg-card p-8 shadow-card">
        <div className="flex items-start gap-4">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-muted">
            <Construction className="size-5 text-muted-foreground" />
          </div>
          <div className="space-y-3">
            <div>
              <h2 className="text-base font-semibold">새 화면 준비 중 ({nav.phase})</h2>
              <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                이 화면은 아직 새 인터페이스로 옮겨지지 않았습니다. 계산 엔진은 이미 동작하며, 기존 화면(Streamlit)에서 사용할 수
                있습니다. 아래 기능이 이 화면으로 옮겨질 예정입니다.
              </p>
            </div>
            <ul className="grid gap-1.5 text-[13px] sm:grid-cols-2">
              {features.map((f) => (
                <li key={f} className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-border-strong" /> {f}
                </li>
              ))}
            </ul>
            <div className="flex gap-2 pt-1">
              <Button asChild variant="outline" size="sm">
                <Link href="/control-tower/">Control Tower 로 이동</Link>
              </Button>
              <Button asChild variant="ghost" size="sm">
                <Link href="/data-hub/">Data Hub</Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
