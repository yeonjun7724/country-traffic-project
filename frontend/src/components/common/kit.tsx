"use client";

import { AlertOctagon, AlertTriangle, CheckCircle2, Download, Info, Loader2, type LucideIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { download } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

// ── 지표 타일 ─────────────────────────────────────────────────────────
export function StatTile({
  label,
  value,
  unit,
  sub,
  tone,
  className,
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  sub?: React.ReactNode;
  tone?: "success" | "warning" | "danger" | "info" | "external";
  className?: string;
  icon?: LucideIcon;
}) {
  return (
    <div className={cn("rounded-xl border border-border bg-card px-4 py-3.5 shadow-card", className)}>
      <div className="flex items-center gap-1.5 text-[12px] font-medium text-muted-foreground">
        {Icon && <Icon className="size-3.5" />}
        {label}
      </div>
      <div className="mt-1.5 flex items-baseline gap-1">
        <span
          className={cn(
            "text-[22px] font-semibold leading-none tracking-tight tabular",
            tone === "success" && "text-success",
            tone === "warning" && "text-warning",
            tone === "danger" && "text-danger",
            tone === "info" && "text-info",
            tone === "external" && "text-external",
          )}
        >
          {value}
        </span>
        {unit && <span className="text-[12.5px] font-medium text-muted-foreground">{unit}</span>}
      </div>
      {sub && <div className="mt-1.5 text-[11.5px] text-subtle-foreground tabular">{sub}</div>}
    </div>
  );
}

// ── 안내 상자 ─────────────────────────────────────────────────────────
const CALLOUT = {
  info: { icon: Info, box: "border-info/20 bg-info/[0.05]", ic: "text-info" },
  warn: { icon: AlertTriangle, box: "border-warning/25 bg-warning/[0.06]", ic: "text-warning" },
  danger: { icon: AlertOctagon, box: "border-danger/25 bg-danger/[0.05]", ic: "text-danger" },
  success: { icon: CheckCircle2, box: "border-success/25 bg-success/[0.05]", ic: "text-success" },
} as const;

export function Callout({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: keyof typeof CALLOUT;
  title?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  const c = CALLOUT[tone];
  const Icon = c.icon;
  return (
    <div role={tone === "danger" ? "alert" : undefined} className={cn("flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-[12.5px] leading-relaxed", c.box, className)}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", c.ic)} />
      <div className="min-w-0 text-foreground/85">
        {title && <span className="mr-1 font-semibold text-foreground">{title}</span>}
        {children}
      </div>
    </div>
  );
}

// ── URL 동기화 탭 ────────────────────────────────────────────────────
export function useUrlTab(tabs: string[], key = "tab") {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const cur = sp.get(key);
  const tab = cur && tabs.includes(cur) ? cur : tabs[0];
  const set = (v: string) => {
    const q = new URLSearchParams(sp.toString());
    if (v === tabs[0]) q.delete(key);
    else q.set(key, v);
    router.replace(`${pathname}${q.toString() ? `?${q}` : ""}`, { scroll: false });
  };
  return [tab, set] as const;
}

export function LineTabs({ items, value, onChange }: { items: { v: string; label: React.ReactNode }[]; value: string; onChange: (v: string) => void }) {
  return (
    <Tabs value={value} onValueChange={onChange}>
      <TabsList variant="line" className="mb-4 h-9 w-full justify-start gap-5 overflow-x-auto rounded-none border-b border-border p-0">
        {items.map((t) => (
          <TabsTrigger
            key={t.v}
            value={t.v}
            className="h-9 flex-none rounded-none border-0 border-b-2 border-transparent px-0.5 text-[13px] data-[state=active]:border-primary data-[state=active]:text-foreground data-[state=active]:shadow-none"
          >
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}

// ── 권한 확인 다운로드 버튼 ──────────────────────────────────────────
export function DownloadButton({
  path,
  params,
  filename,
  label,
  permission = "data.export",
  variant = "outline",
  disabled,
}: {
  path: string;
  params?: URLSearchParams;
  filename: string;
  label: string;
  permission?: string;
  variant?: "outline" | "default" | "secondary" | "ghost";
  disabled?: boolean;
}) {
  const { can } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const allowed = can(permission);
  const btn = (
    <Button
      variant={variant}
      size="sm"
      disabled={!allowed || busy || disabled}
      onClick={async () => {
        setBusy(true);
        try {
          await download(path, params, filename);
          toast.success(`${label} 완료`, { description: "내보내기 기록이 감사 로그에 남습니다." });
        } catch (e) {
          toast.error("내보내기 실패", { description: (e as Error).message });
        } finally {
          setBusy(false);
        }
      }}
    >
      {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Download className="size-3.5" />} {label}
    </Button>
  );
  if (allowed) return btn;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0}>{btn}</span>
      </TooltipTrigger>
      <TooltipContent>분석가 이상 권한이 필요합니다</TooltipContent>
    </Tooltip>
  );
}

// ── 숫자 입력 ────────────────────────────────────────────────────────
export function NumberField({
  id,
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  suffix,
  hint,
  disabled,
}: {
  id: string;
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
  hint?: string;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id} className="text-[12px] font-medium text-muted-foreground">
        {label}
      </Label>
      <div className="relative">
        <input
          id={id}
          type="number"
          inputMode="decimal"
          value={Number.isFinite(value) ? value : ""}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          onChange={(e) => {
            const v = e.target.value === "" ? NaN : Number(e.target.value);
            if (!Number.isNaN(v)) onChange(min !== undefined && v < min ? min : max !== undefined && v > max ? max : v);
          }}
          className={cn(
            "h-8 w-full rounded-md border border-input bg-card px-2.5 text-[13px] tabular shadow-none outline-none transition-colors",
            "focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-60",
            suffix && "pr-9",
          )}
        />
        {suffix && <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[11.5px] text-subtle-foreground">{suffix}</span>}
      </div>
      {hint && <p className="text-[11px] text-subtle-foreground">{hint}</p>}
    </div>
  );
}

export function Field({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("space-y-1", className)}>
      <div className="text-[12px] font-medium text-muted-foreground">{label}</div>
      {children}
    </div>
  );
}

/** 상태 배지(시나리오·조치) */
export const STATUS_LABEL: Record<string, { label: string; tone: "neutral" | "info" | "warning" | "success" | "danger" }> = {
  draft: { label: "초안", tone: "neutral" },
  proposed: { label: "승인 대기", tone: "warning" },
  approved: { label: "승인", tone: "success" },
  rejected: { label: "반려", tone: "danger" },
  archived: { label: "보관", tone: "neutral" },
  open: { label: "열림", tone: "info" },
  in_progress: { label: "진행 중", tone: "warning" },
  done: { label: "완료", tone: "success" },
  dismissed: { label: "보류", tone: "neutral" },
};
