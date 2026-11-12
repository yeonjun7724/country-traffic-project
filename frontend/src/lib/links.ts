import { filterSearchParams, type Filters } from "@/lib/filters";
import { ALL_NAV } from "@/lib/nav";

/**
 * 화면 간 맥락 링크 — 현재 전역 필터(기간·센터·권역 …)를 유지한 채 다른 화면의 특정 탭·상태로 이동.
 * screen 은 nav key (control-tower, inventory …). 알 수 없는 키면 null (깨진 링크를 만들지 않는다).
 */
export function screenHref(screen: string, params: Record<string, string | string[] | undefined> = {}, filters?: Filters): string | null {
  const nav = ALL_NAV.find((n) => n.key === screen);
  if (!nav) return null;
  const extra: Record<string, string | string[]> = {};
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") extra[k] = v;
  const q = filters ? filterSearchParams(filters, extra) : filterSearchParams({ warehouses: [], regions: [], carriers: [], vehicles: [], categories: [], stores: [] }, extra);
  const s = q.toString();
  const anchor = ANCHOR[screen]?.(params);
  return `${nav.href}${s ? `?${s}` : ""}${anchor ? `#${anchor}` : ""}`;
}

/** 목적지 화면 안의 섹션 앵커 (긴 화면에서 해당 섹션으로 바로 스크롤) */
const ANCHOR: Record<string, (p: Record<string, unknown>) => string | undefined> = {
  "control-tower": (p) => (p.ledger ? "ledger" : undefined),
};

/** 알림 목적지 → 링크 문구 */
export const TARGET_LABEL: Record<string, string> = {
  "control-tower": "지연 원장 보기",
  transportation: "운송비 분석 보기",
  inventory: "결품 SKU 보기",
  "data-hub": "다시 업로드",
};
