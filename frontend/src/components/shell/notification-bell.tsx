import * as React from "react";
import { Link } from "@/components/ui/link";
import { useNavigate } from "react-router";
import {
  Bell,
  CheckCheck,
  ListChecks,
  MailCheck,
  ShieldCheck,
  UserMinus,
  UserPlus,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useNotifications, useUnreadNotificationCount } from "@/hooks/queries";
import { useMarkAllNotificationsRead, useMarkNotificationRead } from "@/hooks/mutations";
import { COMMON, NOTIFICATIONS } from "@/i18n/uz";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AppNotification, NotificationKind } from "@/types/api";

/** Menyuda ko'rsatiladigan eng ko'p qator — qolgani alohida sahifada. */
const MENU_LIMIT = 8;

const KIND_ICON: Record<NotificationKind, React.ComponentType<{ className?: string }>> = {
  member_added: UserPlus,
  member_joined: Users,
  member_removed: UserMinus,
  role_changed: ShieldCheck,
  invitation_accepted: MailCheck,
  task_assigned: ListChecks,
};

/**
 * Tur bo'yicha ikonka. Komponent sifatida (funksiya emas): `const Icon =
 * pick(kind)` shakli render paytida komponent yaratadi va `react-hooks`
 * qoidasi uni to'g'ri belgilaydi — bunday qiymat har renderda yangi bo'lib
 * ko'rinadi. Noma'lum `kind` uchun qo'ng'iroqcha: server lug'ati klientdan
 * oldinda bo'lishi mumkin va u holda ham qator chizilishi shart.
 */
export function NotificationIcon({
  kind,
  className,
}: {
  kind: NotificationKind;
  className?: string;
}) {
  const Icon = KIND_ICON[kind] ?? Bell;
  return <Icon className={className} />;
}

export function NotificationBell({ workspaceId }: { workspaceId: string }) {
  const navigate = useNavigate();
  const [open, setOpen] = React.useState(false);
  const unread = useUnreadNotificationCount(workspaceId);
  // Ro'yxat menyu ochilgandagina so'raladi; nishon esa doim ekranda va
  // arzon `unread-count/` dan oziqlanadi.
  const list = useNotifications(workspaceId, open);
  const markRead = useMarkNotificationRead(workspaceId);
  const markAll = useMarkAllNotificationsRead(workspaceId);

  const count = unread.data?.count ?? 0;
  const rows = (list.data?.results ?? []).slice(0, MENU_LIMIT);

  const openNotification = (notification: AppNotification) => {
    setOpen(false);
    if (!notification.is_read) markRead.mutate(notification.id);
    if (notification.url) navigate(notification.url);
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            className="relative"
            aria-label={
              count > 0 ? NOTIFICATIONS.bellAriaUnread(count) : NOTIFICATIONS.bellAria
            }
          />
        }
      >
        <Bell />
        {count > 0 ? (
          // `aria-hidden`: son tugmaning nomida allaqachon o'qiladi, aks holda
          // skrinrider uni ikki marta aytadi.
          <span
            aria-hidden
            className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] leading-none font-semibold text-white tabular-nums"
          >
            {count > 99 ? "99+" : count}
          </span>
        ) : null}
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-90 p-0">
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-sm font-semibold">{NOTIFICATIONS.title}</span>
          {count > 0 ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 text-xs"
              disabled={markAll.isPending}
              onClick={() => markAll.mutate()}
            >
              <CheckCheck className="size-3.5" />
              {NOTIFICATIONS.markAllRead}
            </Button>
          ) : null}
        </div>

        <div className="max-h-96 overflow-y-auto">
          {list.isPending ? (
            <div className="flex flex-col gap-2 p-3" aria-hidden>
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : list.isError ? (
            <div className="flex flex-col items-start gap-2 p-4">
              <p className="text-sm text-danger">{NOTIFICATIONS.loadFailed}</p>
              <Button variant="outline" size="sm" onClick={() => list.refetch()}>
                {COMMON.retry}
              </Button>
            </div>
          ) : rows.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">
              {NOTIFICATIONS.empty}
            </p>
          ) : (
            <ul>
              {rows.map((notification) => (
                <li key={notification.id}>
                  <NotificationRow
                    notification={notification}
                    onOpen={() => openNotification(notification)}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="border-t p-1">
          <Link
            href={`/w/${workspaceId}/notifications`}
            onClick={() => setOpen(false)}
            className="block rounded-md px-3 py-1.5 text-center text-xs font-medium text-primary hover:bg-muted"
          >
            {NOTIFICATIONS.seeAll}
          </Link>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * Bitta qator. Menyu ichida `DropdownMenuItem` EMAS oddiy tugma: element ikki
 * qatorli va o'z ichida ikonka + vaqt tutadi, menyu elementi esa bir qatorli
 * `flex` tartibga majburlaydi.
 */
function NotificationRow({
  notification,
  onOpen,
}: {
  notification: AppNotification;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "flex w-full items-start gap-2.5 px-3 py-2.5 text-left hover:bg-muted",
        !notification.is_read && "bg-primary/5",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full",
          notification.is_read
            ? "bg-muted text-muted-foreground"
            : "bg-primary/15 text-primary",
        )}
      >
        <NotificationIcon kind={notification.kind} className="size-3.5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-medium">
          {notification.title}
        </span>
        {notification.body ? (
          <span className="mt-0.5 block truncate text-xs text-muted-foreground">
            {notification.body}
          </span>
        ) : null}
        <span className="mt-0.5 block text-[11px] text-muted-foreground">
          {timeAgo(notification.created_at)}
        </span>
      </span>
      {!notification.is_read ? (
        <span
          aria-label={NOTIFICATIONS.unreadDot}
          className="mt-2 size-2 shrink-0 rounded-full bg-primary"
        />
      ) : null}
    </button>
  );
}
