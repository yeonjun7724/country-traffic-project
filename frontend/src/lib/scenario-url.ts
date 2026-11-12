import type { Filters } from "@/lib/filters";
import { screenHref } from "@/lib/links";
import type { ScenarioInput } from "@/lib/types";

/**
 * Scenario Lab 입력값 ↔ URL 쿼리. 공유 링크·새로고침·다른 화면에서의 진입("Scenario Lab 에서 비교")에 쓴다.
 *   a=10,0,30,-2,1 &an=이름   (경유가%, 연료 외 단가%, 물동량%, 차량 증감, 1일 운행)
 * 범위는 편집기(NumberField)와 같은 한계로 자른다 — 링크로 비정상 값을 주입해도 화면 입력 범위를 벗어나지 않는다.
 */
const FIELDS = [
  { k: "diesel_pct", min: -50, max: 200, int: false },
  { k: "rate_pct", min: -50, max: 200, int: false },
  { k: "demand_pct", min: -50, max: 300, int: false },
  { k: "fleet_change", min: -100, max: 100, int: true },
  { k: "trips_per_vehicle_day", min: 1, max: 5, int: true },
] as const;

export const SCENARIO_BASE: ScenarioInput = { name: "Scenario", diesel_pct: 0, demand_pct: 0, rate_pct: 0, fleet_change: 0, trips_per_vehicle_day: 1 };

export function encodeScenario(s: ScenarioInput): string {
  return FIELDS.map((f) => String(Number(s[f.k]) || (f.k === "trips_per_vehicle_day" ? 1 : 0))).join(",");
}

export function decodeScenario(v: string | null | undefined, name?: string | null): ScenarioInput | null {
  if (!v) return null;
  const parts = v.split(",");
  if (parts.length !== FIELDS.length) return null;
  const out: ScenarioInput = { ...SCENARIO_BASE, name: (name ?? "").slice(0, 100) || "Scenario" };
  for (let i = 0; i < FIELDS.length; i++) {
    const f = FIELDS[i];
    const n = Number(parts[i]);
    if (parts[i].trim() === "" || !Number.isFinite(n)) return null;
    const c = Math.min(f.max, Math.max(f.min, n));
    out[f.k] = f.int ? Math.round(c) : c;
  }
  return out;
}

/** 시나리오 이름 자동 생성 (링크로 들어올 때 이름이 없으면) */
export function scenarioName(s: Omit<ScenarioInput, "name">): string {
  const parts: string[] = [];
  const sign = (n: number) => (n > 0 ? `+${n}` : `${n}`);
  if (s.diesel_pct) parts.push(`경유가 ${sign(s.diesel_pct)}%`);
  if (s.rate_pct) parts.push(`단가 ${sign(s.rate_pct)}%`);
  if (s.demand_pct) parts.push(`수요 ${sign(s.demand_pct)}%`);
  if (s.fleet_change) parts.push(`차량 ${sign(s.fleet_change)}대`);
  return parts.join(" · ") || "Baseline 동일";
}

/** 다른 화면 → Scenario Lab 비용 시나리오 (A, 선택적으로 B). 전역 필터 유지. */
export function scenarioLink(a: Partial<ScenarioInput>, b?: Partial<ScenarioInput>, filters?: Filters): string {
  const full = (x: Partial<ScenarioInput>): ScenarioInput => {
    const s = { ...SCENARIO_BASE, ...x };
    return { ...s, name: x.name || scenarioName(s) };
  };
  const A = full(a);
  const params: Record<string, string> = { a: encodeScenario(A), an: A.name };
  if (b) {
    const B = full(b);
    params.b = encodeScenario(B);
    params.bn = B.name;
  }
  return screenHref("scenario-lab", params, filters)!;
}

/** 다른 화면 → Scenario Lab 센터 중단 분석 */
export function outageLink(warehouseId: string, filters?: Filters): string {
  return screenHref("scenario-lab", { tab: "outage", wh: warehouseId }, filters)!;
}

/** 저장된 시나리오 상세 (승인·반려) */
export function savedScenarioLink(id: number): string {
  return screenHref("scenario-lab", { tab: "saved", id: String(id) })!;
}
