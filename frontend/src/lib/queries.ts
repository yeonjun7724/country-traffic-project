"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { client, unwrap } from "./api";
import { filterQuery, type Filters } from "./filters";
import { takePreload } from "./preload";
import { useWorkspace } from "./workspace";

/** 워크스페이스가 확정된 뒤에만 조회 + 키에 워크스페이스 포함 (전환 시 캐시 섞임 방지) */
function useWs() {
  const { me } = useWorkspace();
  return me?.workspace.id;
}

type Q = Record<string, string | string[]>;
const q = (f: Filters, extra?: Q) => ({ ...filterQuery(f), ...(extra ?? {}) }) as never;

// ── 쿼리 정의 (훅과 프리페치가 같은 키·요청을 쓰도록 공용) ──
export const queryDefs = {
  filterMeta: (ws: string | undefined) => ({
    queryKey: ["filters", ws],
    queryFn: () => takePreload<never>("filters") ?? unwrap(client.GET("/api/filters")),
    staleTime: 60_000,
  }),
  overview: (ws: string | undefined, f: Filters) => ({
    queryKey: ["ct", "overview", ws, f],
    queryFn: () => takePreload<never>("ct.overview") ?? unwrap(client.GET("/api/control-tower/overview", { params: { query: q(f) } })),
  }),
  network: (ws: string | undefined, f: Filters) => ({
    queryKey: ["ct", "network", ws, f],
    queryFn: () => takePreload<never>("ct.network") ?? unwrap(client.GET("/api/control-tower/network", { params: { query: q(f) } })),
  }),
  cts: (ws: string | undefined, f: Filters, dim: CtsDim) => ({
    queryKey: ["ct", "cts", ws, f, dim],
    queryFn: () =>
      (dim === "region" ? takePreload<never>("ct.cts.region") : null) ??
      unwrap(client.GET("/api/control-tower/cost-to-serve", { params: { query: q(f, { dim }) } })),
  }),
  external: (ws: string | undefined) => ({
    queryKey: ["ct", "external", ws],
    queryFn: () => takePreload<never>("ct.external") ?? unwrap(client.GET("/api/control-tower/external")),
    staleTime: 10 * 60_000,
  }),
};

export function useFilterMeta() {
  const ws = useWs();
  return useQuery({ ...queryDefs.filterMeta(ws), enabled: !!ws });
}

export function useOverview(f: Filters) {
  const ws = useWs();
  return useQuery({
    ...queryDefs.overview(ws, f),
    enabled: !!ws,
    placeholderData: keepPreviousData,
  });
}

export function useDaily(f: Filters) {
  const ws = useWs();
  return useQuery({
    queryKey: ["ct", "daily", ws, f],
    queryFn: () => unwrap(client.GET("/api/control-tower/daily", { params: { query: q(f) } })),
    enabled: !!ws,
    placeholderData: keepPreviousData,
  });
}

export function useNetwork(f: Filters) {
  const ws = useWs();
  return useQuery({
    ...queryDefs.network(ws, f),
    enabled: !!ws,
    placeholderData: keepPreviousData,
  });
}

export type CtsDim = "carrier" | "warehouse_id" | "region" | "customer_group";
export function useCostToServe(f: Filters, dim: CtsDim) {
  const ws = useWs();
  return useQuery({
    ...queryDefs.cts(ws, f, dim),
    enabled: !!ws,
    placeholderData: keepPreviousData,
  });
}

export type LedgerKind = "late" | "cost" | "all";
export function useLedger(f: Filters, kind: LedgerKind, selected: string[], limit = 5000) {
  const ws = useWs();
  return useQuery({
    queryKey: ["ct", "ledger", ws, f, kind, selected, limit],
    queryFn: () =>
      unwrap(
        client.GET("/api/control-tower/ledger", {
          params: { query: q(f, { kind, selected, limit: String(limit) }) },
        }),
      ),
    enabled: !!ws,
    placeholderData: keepPreviousData,
  });
}

export function useExternal() {
  const ws = useWs();
  return useQuery({ ...queryDefs.external(ws), enabled: !!ws });
}

export function useSearch(text: string) {
  const ws = useWs();
  return useQuery({
    queryKey: ["search", ws, text],
    queryFn: () => unwrap(client.GET("/api/search", { params: { query: { q: text } } })),
    enabled: !!ws && text.trim().length > 0,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}

// ── Data Hub ──
export function useEntities() {
  const ws = useWs();
  return useQuery({ queryKey: ["data", "entities", ws], queryFn: () => unwrap(client.GET("/api/data/entities")), enabled: !!ws });
}

export function useDatasets() {
  const ws = useWs();
  return useQuery({ queryKey: ["data", "datasets", ws], queryFn: () => unwrap(client.GET("/api/data/datasets")), enabled: !!ws });
}

export function useQuality() {
  const ws = useWs();
  return useQuery({ queryKey: ["data", "quality", ws], queryFn: () => unwrap(client.GET("/api/data/quality")), enabled: !!ws });
}

export function useIntegrations() {
  const ws = useWs();
  return useQuery({
    queryKey: ["data", "integrations", ws],
    queryFn: () => unwrap(client.GET("/api/data/integrations")),
    enabled: !!ws,
    staleTime: 10 * 60_000,
  });
}

export function useSchema(entity: string | null) {
  return useQuery({
    queryKey: ["data", "schema", entity],
    queryFn: () => unwrap(client.GET("/api/data/schemas/{entity}", { params: { path: { entity: entity! } } })),
    enabled: !!entity,
    staleTime: Infinity,
  });
}
