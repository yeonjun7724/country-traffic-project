import { AlertCircle, RefreshCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  compact,
}: {
  icon?: LucideIcon;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-border-strong bg-card/50 text-center",
        compact ? "gap-1.5 px-4 py-8" : "gap-2 px-6 py-14",
        className,
      )}
    >
      {Icon && (
        <div className="mb-1 flex size-10 items-center justify-center rounded-full bg-muted">
          <Icon className="size-5 text-muted-foreground" />
        </div>
      )}
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {description && <p className="max-w-md text-[13px] leading-relaxed text-muted-foreground">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, className }: { error: unknown; onRetry?: () => void; className?: string }) {
  const msg = error instanceof Error ? error.message : "알 수 없는 오류";
  return (
    <div
      role="alert"
      className={cn("flex items-start gap-3 rounded-xl border border-danger/25 bg-danger/[0.05] p-4 text-[13px]", className)}
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0 text-danger" />
      <div className="flex-1 space-y-1">
        <p className="font-medium text-foreground">데이터를 불러오지 못했습니다</p>
        <p className="text-muted-foreground">{msg}</p>
      </div>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RefreshCw className="size-3.5" /> 다시 시도
        </Button>
      )}
    </div>
  );
}

export function NotComputable({ reason, className }: { reason?: string; className?: string }) {
  return (
    <div className={cn("text-[13px] text-muted-foreground", className)}>
      <span className="font-medium text-warning">계산 불가</span>
      {reason ? ` · ${reason}` : ""}
    </div>
  );
}
