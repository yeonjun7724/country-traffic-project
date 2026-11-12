"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { clearWorkspace, client, getWorkspace, setWorkspace, unwrap, type Me } from "./api";
import { prefetchFirstScreen } from "./prefetch";

type Ctx = {
  me: Me | undefined;
  isLoading: boolean;
  error: Error | null;
  workspaceId: string | null;
  switchWorkspace: (id: string) => void;
  can: (permission: string) => boolean;
};

const WorkspaceContext = createContext<Ctx | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [ws, setWs] = useState<string | null>(() => (typeof window === "undefined" ? null : getWorkspace()));

  const me = useQuery({
    queryKey: ["me", ws],
    queryFn: async () => {
      const m = await unwrap(client.GET("/api/me"));
      prefetchFirstScreen(qc, m); // 렌더 전에 첫 화면 데이터 요청 시작 (lib/prefetch)
      return m;
    },
    retry: (n, e) => (e as { status?: number }).status !== 401 && (e as { status?: number }).status !== 403 && n < 2,
  });

  const switchWorkspace = useCallback(
    (id: string) => {
      setWorkspace(id);
      setWs(id);
      const known = me.data?.workspaces.find((w) => w.id === id);
      if (known) setDemoAttr(known.is_demo); // 전환 직후 배너 자리를 바로 맞춤
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "auth" });
    },
    [qc, me.data],
  );

  // 샘플 여부 기록 → 다음 방문의 첫 페인트에서 배너 자리를 미리 잡는다 (app/layout.tsx 의 인라인 스크립트)
  const meData = me.data;
  useEffect(() => {
    if (!meData) return;
    rememberDemo(meData.workspaces.map((w) => [w.id, w.is_demo] as const), ws ?? "_default", meData.is_demo);
  }, [meData, ws]);

  // 저장된 워크스페이스에 접근 권한이 없어진 경우 서버 기본값으로 복귀
  const forbidden = (me.error as { status?: number } | null)?.status === 403;
  useEffect(() => {
    if (forbidden && ws) {
      clearWorkspace();
      setWs(null);
    }
  }, [forbidden, ws]);

  const value = useMemo<Ctx>(
    () => ({
      me: me.data,
      isLoading: me.isLoading,
      error: me.error as Error | null,
      workspaceId: me.data?.workspace.id ?? ws,
      switchWorkspace,
      can: (p) => !!me.data?.permissions.includes(p),
    }),
    [me.data, me.isLoading, me.error, ws, switchWorkspace],
  );
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

const DEMO_KEY = "lr.demoByWs";

function setDemoAttr(isDemo: boolean) {
  if (typeof document !== "undefined") document.documentElement.dataset.demo = isDemo ? "1" : "0";
}

function rememberDemo(pairs: readonly (readonly [string, boolean])[], current: string, currentIsDemo: boolean) {
  setDemoAttr(currentIsDemo);
  try {
    const m = JSON.parse(window.localStorage.getItem(DEMO_KEY) || "{}") as Record<string, boolean>;
    for (const [id, d] of pairs) m[id] = d;
    m[current] = currentIsDemo;
    window.localStorage.setItem(DEMO_KEY, JSON.stringify(m));
  } catch {
    /* 저장 불가 환경 — 첫 페인트 예측만 못 할 뿐 표시는 /api/me 기준 */
  }
}

export function useWorkspace() {
  const c = useContext(WorkspaceContext);
  if (!c) throw new Error("WorkspaceProvider 가 필요합니다.");
  return c;
}
