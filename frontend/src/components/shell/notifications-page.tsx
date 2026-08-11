import * as React from "react";
import { useNavigate } from "react-router";
import { Bell, CheckCheck } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NotificationIcon } from "@/components/shell/notification-bell";
import { useNotifications, useUnreadNotificationCount } from "@/hooks/queries";
import { useMarkAllNotificationsRead, useMarkNotificationRead } from "@/hooks/mutations";
import { COMMON, NOTIFICATIONS } from "@/i18n/uz";
import { initials, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AppNotification } from "@/types/api";

type Filter = "all" | "unread";

/**
 * `/w/{id}/notifications` — qo'ng'iroqcha menyusining to'liq ko'rinishi.
 *
 * Filtr KLIENTDA: menyu bilan bir xil kesh yozuvidan o'qiladi (`?unread=`
 * bilan alohida so'rov ikkinchi kesh kaliti va o'qilgan deb belgilaganda
 * qatorning ro'yxatdan sakrab yo'qolishini bergan bo'lardi).
 */
export function NotificationsPage({ workspaceId }: { workspaceId: string }) {
  const navigate = useNavigate();
  const [filter, setFilter] = React.useState<Filter>("all");
  const list = useNotifications(workspaceId);
  const unread = useUnreadNotificationCount(workspaceId);
  const markRead = useMarkNotificationRead(workspaceId);
  const markAll = useMarkAllNotificationsRead(workspaceId);

  const rows = list.data?.results ?? [];
  const visible = filter === "unread" ? rows.filter((n) => !n.is_read) : rows;
  const unreadCount = unread.data?.count ?? 0;

  const open = (notification: AppNotification) => {
    if (!notification.is_read) markRead.mutate(notification.id);
    if (notification.url) navigate(notification.url);
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-3xl space-y-5 p-6 lg:p-8">
        <header className="flex items-center gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-semibold">{NOTIFICATIONS.title}</h1>
            <p className="text-sm text-muted-foreground">
              {unreadCount > 0
                ? NOTIFICATIONS.unreadCount(unreadCount)
                : NOTIFICATIONS.allRead}
            </p>
          </div>
          {unreadCount > 0 ? (
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              disabled={markAll.isPending}
              onClick={() => markAll.mutate()}
            >
              <CheckCheck className="size-4" />
              {NOTIFICATIONS.markAllRead}
            </Button>
          ) : null}
        </header>

        <Tabs value={filter} onValueChange={(value) => setFilter(value as Filter)}>
          <TabsList>
            <TabsTrigger value="all">{NOTIFICATIONS.tabAll}</TabsTrigger>
            <TabsTrigger value="unread">{NOTIFICATIONS.tabUnread}</TabsTrigger>
          </TabsList>
        </Tabs>

        {list.isPending ? (
          <div className="space-y-2" aria-hidden>
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : list.isError ? (
          <div className="flex flex-col items-start gap-2 rounded-lg border p-4">
            <p className="text-sm text-danger">{NOTIFICATIONS.loadFailed}</p>
            <Button variant="outline" size="sm" onClick={() => list.refetch()}>
              {COMMON.retry}
            </Button>
          </div>
        ) : visible.length === 0 ? (
          <div className="rounded-lg border p-10 text-center">
            <Bell className="mx-auto size-6 text-muted-foreground" />
            <p className="mt-2 text-sm font-medium">
              {filter === "unread" ? NOTIFICATIONS.emptyUnread : NOTIFICATIONS.empty}
            </p>
            <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
              {NOTIFICATIONS.emptyHint}
            </p>
          </div>
        ) : (
          <ul className="overflow-hidden rounded-lg border">
            {visible.map((notification) => {
              return (
                <li key={notification.id} className="border-b last:border-b-0">
                  <button
                    type="button"
                    onClick={() => open(notification)}
                    className={cn(
                      "flex w-full items-start gap-3 p-3.5 text-left hover:bg-muted/60",
                      !notification.is_read && "bg-primary/5",
                    )}
                  >
                    <span
                      aria-hidden
                      className={cn(
                        "flex size-9 shrink-0 items-center justify-center rounded-full",
                        notification.is_read
                          ? "bg-muted text-muted-foreground"
                          : "bg-primary/15 text-primary",
                      )}
                    >
                      <NotificationIcon kind={notification.kind} className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">
                        {notification.title}
                      </span>
                      {notification.body ? (
                        <span className="mt-0.5 block text-sm text-muted-foreground">
                          {notification.body}
                        </span>
                      ) : null}
                      <span className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                        {notification.actor ? (
                          <>
                            <Avatar className="size-4">
                              {notification.actor.avatar ? (
                                <AvatarImage src={notification.actor.avatar} alt="" />
                              ) : null}
                              <AvatarFallback
                                className="text-[8px] font-semibold text-primary-foreground"
                                style={{
                                  backgroundColor:
                                    notification.actor.avatar_color || "#7B68EE",
                                }}
                              >
                                {initials(notification.actor.full_name)}
                              </AvatarFallback>
                            </Avatar>
                            {notification.actor.full_name || COMMON.someone}
                            <span aria-hidden>·</span>
                          </>
                        ) : null}
                        {timeAgo(notification.created_at)}
                      </span>
                    </span>
                    {!notification.is_read ? (
                      <span
                        aria-label={NOTIFICATIONS.unreadDot}
                        className="mt-1.5 size-2 shrink-0 rounded-full bg-primary"
                      />
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
