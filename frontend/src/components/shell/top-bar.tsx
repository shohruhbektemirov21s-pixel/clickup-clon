"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check, ChevronDown, LogOut, Menu, Moon, Search, Settings, Sun, User as UserIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useMe, useWorkspaces } from "@/hooks/queries";
import { logout } from "@/lib/auth";
import { initials } from "@/lib/format";

export function TopBar({
  workspaceId,
  onToggleSidebar,
}: {
  workspaceId: string;
  onToggleSidebar: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = React.useState("");

  const onSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (q.length >= 2) {
      router.push(`/w/${workspaceId}/search?q=${encodeURIComponent(q)}`);
    }
  };

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-card px-3">
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={onToggleSidebar}
        aria-label="Yon panelni ochish/yopish"
      >
        <Menu />
      </Button>
      <WorkspaceSwitcher workspaceId={workspaceId} />
      <form onSubmit={onSearchSubmit} className="mx-auto w-full max-w-md">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Qidirish..."
            className="h-8 pl-8"
            aria-label="Qidirish"
          />
        </div>
      </form>
      <ThemeToggle />
      <UserMenu />
    </header>
  );
}

function WorkspaceSwitcher({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const { data } = useWorkspaces();
  const workspaces = data?.results ?? [];
  const current = workspaces.find((w) => w.id === workspaceId);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="ghost" size="sm" className="max-w-56 gap-1.5 font-semibold" />
        }
      >
        <span
          className="flex size-5 shrink-0 items-center justify-center rounded-sm text-[10px] font-bold text-primary-foreground"
          style={{ backgroundColor: current?.color || "#7B68EE" }}
        >
          {initials(current?.name ?? "W")}
        </span>
        <span className="truncate">{current?.name ?? "Ish maydoni"}</span>
        <ChevronDown className="size-3.5 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel>Ish maydonlari</DropdownMenuLabel>
        {workspaces.map((w) => (
          <DropdownMenuItem key={w.id} onClick={() => router.push(`/w/${w.id}`)}>
            <span
              className="flex size-5 items-center justify-center rounded-sm text-[10px] font-bold text-primary-foreground"
              style={{ backgroundColor: w.color || "#7B68EE" }}
            >
              {initials(w.name)}
            </span>
            <span className="truncate">{w.name}</span>
            {w.id === workspaceId ? <Check className="ml-auto size-4" /> : null}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => router.push(`/w/${workspaceId}/settings`)}
        >
          <Settings className="size-4" />
          Ish maydoni sozlamalari
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label="Mavzuni almashtirish"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    >
      {/* CSS-driven so SSR markup never mismatches the client theme */}
      <Sun className="hidden dark:block" />
      <Moon className="dark:hidden" />
    </Button>
  );
}

function UserMenu() {
  const router = useRouter();
  const { data: me } = useMe();

  const onLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={<Button variant="ghost" size="icon-sm" aria-label="Hisob menyusi" />}
      >
        <Avatar className="size-7">
          {me?.avatar ? <AvatarImage src={me.avatar} alt="" /> : null}
          <AvatarFallback
            className="text-xs font-semibold text-primary-foreground"
            style={{ backgroundColor: me?.avatar_color || "#7B68EE" }}
          >
            {initials(me?.full_name, me?.email)}
          </AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="flex flex-col">
          <span className="font-medium">{me?.full_name || me?.email}</span>
          <span className="text-xs font-normal text-muted-foreground">{me?.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem render={<Link href="/settings/profile" />}>
          <UserIcon className="size-4" />
          Profil
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={onLogout}>
          <LogOut className="size-4" />
          Chiqish
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
