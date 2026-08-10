"use client";

import * as React from "react";
import Link from "next/link";
import { format } from "date-fns";
import { uz } from "date-fns/locale";
import {
  ArrowLeft,
  ArrowRightLeft,
  CalendarClock,
  CalendarDays,
  CircleAlert,
  CircleCheck,
  CircleDot,
  Paperclip,
  Flag,
  FolderOpen,
  ListChecks,
  MessageSquare,
  Pencil,
  Plus,
  RotateCcw,
  Trash2,
  UserMinus,
  UserPlus,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TaskRow } from "@/components/shared/task-row";
import {
  useMe,
  useMemberProfile,
  useMemberTasks,
  useMyPermissions,
  useStatusesByListIds,
  useWorkspaceActivity,
  useWorkspaceTree,
} from "@/hooks/queries";
import { displayName, formatDueDate, initials, PRIORITY_META, timeAgo } from "@/lib/format";
import { can } from "@/lib/permissions";
import { PROFESSION_LABEL, ROLE_LABEL } from "@/lib/roles";
import { BUCKET_LABEL, BUCKET_ORDER, groupByDue } from "@/lib/task-buckets";
import { cn } from "@/lib/utils";
import type { ActivityVerb, Priority, WorkspaceActivity } from "@/types/api";

type ProfileTab = "tasks" | "activity" | "spaces";

// ---------------------------------------------------------------------------
// Activity vocabulary (§10.6 verbs → Uzbek sentences)
// ---------------------------------------------------------------------------

const VERB_ICON: Record<
  ActivityVerb,
  { icon: React.ComponentType<{ className?: string }>; tone?: string }
> = {
  created: { icon: Plus, tone: "text-brand-green" },
  status_changed: { icon: CircleDot },
  assignee_added: { icon: UserPlus },
  assignee_removed: { icon: UserMinus },
  priority_changed: { icon: Flag },
  due_date_changed: { icon: CalendarClock },
  renamed: { icon: Pencil },
  moved: { icon: ArrowRightLeft },
  completed: { icon: CircleCheck, tone: "text-brand-green" },
  deleted: { icon: Trash2, tone: "text-danger" },
  restored: { icon: RotateCcw },
  attachment_added: { icon: Paperclip },
  attachment_removed: { icon: Trash2, tone: "text-danger" },
};

/** Priority is stored as the English enum value; show the Uzbek label. */
function priorityLabel(value: string | null): string {
  if (!value) return "yo'q";
  const meta = PRIORITY_META[value as Priority];
  return meta ? meta.label.toLowerCase() : value;
}

function dateLabel(iso: string | null): string {
  if (!iso) return "muddatsiz";
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime()) ? iso : formatDueDate(iso);
}

/**
 * One activity row as an Uzbek sentence. The subject is deliberately implicit
 * — this feed is always filtered to one member, so "«X» vazifasini yaratdi"
 * reads correctly under their own profile header.
 */
