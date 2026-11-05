"use client";

import { Check, ChevronDown, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export type Opt = { value: string; label: string };

export function MultiSelect({
  label,
  options,
  value,
  onChange,
  disabled,
}: {
  label: string;
  options: Opt[];
  value: string[];
  onChange: (v: string[]) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const selected = new Set(value);
  const summary =
    value.length === 0
      ? null
      : value.length === 1
        ? (options.find((o) => o.value === value[0])?.label ?? value[0])
        : `${value.length}개`;
  const toggle = (v: string) => onChange(selected.has(v) ? value.filter((x) => x !== v) : [...value, v]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled || options.length === 0}
          className={cn(
            "h-8 gap-1.5 rounded-md border-dashed bg-card px-2.5 font-normal shadow-none",
            value.length > 0 && "border-solid border-primary/40 bg-primary/[0.04] text-foreground",
          )}
          aria-label={`${label} 필터`}
        >
          <span className="text-muted-foreground">{label}</span>
          {summary && (
            <>
              <span className="h-3.5 w-px bg-border" aria-hidden />
              <span className="max-w-36 truncate font-medium">{summary}</span>
            </>
          )}
          <ChevronDown className="size-3.5 text-subtle-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <Command>
          {options.length > 7 && <CommandInput placeholder={`${label} 검색`} className="h-9" />}
          <CommandList className="max-h-72">
            <CommandEmpty>결과 없음</CommandEmpty>
            <CommandGroup>
              {options.map((o) => {
                const on = selected.has(o.value);
                return (
                  <CommandItem key={o.value} value={`${o.label} ${o.value}`} onSelect={() => toggle(o.value)} className="gap-2">
                    <span
                      className={cn(
                        "flex size-4 items-center justify-center rounded-[4px] border",
                        on ? "border-primary bg-primary text-primary-foreground" : "border-border-strong",
                      )}
                    >
                      {on && <Check className="size-3" />}
                    </span>
                    <span className="flex-1 truncate">{o.label}</span>
                    {o.label !== o.value && <span className="text-[11px] text-subtle-foreground">{o.value}</span>}
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
          {value.length > 0 && (
            <div className="border-t border-border p-1">
              <Button variant="ghost" size="sm" className="w-full justify-center" onClick={() => onChange([])}>
                <X className="size-3.5" /> 선택 해제
              </Button>
            </div>
          )}
        </Command>
      </PopoverContent>
    </Popover>
  );
}
