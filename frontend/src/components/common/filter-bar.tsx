"use client";

import { ko } from "date-fns/locale";
import { CalendarDays, ListFilter, RotateCcw } from "lucide-react";
import { useState } from "react";
import type { DateRange } from "react-day-picker";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { dateLabel } from "@/lib/format";
import { FILTER_LABEL, useFilters, type MultiKey } from "@/lib/filters";
import { useFilterMeta } from "@/lib/queries";
import { cn } from "@/lib/utils";

import { MultiSelect } from "./multi-select";

const PRIMARY: MultiKey[] = ["warehouses", "regions", "carriers"];
const MORE: MultiKey[] = ["vehicles", "categories", "stores"];

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parse = (s: string) => new Date(`${s}T00:00:00`);
const addDays = (s: string, n: number) => {
  const d = parse(s);
  d.setDate(d.getDate() + n);
  return iso(d);
};

/** 페이지 상단 필터 바 — 기간(데이터 최신일 기준 프리셋) + 센터·권역·운송사 + 추가 필터 */
export function FilterBar({ className }: { className?: string }) {
  const meta = useFilterMeta();
  const { filters, update, activeCount } = useFilters();
  const [showMore, setShowMore] = useState(() => MORE.some((k) => filters[k].length > 0));

  if (meta.isLoading) return <Skeleton className={cn("h-10 w-full rounded-lg", className)} />;
  const m = meta.data;
  if (!m?.bounds || !m.default) {
    return (
      <div className={cn("rounded-lg border border-dashed border-border-strong px-3 py-2.5 text-[12.5px] text-muted-foreground", className)}>
        운영 데이터를 업로드하면 기간·센터·권역·운송사 필터가 활성화됩니다.
      </div>
    );
  }
  const bounds = m.bounds;
  const start = filters.start ?? m.default.start;
  const end = filters.end ?? m.default.end;
  const isDefault = !filters.start && activeCount === 0;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card px-2 py-2 shadow-card",
        className,
      )}
      role="toolbar"
      aria-label="전역 필터"
    >
      <DateRangeButton
        start={start}
        end={end}
        min={bounds.min}
        max={bounds.max}
        onChange={(s, e) => update({ start: s, end: e })}
      />
      <span className="mx-0.5 h-5 w-px bg-border" aria-hidden />
      {PRIMARY.map((k) => (
        <MultiSelect
          key={k}
          label={FILTER_LABEL[k]}
          options={m.options[k] ?? []}
          value={filters[k]}
          onChange={(v) => update({ [k]: v })}
        />
      ))}
      {(showMore || MORE.some((k) => filters[k].length > 0)) &&
        MORE.map((k) => (
          <MultiSelect
            key={k}
            label={FILTER_LABEL[k]}
            options={m.options[k] ?? []}
            value={filters[k]}
            onChange={(v) => update({ [k]: v })}
          />
        ))}
      {!showMore && !MORE.some((k) => filters[k].length > 0) && (
        <Button variant="ghost" size="sm" className="h-8 text-muted-foreground" onClick={() => setShowMore(true)}>
          <ListFilter className="size-3.5" /> 필터 추가
        </Button>
      )}
      <div className="ml-auto flex items-center gap-2">
        {!isDefault && (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 text-muted-foreground"
            onClick={() =>
              update({ start: undefined, end: undefined, warehouses: [], regions: [], carriers: [], vehicles: [], categories: [], stores: [] })
            }
          >
            <RotateCcw className="size-3.5" /> 초기화
          </Button>
        )}
      </div>
    </div>
  );
}

function DateRangeButton({
  start,
  end,
  min,
  max,
  onChange,
}: {
  start: string;
  end: string;
  min: string;
  max: string;
  onChange: (s: string, e: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DateRange | undefined>();
  const presets: { label: string; s: string; e: string }[] = [
    { label: "최근 7일", s: addDays(max, -6), e: max },
    { label: "최근 30일", s: addDays(max, -29), e: max },
    { label: "최근 90일", s: addDays(max, -89), e: max },
    { label: "전체 기간", s: min, e: max },
  ].map((p) => ({ ...p, s: p.s < min ? min : p.s }));
  const days = Math.round((parse(end).getTime() - parse(start).getTime()) / 86_400_000) + 1;

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) setDraft({ from: parse(start), to: parse(end) });
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 gap-2 px-2 font-medium" aria-label="기간 선택">
          <CalendarDays className="size-4 text-muted-foreground" />
          <span className="tabular">
            {dateLabel(start)} – {dateLabel(end)}
          </span>
          <span className="rounded bg-muted px-1.5 py-px text-[11px] font-normal text-muted-foreground tabular">{days}일</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="flex w-auto gap-0 p-0" align="start">
        <div className="flex w-36 flex-col gap-0.5 border-r border-border p-2">
          <p className="px-2 pb-1 pt-0.5 text-[11px] font-medium text-subtle-foreground">데이터 최신일 기준</p>
          {presets.map((p) => (
            <Button
              key={p.label}
              variant="ghost"
              size="sm"
              className={cn("justify-start font-normal", p.s === start && p.e === end && "bg-muted font-medium")}
              onClick={() => {
                onChange(p.s, p.e);
                setOpen(false);
              }}
            >
              {p.label}
            </Button>
          ))}
        </div>
        <div className="p-2">
          <Calendar
            mode="range"
            locale={ko}
            numberOfMonths={2}
            defaultMonth={parse(addDays(end, -32))}
            selected={draft}
            onSelect={setDraft}
            disabled={{ before: parse(min), after: parse(max) }}
            startMonth={parse(min)}
            endMonth={parse(max)}
          />
          <div className="flex items-center justify-between gap-2 border-t border-border px-2 pt-2">
            <p className="text-[11.5px] text-muted-foreground">
              데이터 범위 {dateLabel(min)} – {dateLabel(max)}
            </p>
            <Button
              size="sm"
              disabled={!draft?.from || !draft?.to}
              onClick={() => {
                if (draft?.from && draft?.to) {
                  onChange(iso(draft.from), iso(draft.to));
                  setOpen(false);
                }
              }}
            >
              적용
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
