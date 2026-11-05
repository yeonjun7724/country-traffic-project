"use client";

import { Building2, Check, ChevronDown, FlaskConical } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useWorkspace } from "@/lib/workspace";

export function WorkspaceSwitcher() {
  const { me, switchWorkspace } = useWorkspace();
  const cur = me?.workspace;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-8 gap-2 px-2 font-medium" aria-label="워크스페이스 전환">
          {cur?.is_demo ? <FlaskConical className="size-4 text-kind-demo" /> : <Building2 className="size-4 text-muted-foreground" />}
          <span className="max-w-48 truncate">{cur ? displayName(cur.name, cur.is_demo) : "워크스페이스"}</span>
          {cur?.is_demo && (
            <span className="rounded-sm bg-kind-demo/12 px-1.5 py-px text-[10.5px] font-semibold text-kind-demo">샘플</span>
          )}
          <ChevronDown className="size-3.5 text-subtle-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">워크스페이스</DropdownMenuLabel>
        {me?.workspaces.map((w) => (
          <DropdownMenuItem key={w.id} onSelect={() => w.id !== cur?.id && switchWorkspace(w.id)} className="items-start gap-2.5 py-2">
            {w.is_demo ? <FlaskConical className="mt-0.5 size-4 text-kind-demo" /> : <Building2 className="mt-0.5 size-4" />}
            <div className="grid flex-1 gap-0.5">
              <span className="font-medium">{displayName(w.name, w.is_demo)}</span>
              <span className="text-xs text-muted-foreground">
                {w.is_demo ? "시연용 샘플 데이터 · 실제 성과 아님" : "우리 회사 운영 데이터"}
              </span>
            </div>
            {w.id === cur?.id && <Check className="mt-0.5 size-4 text-primary" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <div className="px-2 py-1.5 text-[11px] leading-relaxed text-subtle-foreground">
          워크스페이스 간 데이터는 섞이지 않습니다.
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function displayName(name: string, demo: boolean) {
  return demo ? "샘플 워크스페이스" : name;
}
