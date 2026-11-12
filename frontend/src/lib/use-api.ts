"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { apiFetch } from "./api";
import { filterQuery, type Filters } from "./filters";
import { useWorkspace } from "./workspace";

type Query = Record<string, string | number | string[] | number[] | undefined | null>;

/** 워크스페이스 키를 포함한 GET 조회 (전환 시 캐시 섞임 방지). filters 를 주면 전역 필터 쿼리를 합친다. */
export function useApi<T>(path: string | null, opts: { query?: Query; filters?: Filters; staleTime?: number; enabled?: boolean } = {}) {
  const { me } = useWorkspace();
  const ws = me?.workspace.id;
  const query = { ...(opts.filters ? filterQuery(opts.filters) : {}), ...(opts.query ?? {}) };
  return useQuery({
    queryKey: ["api", ws, path, query],
    queryFn: () => apiFetch<T>(path!, { query }),
    enabled: !!ws && !!path && (opts.enabled ?? true),
    placeholderData: keepPreviousData,
    staleTime: opts.staleTime ?? 30_000,
  });
}

/** 쓰기 요청 + 성공 시 관련 조회 무효화 + 토스트 */
export function useApiMutation<TBody, TRes>(
  fn: (body: TBody) => { path: string; method?: string; body?: unknown; query?: Query },
  opts: {
    success?: string | ((r: TRes) => string);
    invalidate?: boolean;
    /** 성공 토스트의 이동 버튼 (예: 저장한 시나리오의 승인 화면 열기) */
    action?: (r: TRes) => { label: string; href: string } | null;
  } = {},
) {
  const qc = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: (b: TBody) => {
      const r = fn(b);
      return apiFetch<TRes>(r.path, { method: r.method ?? "POST", body: r.body, query: r.query });
    },
    onSuccess: (r) => {
      if (opts.invalidate !== false) qc.invalidateQueries();
      const act = opts.action?.(r);
      if (opts.success)
        toast.success(typeof opts.success === "function" ? opts.success(r) : opts.success, act ? { action: { label: act.label, onClick: () => router.push(act.href) } } : undefined);
    },
    onError: (e) => toast.error((e as Error).message),
  });
}
