"use client";

import { Monitor, Moon, Search, Sun } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { Command } from "@/components/ui/command";
import { ALL_NAV } from "@/lib/nav";
import { useSearch } from "@/lib/queries";

/** 검색 결과 → 이동할 화면·필터 (상세 화면이 아직 없는 유형은 선택 불가로 표시) */
const TARGET: Record<string, ((id: string) => string) | undefined> = {
  stores: (id) => `/control-tower/?stores=${encodeURIComponent(id)}`,
  warehouses: (id) => `/control-tower/?warehouses=${encodeURIComponent(id)}`,
  vehicles: (id) => `/control-tower/?vehicles=${encodeURIComponent(id)}`,
};

function useDebounced<T>(v: T, ms = 200) {
  const [d, setD] = useState(v);
  useEffect(() => {
    const t = setTimeout(() => setD(v), ms);
    return () => clearTimeout(t);
  }, [v, ms]);
  return d;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const q = useDebounced(text);
  const router = useRouter();
  const { setTheme } = useTheme();
  const res = useSearch(q);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (href: string) => {
    setOpen(false);
    setText("");
    router.push(href);
  };

  return (
    <>
      <Button
        variant="outline"
        onClick={() => setOpen(true)}
        className="h-8 w-full max-w-72 justify-start gap-2 rounded-md bg-card px-2.5 font-normal text-muted-foreground shadow-none"
        aria-label="검색 열기"
      >
        <Search className="size-4" />
        <span className="flex-1 truncate text-left">배송지·센터·차량·주문 검색</span>
        <kbd className="hidden rounded border border-border bg-muted px-1.5 font-mono text-[10px] text-muted-foreground sm:inline">
          Ctrl K
        </kbd>
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen} title="검색" description="화면 이동과 데이터 검색" className="sm:max-w-xl">
        <Command shouldFilter={false}>
          <CommandInput placeholder="화면 이름, 배송지·센터·차량·주문·영업소 검색…" value={text} onValueChange={setText} />
          <CommandList className="max-h-[60vh]">
            <CommandEmpty>{q ? (res.isFetching ? "검색 중…" : `'${q}'에 대한 결과가 없습니다.`) : "검색어를 입력하세요."}</CommandEmpty>
            {(res.data ?? []).map((g) => (
              <CommandGroup key={g.entity} heading={`${g.label} · ${g.total.toLocaleString()}건`}>
                {g.items.map((it) => {
                  const to = TARGET[g.entity];
                  return (
                    <CommandItem
                      key={`${g.entity}-${String(it.id)}`}
                      value={`${g.entity}-${String(it.id)}`}
                      disabled={!to}
                      onSelect={() => to && go(to(String(it.id)))}
                    >
                      <div className="grid min-w-0 flex-1">
                        <span className="truncate">{it.title}</span>
                        <span className="truncate text-xs text-muted-foreground">
                          {String(it.id)}
                          {it.subtitle ? ` · ${String(it.subtitle)}` : ""}
                        </span>
                      </div>
                      <CommandShortcut className="tracking-normal">{to ? "필터 적용" : "상세 화면 준비 중"}</CommandShortcut>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            ))}
            {!q && (
                <>
                  <CommandGroup heading="화면">
                    {ALL_NAV.map((n) => (
                      <CommandItem key={n.key} value={n.title} onSelect={() => go(n.href)}>
                        <n.icon className="size-4" />
                        <span>{n.title}</span>
                        <span className="text-xs text-muted-foreground">{n.subtitle}</span>
                        {!n.ready && <CommandShortcut className="tracking-normal">준비 중</CommandShortcut>}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                  <CommandSeparator />
                  <CommandGroup heading="테마">
                    <CommandItem value="theme-light" onSelect={() => (setTheme("light"), setOpen(false))}>
                      <Sun className="size-4" /> 라이트 모드
                    </CommandItem>
                    <CommandItem value="theme-dark" onSelect={() => (setTheme("dark"), setOpen(false))}>
                      <Moon className="size-4" /> 다크 모드
                    </CommandItem>
                    <CommandItem value="theme-system" onSelect={() => (setTheme("system"), setOpen(false))}>
                      <Monitor className="size-4" /> 시스템 설정 따르기
                    </CommandItem>
                  </CommandGroup>
                </>
              )}
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  );
}
