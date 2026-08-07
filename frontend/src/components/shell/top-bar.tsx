"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Check,
  ChevronDown,
  LogOut,
  Menu,
  Moon,
  Search,
  Settings,
  Sun,
  User as UserIcon,
  Users,
} from "lucide-react";
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
import { useMe, useMembers, useWorkspaces } from "@/hooks/queries";
import { useLogout } from "@/hooks/use-logout";
import { initials } from "@/lib/format";
import { ROLE_LABEL } from "@/lib/roles";

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
      <MemberStack workspaceId={workspaceId} />
      <ThemeToggle />
      <UserMenu />
    </header>
  );
}

/** Overlapping avatars of the workspace roster (max 4 + "+N"). */
function MemberStack({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const { data } = useMembers(workspaceId);
  const members = data?.results ?? [];
  if (members.length === 0) return null;

  const shown = members.slice(0, 4);
  const extra = members.length - shown.length;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="sm"
            className="hidden gap-0 px-1.5 sm:flex"
            aria-label={`Jamoa a'zolari (${members.length})`}
          />
        }
      >
        <span className="flex items-center -space-x-1.5">
          {shown.map((member) => (
            <Avatar key={member.id} className="size-6 ring-2 ring-card">
              {member.user.avatar ? <AvatarImage src={member.user.avatar} alt="" /> : null}
              <AvatarFallback
                className="text-[10px] font-semibold text-primary-foreground"
                style={{ backgroundColor: member.user.avatar_color || "#7B68EE" }}
              >
                {initials(member.user.full_name, member.user.email)}
              </AvatarFallback>
            </Avatar>
          ))}
          {extra > 0 ? (
            <span className="flex size-6 items-center justify-center rounded-full bg-muted text-[10px] text-muted-foreground ring-2 ring-card">
              +{extra}
            </span>
          ) : null}
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>Jamoa a&apos;zolari ({members.length})</DropdownMenuLabel>
        {members.slice(0, 10).map((member) => (
          <DropdownMenuItem
            key={member.id}
            onClick={() => router.push(`/w/${workspaceId}/settings`)}
          >
            <Avatar className="size-5">
              {member.user.avatar ? <AvatarImage src={member.user.avatar} alt="" /> : null}
              <AvatarFallback
                className="text-[9px] font-semibold text-primary-foreground"
                style={{ backgroundColor: member.user.avatar_color || "#7B68EE" }}
              >
                {initials(member.user.full_name, member.user.email)}
              </AvatarFallback>
            </Avatar>
            <span className="truncate">{member.user.full_name || member.user.email}</span>
            <span className="ml-auto text-xs text-muted-foreground">
              {ROLE_LABEL[member.role]}
            </span>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => router.push(`/w/${workspaceId}/settings`)}>
          <Users className="size-4" />
          Barcha a&apos;zolar
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
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
  const { data: me } = useMe();
  const onLogout = useLogout();

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
