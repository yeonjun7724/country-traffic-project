"use client";

import { ko } from "date-fns/locale";
import type { DateRange } from "react-day-picker";

import { Calendar } from "@/components/ui/calendar";

/** 기간 선택 달력 (2개월, 데이터 범위 밖 비활성) — filter-bar 에서 동적 로딩 */
export function RangeCalendar({
  defaultMonth,
  selected,
  onSelect,
  min,
  max,
}: {
  defaultMonth: Date;
  selected: DateRange | undefined;
  onSelect: (r: DateRange | undefined) => void;
  min: Date;
  max: Date;
}) {
  return (
    <Calendar
      mode="range"
      locale={ko}
      numberOfMonths={2}
      defaultMonth={defaultMonth}
      selected={selected}
      onSelect={onSelect}
      disabled={{ before: min, after: max }}
      startMonth={min}
      endMonth={max}
    />
  );
}
