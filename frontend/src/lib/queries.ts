"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { client, unwrap } from "./api";
import { filterQuery, type Filters } from "./filters";
import { useWorkspace } from "./workspace";

/** 워크스페이스가 확정된 뒤에만 조회 + 키에 워크스페이스 포함 (전환 시 캐시 섞임 방지) */
function useWs() {
  const { me } = useWorkspace();
  return me?.workspace.id;
}

type Q = Record<string, string | string[]>;
const q = (f: Filters, extra?: Q) => ({ ...filterQuery(f), ...(extra ?? {}) }) as never;

export function useFilterMeta() {
  const ws = useWs();
  return useQuery({
    queryKey: ["filters", ws],
    queryFn: () => unwrap(client.GET("/api/filters")),
    enabled: !!ws,
    staleTime: 60_000,
  });
}

export function useOverview(f: Filters) {
  const ws = useWs();
  return useQuery({
    queryKey: ["ct", "overview", ws, f],
    queryFn: () => unwrap(client.GET("/api/control-tower/overview", { params: { query: q(f) } })),
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
    queryKey: ["ct", "network", ws, f],
    queryFn: () => unwrap(client.GET("/api/control-tower/network", { params: { query: q(f) } })),
    enabled: !!ws,
    placeholderData: keepPreviousData,
  });
}

export type CtsDim = "carrier" | "warehouse_id" | "region" | "customer_group";
export function useCostToServe(f: Filters, dim: CtsDim) {
  const ws = useWs();
  return useQuery({
    queryKey: ["ct", "cts", ws, f, dim],
    queryFn: () => unwrap(client.GET("/api/control-tower/cost-to-serve", { params: { query: q(f, { dim }) } })),
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
  return useQuery({
    queryKey: ["ct", "external", ws],
    queryFn: () => unwrap(client.GET("/api/control-tower/external")),
    enabled: !!ws,
    staleTime: 10 * 60_000,
  });
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
