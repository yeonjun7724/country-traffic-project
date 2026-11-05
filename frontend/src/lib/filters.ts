"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

/** 전역 필터 — URL 쿼리에 저장 (공유·새로고침·뒤로가기 유지). 기간 미지정 시 서버 기본값(최근 30일). */
export type Filters = {
  start?: string;
  end?: string;
  warehouses: string[];
  regions: string[];
  carriers: string[];
  vehicles: string[];
  categories: string[];
  stores: string[];
};

export const MULTI_KEYS = ["warehouses", "regions", "carriers", "vehicles", "categories", "stores"] as const;
export type MultiKey = (typeof MULTI_KEYS)[number];

export const FILTER_LABEL: Record<MultiKey, string> = {
  warehouses: "센터",
  regions: "권역",
  carriers: "운송사",
  vehicles: "차량",
  categories: "상품군",
  stores: "배송지",
};

export function useFilters() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const filters: Filters = useMemo(
    () => ({
      start: sp.get("start") ?? undefined,
      end: sp.get("end") ?? undefined,
      warehouses: sp.getAll("warehouses"),
      regions: sp.getAll("regions"),
      carriers: sp.getAll("carriers"),
      vehicles: sp.getAll("vehicles"),
      categories: sp.getAll("categories"),
      stores: sp.getAll("stores"),
    }),
    [sp],
  );

  const update = useCallback(
    (patch: Partial<Filters>) => {
      const next = { ...filters, ...patch };
      const q = new URLSearchParams();
      // 화면 고유 파라미터(탭 등)는 유지
      sp.forEach((v, k) => {
        if (k !== "start" && k !== "end" && !(MULTI_KEYS as readonly string[]).includes(k)) q.append(k, v);
      });
      if (next.start && next.end) {
        q.set("start", next.start);
        q.set("end", next.end);
      }
      for (const k of MULTI_KEYS) next[k].forEach((v) => q.append(k, v));
      const s = q.toString();
      router.replace(`${pathname}${s ? `?${s}` : ""}`, { scroll: false });
    },
    [filters, sp, router, pathname],
  );

  const activeCount = MULTI_KEYS.reduce((n, k) => n + (filters[k].length ? 1 : 0), 0);

  return { filters, update, activeCount };
}

/** API 쿼리 파라미터로 변환 */
export function filterQuery(f: Filters): Record<string, string | string[]> {
  const q: Record<string, string | string[]> = {};
  if (f.start && f.end) {
    q.start = f.start;
    q.end = f.end;
  }
  for (const k of MULTI_KEYS) if (f[k].length) q[k] = f[k];
  return q;
}

export function filterSearchParams(f: Filters, extra?: Record<string, string | string[]>): URLSearchParams {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...filterQuery(f), ...(extra ?? {}) })) {
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
    else p.set(k, v);
  }
  return p;
}
