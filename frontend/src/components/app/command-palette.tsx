"use client";

import { Search } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

// 검색 대화상자(cmdk ~43kB)는 첫 화면에 필요 없으므로 처음 열 때 불러온다. 버튼에 마우스·포커스가 오면 미리 받아 둔다.
const loadDialog = () => import("./palette-dialog");
const PaletteDialog = dynamic(() => loadDialog().then((m) => m.PaletteDialog), { ssr: false });

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setMounted(true);
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <Button
        variant="outline"
        onClick={() => {
          setMounted(true);
          setOpen(true);
        }}
        onMouseEnter={() => void loadDialog()}
        onFocus={() => void loadDialog()}
        className="h-8 w-8 justify-center gap-2 rounded-md bg-card px-0 font-normal text-muted-foreground shadow-none sm:w-full sm:justify-start sm:px-2.5"
      >
        <Search className="size-4" />
        <span className="sr-only sm:not-sr-only sm:flex-1 sm:truncate sm:text-left">검색</span>
        <kbd className="hidden rounded border border-border bg-muted px-1.5 font-mono text-caption text-muted-foreground sm:inline">
          Ctrl K
        </kbd>
      </Button>
      {mounted && <PaletteDialog open={open} setOpen={setOpen} />}
    </>
  );
}
