"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { Suspense, useEffect, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { client, unwrap } from "@/lib/api";
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
          <main id="main" className="mx-auto w-full max-w-[1600px] flex-1 px-4 pb-16 pt-5 md:px-6 lg:px-8">
            <MeGate>{children}</MeGate>
          </main>
        </SidebarInset>
      </SidebarProvider>
    </WorkspaceProvider>
  );
}

function Topbar() {
  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-canvas/85 px-3 backdrop-blur supports-[backdrop-filter]:bg-canvas/70 md:px-4">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded focus:bg-card focus:px-3 focus:py-1.5">
        본문으로 건너뛰기
      </a>
      <SidebarTrigger className="-ml-1 text-muted-foreground" aria-label="내비게이션 접기/펼치기" />
      <Separator orientation="vertical" className="mr-1 !h-5" />
      <WorkspaceSwitcher />
      <div className="ml-auto flex w-full max-w-72 items-center justify-end gap-2">
        <CommandPalette />
      </div>
    </header>
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
