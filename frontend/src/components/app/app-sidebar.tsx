"use client";

import { ChevronsUpDown, LogOut, Monitor, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
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
import { client } from "@/lib/api";
import { NAV } from "@/lib/nav";
import { useWorkspace } from "@/lib/workspace";

import { Brand } from "./brand";

/** 필터(기간·센터 등)는 화면을 옮겨도 유지 */
const CARRY = ["start", "end", "warehouses", "regions", "carriers", "vehicles", "categories", "stores"];

export function AppSidebar() {
  const pathname = usePathname();
  const sp = useSearchParams();
  const carry = new URLSearchParams();
  sp.forEach((v, k) => CARRY.includes(k) && carry.append(k, v));
  const qs = carry.toString();

  return (
    <Sidebar collapsible="icon" variant="sidebar">
      <SidebarHeader className="h-14 justify-center border-b border-sidebar-border px-3">
        <Link href={`/control-tower/${qs ? `?${qs}` : ""}`} className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Brand />
        </Link>
      </SidebarHeader>
      <SidebarContent className="gap-0 py-2">
        {NAV.map((sec) => (
          <SidebarGroup key={sec.section} className="py-1.5">
            <SidebarGroupLabel className="h-7 text-[11px] font-medium tracking-wide text-subtle-foreground">
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
                      className="h-8 gap-2.5 text-[13px] font-medium data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground"
                    >
                      <Link href={`${it.href}${qs ? `?${qs}` : ""}`} aria-current={active ? "page" : undefined}>
                        <Icon className={active ? "text-primary" : "text-subtle-foreground"} />
                        <span className={it.ready ? "" : "text-subtle-foreground"}>{it.title}</span>
                      </Link>
                    </SidebarMenuButton>
                    {!it.ready && (
                      <SidebarMenuBadge className="rounded-sm border border-sidebar-border px-1 text-[10px] font-medium text-subtle-foreground">
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
  const { theme, setTheme } = useTheme();
  const initials = (me?.display_name ?? "?").slice(0, 1);
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent" aria-label="사용자 메뉴">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[13px] font-semibold text-primary">
                {initials}
              </span>
              <div className="grid flex-1 text-left leading-tight">
                <span className="truncate text-[13px] font-medium text-foreground">{me?.display_name ?? "—"}</span>
                <span className="truncate text-[11px] text-subtle-foreground">{me?.role_label ?? ""}</span>
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
            <DropdownMenuSeparator />
            <div className="px-2 py-1.5 text-[11px] text-subtle-foreground">
              v{me?.app_version} · 계산 {me?.calc_version}
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
