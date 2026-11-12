/**
 * 변화량 워터폴 데이터 — Baseline 대비 '변화'를 0 에서 시작해 요인별로 쌓는다.
 * 총액(1.4억) 위에 수백만 원 증분을 얹으면 막대가 보이지 않으므로, 총액은 머리글 문장으로 따로 표시한다.
 * range 는 [아래, 위] — Recharts 의 떠 있는 막대(ranged bar) 용.
 */
export type WaterfallStep = { name: string; value: number; range: [number, number]; kind: "up" | "down" | "total" };

export function waterfallSteps(contribution: Record<string, number>, labels: Record<string, string> = {}): WaterfallStep[] {
  const out: WaterfallStep[] = [];
  let acc = 0;
  for (const [k, raw] of Object.entries(contribution)) {
    const v = Number.isFinite(raw) ? raw : 0;
    const start = acc;
    acc += v;
    out.push({ name: labels[k] ?? k, value: v, range: [Math.min(start, acc), Math.max(start, acc)], kind: v >= 0 ? "up" : "down" });
  }
  out.push({ name: "총 변화", value: acc, range: [Math.min(0, acc), Math.max(0, acc)], kind: "total" });
  return out;
}

/** 축 끝을 1·2·5×10ⁿ 단위로 올림 (눈금이 95만·190만 같은 어색한 값이 되지 않도록) */
export function niceCeil(v: number): number {
  if (!Number.isFinite(v) || v <= 0) return 0;
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 2.5, 5, 10]) if (v <= m * p) return m * p;
  return 10 * p;
}
