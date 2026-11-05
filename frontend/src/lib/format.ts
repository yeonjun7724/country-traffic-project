/** 숫자·단위 표기 — 원값은 API 그대로, 반올림·만/억 표기는 화면에서만. */

const nf0 = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 });

export const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** 원화: 1억 이상 '1.42억', 1만 이상 '17만', 그 외 '9,800' (단위 '원'은 별도) */
export function won(v: number | null | undefined, { compact = true }: { compact?: boolean } = {}): string {
  if (!isNum(v)) return "—";
  const a = Math.abs(v);
  if (compact && a >= 1e8) return `${nf2.format(v / 1e8)}억`;
  if (compact && a >= 1e4) return `${nf0.format(v / 1e4)}만`;
  return nf0.format(v);
}

export function num(v: number | null | undefined, digits = 0): string {
  if (!isNum(v)) return "—";
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(v);
}

export function pct(v: number | null | undefined, digits = 1): string {
  if (!isNum(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

/** Metric 의 unit 에 맞춘 값 + 단위 분리 표기 (KPI 카드용) */
export function metricParts(value: number | null | undefined, unit: string): { value: string; unit: string } {
  if (!isNum(value)) return { value: "—", unit: "" };
  switch (unit) {
    case "%":
      return { value: (value * 100).toFixed(1), unit: "%" };
    case "원": {
      const a = Math.abs(value);
      if (a >= 1e8) return { value: nf2.format(value / 1e8), unit: "억원" };
      if (a >= 1e4) return { value: nf0.format(value / 1e4), unit: "만원" };
      return { value: nf0.format(value), unit: "원" };
    }
    case "원/km":
    case "원/kg":
      return { value: nf0.format(value), unit };
    default:
      return { value: Math.abs(value) >= 100 ? nf0.format(value) : nf2.format(value), unit };
  }
}

export function metricText(value: number | null | undefined, unit: string): string {
  const p = metricParts(value, unit);
  return p.value === "—" ? "—" : `${p.value}${p.unit === "%" ? "%" : p.unit ? ` ${p.unit}` : ""}`;
}

export function deltaText(d: number | null | undefined): string {
  if (!isNum(d)) return "—";
  return `${d > 0 ? "+" : d < 0 ? "−" : "±"}${nf1.format(Math.abs(d))}%`;
}

export function dateLabel(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
}

export function dateTimeLabel(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return iso;
  return `${dateLabel(iso.slice(0, 10))} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function shortDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}
