import * as React from "react";
import { Link } from "@/components/ui/link";
import { useLocation, useNavigate } from "react-router";
import {
  BarChart3,
  Bell,
  CalendarDays,
  Grid3x3,
  House,
  MessageSquare,
  Search,
  Settings,
  Sparkles,
  UserRound,
  Users,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useWorkspaces } from "@/hooks/queries";
import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";

interface RailItem {
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  href: (workspaceId: string) => string;
  /** Faol holat: aynan shu yo'l (`exact`) yoki shu prefiks bilan boshlanishi. */
  exact?: boolean;
}

/**
 * Chap reyk — ilovaning eng yuqori darajadagi navigatsiyasi.
 *
 * Yon paneldan (BO'LIMLAR daraxti) farqi shundaki, bu yerda **rejim**
 * tanlanadi: bosh sahifa, rejalashtirish, yordamchi, jamoa, tahlil. Daraxt
 * esa tanlangan rejim ichidagi kontent. Shu sababli reyk yon panel
 * yig'ilganda ham ko'rinib turadi — u ilovaning ramkasi.
 */
const ITEMS: RailItem[] = [
  {
    key: "home",
    label: "Bosh sahifa",
    icon: House,
    href: (w) => `/w/${w}`,
    exact: true,
  },
  {
    key: "planner",
    label: "Rejalar",
    icon: CalendarDays,
    href: (w) => `/w/${w}/planner`,
  },
  { key: "ai", label: "AI", icon: Sparkles, href: (w) => `/w/${w}/ai` },
  {
    key: "teams",
    label: "Jamoa",
    icon: Users,
    href: (w) => `/w/${w}/settings/members`,
  },
  {
    key: "dashboard",
    label: "Tahlil",
    icon: BarChart3,
    href: (w) => `/w/${w}/dashboard`,
  },
];

export function NavRail({ workspaceId }: { workspaceId: string }) {
  const { pathname } = useLocation();

  return (
    <nav
      aria-label="Asosiy navigatsiya"
      className="flex w-16 shrink-0 flex-col items-center gap-1 border-r border-rail-border bg-rail py-2"
    >
      <WorkspaceBadge workspaceId={workspaceId} />
      {ITEMS.map((item) => {
        const href = item.href(workspaceId);
        const active = item.exact ? pathname === href : pathname.startsWith(href);
        return (
          <RailLink key={item.key} href={href} label={item.label} active={active}>
            <item.icon className="size-5" />
          </RailLink>
        );
      })}
      <MoreMenu workspaceId={workspaceId} />
    </nav>
  );
}

/** Ish maydoni nishoni — reykning tepasida, bosh sahifaga havola. */
function WorkspaceBadge({ workspaceId }: { workspaceId: string }) {
  const { data } = useWorkspaces();
  const current = data?.results.find((w) => w.id === workspaceId);
  const name = current?.name ?? "Ish maydoni";

  return (
    <Link
      href={`/w/${workspaceId}`}
      title={name}
      aria-label={`${name} — bosh sahifa`}
      className="mb-1 flex size-9 items-center justify-center rounded-lg text-xs font-bold text-white ring-1 ring-white/10"
      style={{ backgroundColor: current?.color || "#7B68EE" }}
    >
      {initials(name)}
    </Link>
  );
}

function RailLink({
  href,
  label,
  active,
  children,
}: {
  href: string;
  label: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex w-14 flex-col items-center gap-0.5 rounded-lg px-1 py-1.5 text-[10px] leading-tight font-medium transition-colors",
        active
          ? "bg-rail-hover text-rail-active"
          : "text-rail-foreground hover:bg-rail-hover hover:text-rail-active",
      )}
    >
      {children}
      <span className="w-full truncate text-center">{label}</span>
    </Link>
  );
}

/**
 * «Yana» — reykka sig'magan, lekin kamroq ishlatiladigan yo'llar.
 * Ular yo'qolib qolmasligi uchun bitta ro'yxatga yig'ilgan (chat, qidiruv,
 * bildirishnomalar, sozlamalar, profil).
 */
function MoreMenu({ workspaceId }: { workspaceId: string }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const items = [
    { href: `/w/${workspaceId}/chat`, label: "Chat", icon: MessageSquare },
    { href: `/w/${workspaceId}/search`, label: "Qidiruv", icon: Search },
    {
      href: `/w/${workspaceId}/notifications`,
      label: "Bildirishnomalar",
      icon: Bell,
    },
    { href: `/w/${workspaceId}/settings`, label: "Ish maydoni sozlamalari", icon: Settings },
    { href: "/settings/profile", label: "Profil", icon: UserRound },
  ];
  const active = items.some((item) => pathname.startsWith(item.href));

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            aria-label="Yana"
            className={cn(
              "flex w-14 flex-col items-center gap-0.5 rounded-lg px-1 py-1.5 text-[10px] leading-tight font-medium transition-colors",
              active
                ? "bg-rail-hover text-rail-active"
                : "text-rail-foreground hover:bg-rail-hover hover:text-rail-active",
            )}
          />
        }
      >
        <Grid3x3 className="size-5" />
        <span>Yana</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="right" className="w-56">
        <DropdownMenuLabel>Yana</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {/* `navigate()`, `render={<Link/>}` emas — `TopBar` dagi hisob
            menyusi bilan bir xil sabab: MenuItem `<div>` chizadi, unga
            `<a>` ni joylash navigatsiyani menyu yopilishiga bog'lab
            qo'yadi. */}
        {items.map((item) => (
          <DropdownMenuItem key={item.href} onClick={() => navigate(item.href)}>
            <item.icon className="size-4" />
            {item.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
