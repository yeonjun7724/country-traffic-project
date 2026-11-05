"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { clearWorkspace, client, getWorkspace, setWorkspace, unwrap, type Me } from "./api";

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
    queryFn: () => unwrap(client.GET("/api/me")),
    retry: (n, e) => (e as { status?: number }).status !== 401 && (e as { status?: number }).status !== 403 && n < 2,
  });

  const switchWorkspace = useCallback(
    (id: string) => {
      setWorkspace(id);
      setWs(id);
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "auth" });
    },
    [qc],
  );

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

export function useWorkspace() {
  const c = useContext(WorkspaceContext);
  if (!c) throw new Error("WorkspaceProvider 가 필요합니다.");
  return c;
}
