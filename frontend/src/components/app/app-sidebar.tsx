"use client";

import { ChevronsUpDown, LogOut, Monitor, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTheme } from "next-themes";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import { useQuery } from "@tanstack/react-query";

import { client, unwrap } from "@/lib/api";
import { NAV } from "@/lib/nav";
import { useWorkspace } from "@/lib/workspace";

import { Brand } from "./brand";

/** 필터(기간·센터 등)는 화면을 옮겨도 유지 */
const CARRY = ["start", "end", "warehouses", "regions", "carriers", "vehicles", "categories", "stores"];

export function AppSidebar() {
  const pathname = usePathname();
  const sp = useSearchParams();
  const router = useRouter();
  // 화면에 보이는 링크 전부를 미리 받지 않는다(모든 화면 진입 시 JS ~2.7MB 다운로드의 원인). 의도가 보일 때만 프리페치.
  const intent = (href: string) => ({ prefetch: false, onMouseEnter: () => router.prefetch(href), onFocus: () => router.prefetch(href) });
  const carry = new URLSearchParams();
  sp.forEach((v, k) => CARRY.includes(k) && carry.append(k, v));
  const qs = carry.toString();

  return (
    <Sidebar collapsible="icon" variant="sidebar">
      <SidebarHeader className="h-14 justify-center border-b border-sidebar-border px-3">
        <Link href={`/control-tower/${qs ? `?${qs}` : ""}`} {...intent("/control-tower/")} className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Brand />
        </Link>
      </SidebarHeader>
      <SidebarContent className="gap-0 py-2">
        {NAV.map((sec) => (
          <SidebarGroup key={sec.section} className="py-1.5">
            <SidebarGroupLabel className="h-7 text-caption font-medium tracking-wide text-subtle-foreground">
              {sec.section}
            </SidebarGroupLabel>
            <SidebarMenu className="gap-0.5">
              {sec.items.map((it) => {
                const active = pathname.startsWith(it.href.replace(/\/$/, ""));
                const Icon = it.icon;
                return (
                  <SidebarMenuItem key={it.key}>
                    <SidebarMenuButton
                      asChild
                      isActive={active}
                      tooltip={it.ready ? it.title : `${it.title} · 준비 중`}
                      className="relative h-8 gap-2.5 text-body font-medium before:absolute before:inset-y-1.5 before:-left-2 before:w-[3px] before:rounded-r-full before:bg-transparent data-[active=true]:bg-sidebar-accent data-[active=true]:font-semibold data-[active=true]:text-sidebar-accent-foreground data-[active=true]:before:bg-primary group-data-[collapsible=icon]:before:hidden"
                    >
                      <Link href={`${it.href}${qs ? `?${qs}` : ""}`} {...intent(it.href)} aria-current={active ? "page" : undefined}>
                        <Icon className={active ? "text-primary" : "text-subtle-foreground"} />
                        <span className={it.ready ? "" : "text-subtle-foreground"}>{it.title}</span>
                      </Link>
                    </SidebarMenuButton>
                    {!it.ready && (
                      <SidebarMenuBadge className="rounded-sm border border-sidebar-border px-1 text-caption font-medium text-subtle-foreground">
                        준비 중
                      </SidebarMenuBadge>
                    )}
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border p-2">
        <UserMenu />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

function UserMenu() {
  const { me } = useWorkspace();
  const auth = useQuery({ queryKey: ["auth"], queryFn: () => unwrap(client.GET("/api/auth/status")), staleTime: 60_000 });
  const { theme, setTheme } = useTheme();
  const initials = (me?.display_name ?? "?").slice(0, 1);
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent">
              <span className="sr-only">사용자 메뉴:</span>
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-body font-semibold text-primary">
                {initials}
              </span>
              <div className="grid flex-1 text-left leading-tight">
                <span className="truncate text-body font-medium text-foreground">{me?.display_name ?? "—"}</span>
                <span className="truncate text-caption text-subtle-foreground">{me?.role_label ?? " "}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4 text-subtle-foreground" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-60">
            <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
              {me?.display_name} · {me?.role_label}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-xs">테마</DropdownMenuLabel>
            <DropdownMenuRadioGroup value={theme ?? "system"} onValueChange={setTheme}>
              <DropdownMenuRadioItem value="light">
                <Sun className="size-4" /> 라이트
              </DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="dark">
                <Moon className="size-4" /> 다크
              </DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="system">
                <Monitor className="size-4" /> 시스템 설정
              </DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
            <DropdownMenuSeparator />
            {auth.data?.access_code_required && (
            <DropdownMenuGroup>
              <DropdownMenuItem
                onSelect={async () => {
                  await client.POST("/api/auth/logout");
                  window.location.assign("/login/");
                }}
              >
                <LogOut className="size-4" /> 로그아웃
              </DropdownMenuItem>
            </DropdownMenuGroup>
            )}
            <DropdownMenuSeparator />
            <div className="px-2 py-1.5 text-caption text-subtle-foreground">
              v{me?.app_version} · 계산 {me?.calc_version}
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