function activitySentence(row: WorkspaceActivity, title: React.ReactNode): React.ReactNode {
  const quoted = <>«{title}»</>;
  switch (row.verb) {
    case "created":
      return <>{quoted} vazifasini yaratdi</>;
    case "status_changed":
      return (
        <>
          {quoted} vazifasini <strong className="font-medium">{row.to_value}</strong> ga
          o&apos;tkazdi
        </>
      );
    case "completed":
      return <>{quoted} vazifasini bajardi</>;
    case "assignee_added":
      return (
        <>
          {quoted} vazifasini <strong className="font-medium">{row.to_value}</strong> ga
          biriktirdi
        </>
      );
    case "assignee_removed":
      return (
        <>
          {quoted} vazifasidan <strong className="font-medium">{row.from_value}</strong>{" "}
          ni olib tashladi
        </>
      );
    case "priority_changed":
      return (
        <>
          {quoted} muhimligini{" "}
          <strong className="font-medium">{priorityLabel(row.to_value)}</strong> qildi
        </>
      );
    case "due_date_changed":
      return (
        <>
          {quoted} muddatini{" "}
          <strong className="font-medium">{dateLabel(row.to_value)}</strong> ga
          o&apos;zgartirdi
        </>
      );
    case "renamed":
      return (
        <>
          {quoted} vazifasining nomini o&apos;zgartirdi
          {row.from_value ? (
            <span className="text-muted-foreground"> (avval «{row.from_value}»)</span>
          ) : null}
        </>
      );
    case "moved":
      return (
        <>
          {quoted} vazifasini <strong className="font-medium">{row.to_value}</strong>{" "}
          ro&apos;yxatiga ko&apos;chirdi
        </>
      );
    case "deleted":
      return <>{quoted} vazifasini o&apos;chirdi</>;
    case "attachment_added":
      return (
        <>
          {quoted} vazifasiga <strong className="font-medium">{row.to_value}</strong>{" "}
          faylini biriktirdi
        </>
      );
    case "attachment_removed":
      return (
        <>
          {quoted} vazifasidan <strong className="font-medium">{row.from_value}</strong>{" "}
          faylini o&apos;chirdi
        </>
      );
    case "restored":
      return <>{quoted} vazifasini tikladi</>;
    default:
      return <>{quoted} vazifasini yangiladi</>;
  }
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function MemberProfile({
  workspaceId,
  userId,
}: {
  workspaceId: string;
  userId: string;
}) {
  const { data: me } = useMe();
  const permissions = useMyPermissions(workspaceId);
  const myPermissions = permissions.data;
  const canReadMembers = can(myPermissions, "member.read");
  const canReadTasks = can(myPermissions, "task.read");

  const profile = useMemberProfile(workspaceId, userId, canReadMembers);
  const [tab, setTab] = React.useState<ProfileTab>("tasks");

  // Ruxsat javobi kelmaguncha skeleton; ruxsat yo'q bo'lsa profil so'rovi
  // umuman yubormaydi, shuning uchun `isPending` dan OLDIN tekshiriladi —
  // aks holda skeleton abadiy qotib qolardi.
  if (permissions.isPending) return <ProfileSkeleton />;

  // 500, uzilgan tarmoq yoki tugagan retry byudjeti: `data` abadiy `undefined`
  // qoladi. Skeletonda qotib qolmaslik uchun xato holati va qayta urinish.
  if (permissions.isError || !myPermissions) {
    return (
      <ProfileMessage
        workspaceId={workspaceId}
        title="Profilni yuklab bo'lmadi."
        hint="Aloqada muammo bo'lishi mumkin. Qayta urinib ko'ring."
        onRetry={() => permissions.refetch()}
      />
    );
  }

  if (!canReadMembers) {
    return (
      <ProfileMessage
        workspaceId={workspaceId}
        title="Jamoa a'zolarini ko'rish uchun ruxsatingiz yo'q."
        hint="Ish maydoni administratoridan «A'zolarni ko'rish» huquqini so'rang."
      />
    );
  }

  if (profile.isPending) return <ProfileSkeleton />;

  if (profile.isError || !profile.data) {
    return (
      <ProfileMessage
        workspaceId={workspaceId}
        title="Bunday a'zo topilmadi."
        hint="Foydalanuvchi ish maydonidan chiqarilgan bo'lishi mumkin."
      />
    );
  }

  const { user, role, joined_at, last_active_at, stats, spaces } = profile.data;
  // Mehmonga email `null` keladi (§4) — ism har doim to'ldirilgan.
  const name = displayName(user);
  const isMe = me?.id === user.id;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl space-y-8 p-6 lg:p-8">
        <Button
          variant="ghost"
          size="sm"
          className="-ml-2 text-muted-foreground"
          nativeButton={false}
          render={<Link href={`/w/${workspaceId}`} />}
        >
          <ArrowLeft className="size-4" />
          Bosh sahifa
        </Button>

        <header className="flex flex-wrap items-start gap-4">
          <Avatar className="size-16 shrink-0">
            {user.avatar ? <AvatarImage src={user.avatar} alt="" /> : null}
            <AvatarFallback
              className="text-lg font-semibold text-primary-foreground"
              style={{ backgroundColor: user.avatar_color || "#7B68EE" }}
            >
              {initials(user.full_name, user.email ?? undefined)}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <h1 className="flex flex-wrap items-center gap-2 text-xl font-semibold">
              {name}
              {isMe ? (
                <span className="text-sm font-normal text-muted-foreground">(siz)</span>
              ) : null}
              <Badge variant="secondary" className="font-normal">
                {ROLE_LABEL[role]}
              </Badge>
              {user.profession ? (
                <Badge variant="outline" className="font-normal">
                  {PROFESSION_LABEL[user.profession]}
                </Badge>
              ) : null}
            </h1>
            {/* Mehmon ko'ruvchiga email `null` keladi — bo'sh qator chizmaymiz. */}
            {user.email ? (
              <p className="truncate text-sm text-muted-foreground">{user.email}</p>
            ) : null}
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
              <span>
                Qo&apos;shilgan:{" "}
                {format(new Date(joined_at), "d MMMM yyyy", { locale: uz })}
              </span>
              <span aria-hidden>·</span>
              <span>
                Oxirgi faollik:{" "}
                {last_active_at ? timeAgo(last_active_at) : "ma'lumot yo'q"}
              </span>
            </p>
          </div>
        </header>

        <section
          className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
          aria-label="A'zo statistikasi"
        >
          <StatCard
            icon={ListChecks}
            label="Ochiq vazifalar"
            hint="Biriktirilgan"
            value={stats.open_tasks}
          />
          <StatCard
            icon={CircleAlert}
            label="Muddati o'tgan"
            hint="Kechikkan ishlar"
            tone="text-danger"
            value={stats.overdue_tasks}
          />
          <StatCard
            icon={CalendarDays}
            label="Bugun"
            hint="Bugun tugaydi"
            value={stats.due_today}
          />
          <StatCard
            icon={CircleCheck}
            label="Bajarilgan"
            hint="Yopilgan vazifalar"
            value={stats.completed_tasks}
          />
        </section>

        <p className="-mt-4 text-xs text-muted-foreground">
          Yaratgan vazifalari: {stats.created_tasks} ta · Izohlari: {stats.comments} ta
          <MessageSquare className="ml-1 inline size-3" aria-hidden />
        </p>

        <div className="space-y-3">
          <Tabs value={tab} onValueChange={(value) => setTab(value as ProfileTab)}>
            <TabsList>
              <TabsTrigger value="tasks">Vazifalar</TabsTrigger>
              <TabsTrigger value="activity">Faoliyat</TabsTrigger>
              <TabsTrigger value="spaces">Bo&apos;limlar</TabsTrigger>
            </TabsList>
          </Tabs>

          {tab === "tasks" ? (
            <TasksTab
              workspaceId={workspaceId}
              userId={userId}
              name={name}
              canRead={canReadTasks}
            />
          ) : tab === "activity" ? (
            <ActivityTab
              workspaceId={workspaceId}
              userId={userId}
              name={name}
              canRead={canReadTasks}
            />
          ) : (
            <SpacesTab workspaceId={workspaceId} spaces={spaces} name={name} />
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

function TasksTab({
  workspaceId,
  userId,
  name,
  canRead,
}: {
  workspaceId: string;
  userId: string;
  name: string;
  canRead: boolean;
}) {
  const tasks = useMemberTasks(workspaceId, userId, canRead);
  const open = React.useMemo(
    () => (tasks.data?.results ?? []).filter((t) => !t.completed_at),
    [tasks.data],
  );
  const buckets = React.useMemo(() => groupByDue(open), [open]);
  const listIds = React.useMemo(
    () => Array.from(new Set(open.map((t) => t.list_id))),
    [open],
  );
  const { statusById } = useStatusesByListIds(listIds);
  const tree = useWorkspaceTree(workspaceId);
  const listNames = React.useMemo(() => {
    const names = new Map<string, string>();
    for (const space of tree.data?.spaces ?? []) {
      for (const list of [...space.lists, ...space.folders.flatMap((f) => f.lists)]) {
        names.set(list.id, list.name);
      }
    }
    return names;
  }, [tree.data]);

  if (!canRead) {
    return <EmptyBox title="Vazifalarni ko'rish uchun ruxsatingiz yo'q." />;
  }
  if (tasks.isPending) return <RowsSkeleton />;
  if (tasks.isError) {
    return (
      <ErrorBox message="Vazifalarni yuklab bo'lmadi." onRetry={() => tasks.refetch()} />
    );
  }
  if (open.length === 0) {
    return (
      <EmptyBox
        title={`${name} uchun ochiq vazifa yo'q.`}
        hint="Yopilgan vazifalar bu ro'yxatda ko'rsatilmaydi."
      />
    );
  }

  return (
    <section aria-label="A'zo vazifalari" className="space-y-5">
      {BUCKET_ORDER.filter((key) => buckets[key].length > 0).map((key) => (
        <div key={key}>
          <div className="mb-1.5 flex items-center gap-2">
            <span
              className={cn(
                "text-xs font-semibold tracking-wide uppercase",
                key === "overdue" ? "text-danger" : "text-muted-foreground",
              )}
            >
              {BUCKET_LABEL[key]}
            </span>
            <span className="text-xs text-muted-foreground">{buckets[key].length}</span>
          </div>
          <div className="overflow-hidden rounded-lg border">
            {buckets[key].map((task) => (
              <TaskRow
                key={task.id}
                workspaceId={workspaceId}
                task={task}
                status={statusById.get(task.status_id)}
                listName={listNames.get(task.list_id)}
                overdue={key === "overdue"}
              />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

function ActivityTab({
  workspaceId,
  userId,
  name,
  canRead,
}: {
  workspaceId: string;
  userId: string;
  name: string;
  canRead: boolean;
}) {
  const feed = useWorkspaceActivity(workspaceId, userId, canRead);

  if (!canRead) {
    return <EmptyBox title="Faoliyatni ko'rish uchun ruxsatingiz yo'q." />;
  }
  if (feed.isPending) return <RowsSkeleton />;
  if (feed.isError) {
    return (
      <ErrorBox message="Faoliyat tasmasini yuklab bo'lmadi." onRetry={() => feed.refetch()} />
    );
  }

  const rows = feed.data?.results ?? [];
  if (rows.length === 0) {
    return (
      <EmptyBox
        title={`${name} hali hech narsa qilmagan.`}
        hint="Vazifa yaratilishi, holati o'zgarishi yoki biriktirilishi shu yerda ko'rinadi."
      />
    );
  }

  return (
    <section aria-label="A'zo faoliyati">
      <ol className="overflow-hidden rounded-lg border">
        {rows.map((row) => {
          const meta = VERB_ICON[row.verb] ?? { icon: CircleDot };
          const Icon = meta.icon;
          return (
            <li
              key={row.id}
              className="flex items-start gap-3 border-b px-3 py-2.5 last:border-b-0"
            >
              <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-muted">
                <Icon className={cn("size-3.5 text-muted-foreground", meta.tone)} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm">
                  {activitySentence(
                    row,
                    <Link
                      href={`/w/${workspaceId}/l/${row.task.list_id}?task=${row.task.id}`}
                      className="font-medium hover:underline"
                    >
                      {row.task.title}
                    </Link>,
                  )}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {row.task.list_name} · {timeAgo(row.created_at)}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
      {feed.data && feed.data.count > rows.length ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Oxirgi {rows.length} ta yozuv ko&apos;rsatildi (jami {feed.data.count} ta).
        </p>
      ) : null}
    </section>
  );
}

function SpacesTab({
  workspaceId,
  spaces,
  name,
}: {
  workspaceId: string;
  spaces: { id: string; name: string; color: string; open_tasks: number }[];
  name: string;
}) {
  const ordered = React.useMemo(
    () => [...spaces].sort((a, b) => b.open_tasks - a.open_tasks),
    [spaces],
  );
  const tree = useWorkspaceTree(workspaceId);
  const firstListOf = React.useMemo(() => {
    const map = new Map<string, string>();
    for (const space of tree.data?.spaces ?? []) {
      const first = space.lists[0] ?? space.folders.flatMap((f) => f.lists)[0];
      if (first) map.set(space.id, first.id);
    }
    return map;
  }, [tree.data]);

  if (ordered.length === 0) {
    return (
      <EmptyBox
        title="Sizga ko'rinadigan bo'lim yo'q."
        hint="Yopiq bo'limlar bu ro'yxatga kirmaydi."
      />
    );
  }

  return (
    <section aria-label="A'zo bo'limlari" className="grid gap-2 sm:grid-cols-2">
      {ordered.map((space) => {
        const listId = firstListOf.get(space.id);
        const body = (
          <>
            <span
              className="size-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: space.color || "#7B68EE" }}
              aria-hidden
            />
            <FolderOpen className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <span className="min-w-0 flex-1 truncate text-sm font-medium">
              {space.name}
            </span>
            <span
              className="shrink-0 text-xs text-muted-foreground tabular-nums"
              title={`${name}ning ochiq vazifalari`}
            >
              {space.open_tasks} ta
            </span>
          </>
        );
        return listId ? (
          <Link
            key={space.id}
            href={`/w/${workspaceId}/l/${listId}`}
            className="flex items-center gap-2.5 rounded-lg border p-3 transition-colors hover:bg-muted/40"
          >
            {body}
          </Link>
        ) : (
          <div
            key={space.id}
            className="flex items-center gap-2.5 rounded-lg border p-3"
          >
            {body}
          </div>
        );
      })}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Shared bits
// ---------------------------------------------------------------------------

function StatCard({
  icon: Icon,
  label,
  hint,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  hint: string;
  value: number;
  tone?: string;
}) {
  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Icon className={cn("size-4", tone)} />
        {label}
      </div>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function EmptyBox({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-lg border p-8 text-center">
      <p className="text-sm font-medium">{title}</p>
      {hint ? (
        <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

function ErrorBox({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-lg border p-4">
      <p className="text-sm text-danger">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Qayta urinish
      </Button>
    </div>
  );
}

function ProfileMessage({
  workspaceId,
  title,
  hint,
  onRetry,
}: {
  workspaceId: string;
  title: string;
  hint: string;
  /** Berilsa — xato holati: qaytadan so'rash tugmasi ham chiqadi. */
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-16 text-center">
      <h1 className="text-lg font-semibold">{title}</h1>
      <p className="max-w-sm text-sm text-muted-foreground">{hint}</p>
      <div className="mt-2 flex flex-wrap justify-center gap-2">
        {onRetry ? (
          <Button size="sm" onClick={onRetry}>
            Qayta urinish
          </Button>
        ) : null}
        <Button
          variant="outline"
          size="sm"
          nativeButton={false}
          render={<Link href={`/w/${workspaceId}`} />}
        >
          Bosh sahifaga qaytish
        </Button>
      </div>
    </div>
  );
}

function RowsSkeleton() {
  return (
    <div className="space-y-2" aria-hidden>
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-11 w-full" />
      ))}
    </div>
  );
}

function ProfileSkeleton() {
  return (
    <div className="flex-1 overflow-hidden" aria-hidden>
      <div className="mx-auto w-full max-w-5xl space-y-8 p-6 lg:p-8">
        <div className="flex items-center gap-4">
          <Skeleton className="size-16 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-11 w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}
