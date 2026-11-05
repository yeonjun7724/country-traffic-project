"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronRight, FlaskConical, Moon, RefreshCw, Sun } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { Suspense, useEffect, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { client, unwrap } from "@/lib/api";
import { dateTimeLabel } from "@/lib/format";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { WorkspaceProvider, useWorkspace } from "@/lib/workspace";

import { AppSidebar } from "./app-sidebar";
import { BrandMark } from "./brand";
import { CommandPalette } from "./command-palette";
import { WorkspaceSwitcher } from "./workspace-switcher";

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const auth = useQuery({ queryKey: ["auth"], queryFn: () => unwrap(client.GET("/api/auth/status")), staleTime: 60_000 });
  const needLogin = auth.data && auth.data.access_code_required && !auth.data.authenticated;

  useEffect(() => {
    if (needLogin) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      router.replace(`/login/?next=${next}`);
    }
  }, [needLogin, router]);

  if (auth.isError) return <BootError onRetry={() => auth.refetch()} />;
  if (!auth.data || needLogin) return <BootSplash />;

  return (
    <WorkspaceProvider>
      <SidebarProvider>
        <Suspense>
          <AppSidebar />
        </Suspense>
        <SidebarInset className="min-w-0 bg-canvas">
          <Topbar />
          <main id="main" className="mx-auto w-full max-w-[1600px] flex-1 px-4 pb-16 pt-6 md:px-6 lg:px-8">
            <MeGate>{children}</MeGate>
          </main>
        </SidebarInset>
      </SidebarProvider>
    </WorkspaceProvider>
  );
}

function Topbar() {
  return (
    <header className="sticky top-0 z-30 shrink-0 border-b border-border bg-canvas/85 backdrop-blur supports-[backdrop-filter]:bg-canvas/70">
      <div className="flex h-14 items-center gap-2 px-3 md:px-4">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded focus:bg-card focus:px-3 focus:py-1.5">
          본문으로 건너뛰기
        </a>
        <SidebarTrigger className="-ml-1 text-muted-foreground" aria-label="내비게이션 접기/펼치기" />
        <Separator orientation="vertical" className="mr-1 !h-5" />
        <WorkspaceSwitcher />
        <Suspense>
          <Crumb />
        </Suspense>
        <div className="ml-auto flex items-center gap-2">
          <Freshness />
          <div className="w-56 lg:w-72">
            <CommandPalette />
          </div>
          <ThemeButton />
        </div>
      </div>
      <SampleBanner />
    </header>
  );
}

/** 현재 위치: 섹션 › 화면 */
function Crumb() {
  const pathname = usePathname();
  const sec = NAV.find((s) => s.items.some((i) => pathname.startsWith(i.href.replace(/\/$/, ""))));
  const item = sec?.items.find((i) => pathname.startsWith(i.href.replace(/\/$/, "")));
  if (!sec || !item) return null;
  return (
    <nav aria-label="현재 위치" className="hidden items-center gap-1.5 text-[13px] md:flex">
      <ChevronRight className="size-3.5 text-subtle-foreground" />
      <span className="text-subtle-foreground">{sec.section}</span>
      <ChevronRight className="size-3.5 text-subtle-foreground" />
      <span className="font-medium text-foreground">{item.title}</span>
    </nav>
  );
}

function Freshness() {
  const { me } = useWorkspace();
  if (!me) return null;
  return (
    <span className="hidden items-center gap-1.5 text-[12px] text-muted-foreground xl:inline-flex" title="마지막 데이터 업로드 시각">
      <span className={cn("size-1.5 rounded-full", me.data_updated_at ? "bg-success" : "bg-border-strong")} />
      {me.data_updated_at ? `데이터 ${dateTimeLabel(me.data_updated_at)}` : "운영 데이터 없음"}
    </span>
  );
}

function ThemeButton() {
  const { resolvedTheme, setTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  return (
    <Button variant="ghost" size="icon" className="text-muted-foreground" onClick={() => setTheme(dark ? "light" : "dark")} aria-label={dark ? "라이트 모드로" : "다크 모드로"}>
      {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  );
}

/** 샘플 워크스페이스 안내 — 모든 화면 상단에 항상 표시 (실제 성과로 오인 방지) */
function SampleBanner() {
  const { me, switchWorkspace } = useWorkspace();
  if (!me?.is_demo) return null;
  const mine = me.workspaces.find((w) => !w.is_demo);
  return (
    <div className="flex items-center gap-2 border-t border-kind-demo/20 bg-kind-demo/[0.07] px-4 py-1.5 text-[12px] text-foreground/80">
      <FlaskConical className="size-3.5 shrink-0 text-kind-demo" />
      <span className="truncate">
        <b className="font-semibold text-kind-demo">샘플 워크스페이스</b> · 화면의 운영 수치는 시연용 가상 데이터로 계산한 값이며 실제 성과가 아닙니다.
      </span>
      {mine && (
        <button type="button" onClick={() => switchWorkspace(mine.id)} className="ml-auto shrink-0 font-medium text-primary hover:underline">
          내 워크스페이스로 전환
        </button>
      )}
    </div>
  );
}

function MeGate({ children }: { children: ReactNode }) {
  const { me, isLoading, error } = useWorkspace();
  if (error && !isLoading && (error as { status?: number }).status !== 403) {
    return <BootError inline message={error.message} onRetry={() => window.location.reload()} />;
  }
  if (!me) return <PageSkeleton />;
  return <>{children}</>;
}

export function PageSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="불러오는 중">
      <div className="space-y-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-7 w-64" />
      </div>
      <Skeleton className="h-10 w-full" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-[118px] rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-[420px] w-full rounded-xl" />
    </div>
  );
}

function BootSplash() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 bg-canvas">
      <BrandMark className="size-10 animate-pulse" />
      <p className="text-sm text-muted-foreground">불러오는 중…</p>
    </div>
  );
}

function BootError({ onRetry, inline, message }: { onRetry: () => void; inline?: boolean; message?: string }) {
  return (
    <div className={inline ? "py-24" : "flex min-h-svh items-center justify-center bg-canvas"}>
      <div className="mx-auto max-w-md rounded-xl border border-border bg-card p-6 text-center shadow-card">
        <AlertTriangle className="mx-auto size-8 text-warning" />
        <h1 className="mt-3 text-base font-semibold">서버에 연결할 수 없습니다</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          {message ?? "네트워크 연결을 확인하거나 잠시 후 다시 시도하세요. 서버가 재시작 중이면 1분 내 복구됩니다."}
        </p>
        <Button onClick={onRetry} className="mt-4" variant="outline">
          <RefreshCw className="size-4" /> 다시 시도
        </Button>
      </div>
    </div>
  );
}
