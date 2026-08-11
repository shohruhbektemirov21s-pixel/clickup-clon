import * as React from "react";
import { Link } from "@/components/ui/link";
import { useLocation, useNavigate } from "react-router";
import {
  ArrowLeft,
  Check,
  LogOut,
  Menu,
  Moon,
  Search,
  Settings,
  Sun,
  User as UserIcon,
} from "lucide-react";
import { useTheme } from "next-themes";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuGroupLabel,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { NotificationBell } from "@/components/shell/notification-bell";
import { useMe, useWorkspaces } from "@/hooks/queries";
import { useLogout } from "@/hooks/use-logout";
import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";

export function TopBar({
  workspaceId,
  onToggleSidebar,
}: {
  workspaceId: string;
  onToggleSidebar: () => void;
}) {
  const navigate = useNavigate();
  const [query, setQuery] = React.useState("");

  const onSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (q.length >= 2) {
      navigate(`/w/${workspaceId}/search?q=${encodeURIComponent(q)}`);
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
      <BackButton workspaceId={workspaceId} />
      <WorkspaceHomeLink workspaceId={workspaceId} />
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
      <NotificationBell workspaceId={workspaceId} />
      <ThemeToggle />
      <AccountMenu workspaceId={workspaceId} />
    </header>
  );
}

/**
 * «Orqaga» — bir qadam ortga.
 *
 * Ish maydoni sahifasining O'ZIDA yashiriladi: u ilovaning ildizi, undan
 * ortga qaytish foydalanuvchini ilovadan tashqariga (landing yoki kirish
 * sahifasiga) otib yuborardi.
 *
 * `navigate(-1)` brauzer tarixiga tayanadi, tarix esa bo'sh bo'lishi mumkin
 * — masalan ro'yxat havolasi yangi ichki oynada ochilgan bo'lsa. Shuning
 * uchun tarix chuqurligi tekshiriladi va bo'lmasa ish maydoni bosh
 * sahifasiga qaytariladi, ya'ni tugma hech qachon "hech narsa qilmaydi"
 * holatida qolmaydi.
 */
function BackButton({ workspaceId }: { workspaceId: string }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  if (pathname === `/w/${workspaceId}`) return null;

  const goBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate(`/w/${workspaceId}`);
  };

  return (
    <Button variant="ghost" size="icon-sm" onClick={goBack} aria-label="Orqaga">
      <ArrowLeft />
    </Button>
  );
}

/**
 * Plain link, not a menu: workspace switching lives in the account menu, so a
 * second dropdown here would only duplicate it. Clicking goes to the workspace
 * home.
 */
function WorkspaceHomeLink({ workspaceId }: { workspaceId: string }) {
  const { data } = useWorkspaces();
  const current = data?.results.find((w) => w.id === workspaceId);
  const name = current?.name ?? "Ish maydoni";

  return (
    // A real <a>, styled like a ghost button: Base UI's Button would either
    // warn about the non-native element or stamp role="button" over the link.
    <Link
      href={`/w/${workspaceId}`}
      aria-label={`${name} — ish maydoni bosh sahifasi`}
      className={cn(
        buttonVariants({ variant: "ghost", size: "sm" }),
        "max-w-56 gap-1.5 font-semibold",
      )}
    >
      <span
        aria-hidden
        className="flex size-5 shrink-0 items-center justify-center rounded-sm text-[10px] font-bold text-primary-foreground"
        style={{ backgroundColor: current?.color || "#7B68EE" }}
      >
        {initials(name)}
      </span>
      <span className="truncate">{name}</span>
    </Link>
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

/**
 * The single menu of the shell: identity, profile, workspace settings, the
 * workspace switcher and logout. Everything the old workspace dropdown carried
 * now lives here, so nothing is offered twice.
 */
function AccountMenu({ workspaceId }: { workspaceId: string }) {
  const navigate = useNavigate();
  const { data: me } = useMe();
  const { data: workspacesPage } = useWorkspaces();
  const onLogout = useLogout();
  const workspaces = workspacesPage?.results ?? [];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          /* Name kept as "Hisob menyusi" — the E2E suite selects the trigger
             by this accessible name. */
          <Button variant="ghost" size="icon-sm" aria-label="Hisob menyusi" />
        }
      >
        <Avatar className="size-7">
          {me?.avatar ? <AvatarImage src={me.avatar} alt="" /> : null}
          <AvatarFallback
            className="text-xs font-semibold text-primary-foreground"
            style={{ backgroundColor: me?.avatar_color || "#7B68EE" }}
          >
            {initials(me?.full_name, me?.email ?? undefined)}
          </AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      {/* Cap the popup so a long workspace list scrolls instead of running off
          the viewport; the popup itself is the scroll container so arrow-key
          navigation still reaches every item. */}
      <DropdownMenuContent align="end" className="max-h-[70vh] w-64">
        {/* DropdownMenuLabel carries its own MenuPrimitive.Group — never wrap
            it in another DropdownMenuGroup or the groups nest. */}
        <DropdownMenuLabel className="flex items-center gap-2 py-1.5">
          <Avatar className="size-8 shrink-0">
            {me?.avatar ? <AvatarImage src={me.avatar} alt="" /> : null}
            <AvatarFallback
              className="text-xs font-semibold text-primary-foreground"
              style={{ backgroundColor: me?.avatar_color || "#7B68EE" }}
            >
              {initials(me?.full_name, me?.email ?? undefined)}
            </AvatarFallback>
          </Avatar>
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-medium text-foreground">
              {me?.full_name || me?.email}
            </span>
            <span className="truncate text-xs font-normal text-muted-foreground">
              {me?.email}
            </span>
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {/* navigate() rather than render={<Link/>}: a MenuItem renders a
            <div>, so composing an <a> into it relies on the anchor's native
            navigation surviving the menu close. An explicit push is
            unambiguous. */}
        <DropdownMenuItem onClick={() => navigate("/settings/profile")}>
          <UserIcon className="size-4" />
          Profil
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => navigate(`/w/${workspaceId}/settings`)}>
          <Settings className="size-4" />
          Ish maydoni sozlamalari
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuGroupLabel>Ish maydonlari</DropdownMenuGroupLabel>
          {workspaces.map((w) => {
            const isCurrent = w.id === workspaceId;
            return (
              <DropdownMenuItem
                key={w.id}
                aria-label={
                  isCurrent
                    ? `${w.name} — joriy ish maydoni`
                    : `${w.name} ish maydoniga o'tish`
                }
                onClick={() => navigate(`/w/${w.id}`)}
              >
                <span
                  aria-hidden
                  className="flex size-5 shrink-0 items-center justify-center rounded-sm text-[10px] font-bold text-primary-foreground"
                  style={{ backgroundColor: w.color || "#7B68EE" }}
                >
                  {initials(w.name)}
                </span>
                <span className="truncate">{w.name}</span>
                {isCurrent ? <Check className="ml-auto size-4" /> : null}
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={onLogout}>
          <LogOut className="size-4" />
          Chiqish
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
