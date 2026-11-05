import { cn } from "@/lib/utils";

type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "external" | "demo";

const TONE: Record<Tone, string> = {
  neutral: "bg-muted text-muted-foreground ring-border",
  success: "bg-success/10 text-success ring-success/20",
  warning: "bg-warning/10 text-warning ring-warning/25",
  danger: "bg-danger/10 text-danger ring-danger/20",
  info: "bg-info/10 text-info ring-info/20",
  external: "bg-external/10 text-external ring-external/20",
  demo: "bg-kind-demo/10 text-kind-demo ring-kind-demo/25",
};

export function Pill({
  tone = "neutral",
  className,
  children,
  dot,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center gap-1 rounded-full px-2 text-[11px] font-medium whitespace-nowrap ring-1 ring-inset",
        TONE[tone],
        className,
      )}
    >
      {dot && <span className="size-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

const KIND: Record<string, { label: string; cls: string }> = {
  observed: { label: "관측", cls: "text-kind-observed bg-kind-observed/10 ring-kind-observed/20" },
  derived: { label: "관측 기반 파생", cls: "text-kind-derived bg-kind-derived/10 ring-kind-derived/20" },
  forecast: { label: "모델 예측", cls: "text-kind-forecast bg-kind-forecast/10 ring-kind-forecast/20" },
  simulated: { label: "시뮬레이션", cls: "text-kind-simulated bg-kind-simulated/10 ring-kind-simulated/20" },
  assumption: { label: "가정 기반 추정", cls: "text-kind-assumption bg-kind-assumption/10 ring-kind-assumption/25" },
  demo: { label: "샘플 데이터", cls: "text-kind-demo bg-kind-demo/10 ring-kind-demo/25" },
};

/** 데이터 성격 배지 — 관측/예측/시뮬레이션/가정/샘플을 항상 구분 표기 */
export function KindBadge({ kind, className }: { kind: string; className?: string }) {
  const k = KIND[kind] ?? KIND.observed;
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-full px-2 text-[11px] font-medium whitespace-nowrap ring-1 ring-inset",
        k.cls,
        className,
      )}
    >
      {k.label}
    </span>
  );
}

export function SampleDataBadge() {
  return (
    <Pill tone="demo" dot>
      샘플 데이터
    </Pill>
  );
}
