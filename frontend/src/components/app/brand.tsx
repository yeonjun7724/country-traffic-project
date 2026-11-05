import { cn } from "@/lib/utils";

/** 로고 마크: 거점-경로 형상 (외부 브랜드 이미지 사용 안 함) */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex size-7 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-blue-600 to-indigo-700 text-white shadow-sm ring-1 ring-black/5",
        className,
      )}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
        <circle cx="6" cy="17" r="2.2" fill="currentColor" stroke="none" />
        <circle cx="18" cy="7" r="2.2" fill="currentColor" stroke="none" />
        <path d="M7.8 15.6 16.2 8.4" />
        <path d="M6 6.5h4M14 17.5h4" opacity=".55" />
      </svg>
    </span>
  );
}

export function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <BrandMark />
      <div className="grid leading-tight group-data-[collapsible=icon]:hidden">
        <span className="text-[13.5px] font-semibold tracking-tight text-foreground">LogisRisk</span>
        <span className="text-[11px] text-subtle-foreground">Logistics Intelligence</span>
      </div>
    </div>
  );
}
