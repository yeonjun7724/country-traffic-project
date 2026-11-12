"use client";

import { Bookmark, BookmarkPlus, Trash2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { ALL_NAV } from "@/lib/nav";
import { useApi, useApiMutation } from "@/lib/use-api";
import { useWorkspace } from "@/lib/workspace";

export type SavedView = { id: string; name: string; screen: string; query: string; created_by: string; created_at: string };

/** 저장된 보기 목록 (워크스페이스 공유) */
export function useSavedViews() {
  return useApi<SavedView[]>("/api/views", { staleTime: 60_000 });
}

export function viewHref(v: SavedView): string | null {
  const nav = ALL_NAV.find((n) => n.key === v.screen);
  return nav ? `${nav.href}${v.query ? `?${v.query}` : ""}` : null;
}

function currentScreen(pathname: string) {
  return ALL_NAV.find((n) => pathname.startsWith(n.href.replace(/\/$/, "")));
}

/** 상단 바: 저장된 보기 열기 · 현재 화면(필터·탭·입력값 포함)을 보기로 저장 · 삭제 */
export function SavedViewsMenu() {
  const { can } = useWorkspace();
  const router = useRouter();
  const pathname = usePathname();
  const views = useSavedViews();
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const screen = currentScreen(pathname);
  const save = useApiMutation<void, SavedView>(
    () => ({ path: "/api/views", body: { name, screen: screen?.key, query: window.location.search.replace(/^\?/, "") } }),
    { success: (v) => `'${v.name}' 보기를 저장했습니다` },
  );
  const del = useApiMutation<string, unknown>((id) => ({ path: `/api/views/${id}`, method: "DELETE" }), { success: "보기를 지웠습니다" });
  const list = views.data ?? [];

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="text-muted-foreground">
            <Bookmark className="size-4" />
            <span className="sr-only">저장된 보기 {list.length}개</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <DropdownMenuLabel className="text-small font-normal text-muted-foreground">저장된 보기 · 이 워크스페이스</DropdownMenuLabel>
          {list.length === 0 && <p className="px-2 py-2 text-small text-muted-foreground">아직 없습니다. 자주 보는 필터·탭 조합을 저장해 두세요.</p>}
          {list.map((v) => {
            const href = viewHref(v);
            const title = ALL_NAV.find((n) => n.key === v.screen)?.title ?? v.screen;
            return (
              <DropdownMenuItem key={v.id} className="items-start gap-2" disabled={!href} onSelect={() => href && router.push(href)}>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-body font-medium">{v.name}</p>
                  <p className="truncate text-caption text-muted-foreground">{title}</p>
                </div>
                {can("scenario.save") && (
                  <button
                    type="button"
                    className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-danger"
                    aria-label={`${v.name} 보기 지우기`}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      del.mutate(v.id);
                    }}
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                )}
              </DropdownMenuItem>
            );
          })}
          {can("scenario.save") && screen && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={() => {
                  setName(screen.title);
                  setSaving(true);
                }}
              >
                <BookmarkPlus className="size-4" /> 현재 화면을 보기로 저장…
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog open={saving} onOpenChange={setSaving}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>현재 화면을 보기로 저장</DialogTitle>
            <DialogDescription>
              {screen?.title} 의 기간·센터·권역 등 전역 필터와 탭·입력값을 그대로 저장합니다. 같은 이름이면 덮어씁니다.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) save.mutate(undefined, { onSuccess: () => setSaving(false) });
            }}
            className="space-y-4"
          >
            <Input value={name} onChange={(e) => setName(e.target.value.slice(0, 80))} aria-label="보기 이름" autoFocus />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setSaving(false)}>
                취소
              </Button>
              <Button type="submit" disabled={!name.trim() || save.isPending}>
                저장
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
