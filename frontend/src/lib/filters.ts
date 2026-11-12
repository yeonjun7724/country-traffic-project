"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";
import { replaceQuery } from "@/lib/url-state";

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

/** URL 쿼리 → 전역 필터 (훅·프리페치 공용 — 같은 입력이면 같은 쿼리 키) */
export function parseFilters(sp: Pick<URLSearchParams, "get" | "getAll">): Filters {
  return {
    start: sp.get("start") ?? undefined,
    end: sp.get("end") ?? undefined,
    warehouses: sp.getAll("warehouses"),
    regions: sp.getAll("regions"),
    carriers: sp.getAll("carriers"),
    vehicles: sp.getAll("vehicles"),
    categories: sp.getAll("categories"),
    stores: sp.getAll("stores"),
  };
}

export function useFilters() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const filters: Filters = useMemo(() => parseFilters(sp), [sp],
  );

  const update = useCallback(
    (patch: Partial<Filters>) =>
      // 바뀐 키만 갱신 — 화면 고유 파라미터(탭 등)와 진행 중인 다른 URL 변경을 보존
      replaceQuery(router, pathname, sp.toString(), (q) => {
        if ("start" in patch || "end" in patch) {
          const start = "start" in patch ? patch.start : (q.get("start") ?? undefined);
          const end = "end" in patch ? patch.end : (q.get("end") ?? undefined);
          q.delete("start");
          q.delete("end");
          if (start && end) {
            q.set("start", start);
            q.set("end", end);
          }
        }
        for (const k of MULTI_KEYS) {
          if (!(k in patch)) continue;
          q.delete(k);
          (patch[k] ?? []).forEach((v) => q.append(k, v));
        }
      }),
    [sp, router, pathname],
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
