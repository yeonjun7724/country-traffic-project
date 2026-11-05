"use client";

import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
  type SortingState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData, TValue> {
    align?: "left" | "right" | "center";
    className?: string;
  }
}

const ROW_H = 36;

/**
 * 가상 스크롤 데이터 표 — 수천 행도 DOM 은 화면에 보이는 행만.
 * selection 은 rowKey 기준 controlled (지도·표·차트 선택 동기화용).
 */
export function DataTable<T>({
  data,
  columns,
  rowKey,
  height = 360,
  selected,
  onSelectedChange,
  initialSort,
  empty,
  onRowClick,
  className,
  ariaLabel,
}: {
  data: T[];
  columns: ColumnDef<T, unknown>[];
  rowKey: (row: T) => string;
  height?: number;
  selected?: string[];
  onSelectedChange?: (keys: string[]) => void;
  initialSort?: SortingState;
  empty?: React.ReactNode;
  onRowClick?: (row: T) => void;
  className?: string;
  ariaLabel?: string;
}) {
  const [sorting, setSorting] = useState<SortingState>(initialSort ?? []);
  const selectable = !!onSelectedChange;
  const rowSelection: RowSelectionState = useMemo(
    () => Object.fromEntries((selected ?? []).map((k) => [k, true])),
    [selected],
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting, rowSelection },
    getRowId: (r) => rowKey(r),
    onSortingChange: setSorting,
    enableRowSelection: selectable,
    onRowSelectionChange: (u) => {
      const next = typeof u === "function" ? u(rowSelection) : u;
      onSelectedChange?.(Object.keys(next).filter((k) => next[k]));
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const rows = table.getRowModel().rows;
  const parentRef = useRef<HTMLDivElement>(null);
  const v = useVirtualizer({ count: rows.length, getScrollElement: () => parentRef.current, estimateSize: () => ROW_H, overscan: 12 });
  const items = v.getVirtualItems();
  const padTop = items.length ? items[0].start : 0;
  const padBottom = items.length ? v.getTotalSize() - items[items.length - 1].end : 0;
  const colCount = table.getVisibleLeafColumns().length + (selectable ? 1 : 0);

  return (
    <div
      ref={parentRef}
      className={cn("relative overflow-auto rounded-lg border border-border", className)}
      style={{ maxHeight: height }}
      tabIndex={0}
      aria-label={ariaLabel}
      role="region"
    >
      <table className="w-full border-separate border-spacing-0 text-[12.5px]">
        <thead className="sticky top-0 z-10 bg-muted/95 backdrop-blur">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {selectable && (
                <th className="w-9 border-b border-border px-2">
                  <Check
                    checked={table.getIsAllRowsSelected()}
                    indeterminate={table.getIsSomeRowsSelected()}
                    onChange={() => table.toggleAllRowsSelected()}
                    label="전체 선택"
                  />
                </th>
              )}
              {hg.headers.map((h) => {
                const meta = h.column.columnDef.meta;
                const sort = h.column.getIsSorted();
                const can = h.column.getCanSort();
                return (
                  <th
                    key={h.id}
                    scope="col"
                    aria-sort={sort === "asc" ? "ascending" : sort === "desc" ? "descending" : "none"}
                    className={cn(
                      "h-9 whitespace-nowrap border-b border-border px-3 text-[11.5px] font-medium text-muted-foreground",
                      meta?.align === "right" ? "text-right" : "text-left",
                    )}
                  >
                    {can ? (
                      <button
                        type="button"
                        onClick={h.column.getToggleSortingHandler()}
                        className={cn(
                          "inline-flex items-center gap-1 rounded hover:text-foreground",
                          meta?.align === "right" && "flex-row-reverse",
                        )}
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {sort === "asc" ? (
                          <ArrowUp className="size-3" />
                        ) : sort === "desc" ? (
                          <ArrowDown className="size-3" />
                        ) : (
                          <ChevronsUpDown className="size-3 opacity-40" />
                        )}
                      </button>
                    ) : (
                      flexRender(h.column.columnDef.header, h.getContext())
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={colCount} className="px-3 py-10 text-center text-[13px] text-muted-foreground">
                {empty ?? "표시할 데이터가 없습니다."}
              </td>
            </tr>
          )}
          {padTop > 0 && (
            <tr aria-hidden>
              <td colSpan={colCount} style={{ height: padTop }} />
            </tr>
          )}
          {items.map((vi) => {
            const row = rows[vi.index];
            const sel = row.getIsSelected();
            return (
              <tr
                key={row.id}
                data-selected={sel || undefined}
                onClick={onRowClick ? () => onRowClick(row.original) : selectable ? () => row.toggleSelected() : undefined}
                className={cn(
                  "group transition-colors hover:bg-muted/50",
                  (onRowClick || selectable) && "cursor-pointer",
                  sel && "bg-primary/[0.06] hover:bg-primary/[0.09]",
                )}
                style={{ height: ROW_H }}
              >
                {selectable && (
                  <td className="border-b border-border px-2" onClick={(e) => e.stopPropagation()}>
                    <Check checked={sel} onChange={() => row.toggleSelected()} label="행 선택" />
                  </td>
                )}
                {row.getVisibleCells().map((c) => {
                  const meta = c.column.columnDef.meta;
                  return (
                    <td
                      key={c.id}
                      className={cn(
                        "whitespace-nowrap border-b border-border px-3 text-foreground/90",
                        meta?.align === "right" && "text-right tabular",
                        meta?.className,
                      )}
                    >
                      {flexRender(c.column.columnDef.cell, c.getContext())}
                    </td>
                  );
                })}
              </tr>
            );
          })}
          {padBottom > 0 && (
            <tr aria-hidden>
              <td colSpan={colCount} style={{ height: padBottom }} />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function Check({ checked, indeterminate, onChange, label }: { checked: boolean; indeterminate?: boolean; onChange: () => void; label: string }) {
  return (
    <input
      type="checkbox"
      aria-label={label}
      checked={checked}
      ref={(el) => {
        if (el) el.indeterminate = !!indeterminate && !checked;
      }}
      onChange={onChange}
      className="size-3.5 cursor-pointer rounded-[3px] border-border-strong accent-[var(--primary)]"
    />
  );
}
