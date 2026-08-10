"use client";

import * as React from "react";
import Link from "next/link";
import { endOfWeek, isToday } from "date-fns";
import {
  CalendarDays,
  CircleAlert,
  ListChecks,
  MessageSquare,
  Users,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useMe,
  useMembers,
  useMyTasks,
  useStatusesByListIds,
  useWorkspace,
  useWorkspaceTasks,
  useWorkspaceTree,
} from "@/hooks/queries";
import { CreateEntityDialog } from "@/components/shell/create-entity-dialog";
import { PriorityFlag, StatusDot } from "@/components/task/pickers";
import { formatDueDate, initials, PRIORITY_META } from "@/lib/format";
import { ROLE_LABEL } from "@/lib/roles";
import { cn } from "@/lib/utils";
import type { Status, Task, WorkspaceTree } from "@/types/api";

// ---------------------------------------------------------------------------
// Due-date buckets
// ---------------------------------------------------------------------------

type BucketKey = "overdue" | "today" | "week" | "later" | "none";

const BUCKET_ORDER: BucketKey[] = ["overdue", "today", "week", "later", "none"];

const BUCKET_LABEL: Record<BucketKey, string> = {
  overdue: "Muddati o'tgan",
  today: "Bugun",
  week: "Shu hafta",
  later: "Keyinroq",
  none: "Muddatsiz",
};

/**
 * Mirrors the server vocabulary (contract §10.5): `overdue` is `due_date < now`
 * on a non-closed task, `today`/`this_week` are calendar windows. Bucketing is
 * done here rather than with three `due=` requests because those windows
 * overlap — an overdue task is also inside `this_week`.
 */
function bucketOf(task: Task, now: Date, weekEnd: Date): BucketKey {
  if (!task.due_date) return "none";
  const due = new Date(task.due_date);
  if (due < now) return "overdue";
  if (isToday(due)) return "today";
  if (due <= weekEnd) return "week";
  return "later";
}

function groupByDue(tasks: Task[]): Record<BucketKey, Task[]> {
  const now = new Date();
  const weekEnd = endOfWeek(now, { weekStartsOn: 1 });
  const groups: Record<BucketKey, Task[]> = {
    overdue: [],
    today: [],
    week: [],
    later: [],
    none: [],
  };
  for (const task of tasks) groups[bucketOf(task, now, weekEnd)].push(task);
  return groups;
}

// ---------------------------------------------------------------------------
// Tree helpers
// ---------------------------------------------------------------------------

interface TreeSummary {
  /** listId → list name, for the "which list" column. */
  listNames: Map<string, string>;
  openTaskCount: number;
  spaceCount: number;
  firstSpaceId: string | null;
}

function summarizeTree(tree: WorkspaceTree | undefined): TreeSummary {
  const listNames = new Map<string, string>();
  let openTaskCount = 0;
  for (const space of tree?.spaces ?? []) {
    const lists = [...space.lists, ...space.folders.flatMap((f) => f.lists)];
    for (const list of lists) {
      listNames.set(list.id, list.name);
      openTaskCount += list.open_task_count;
    }
  }
  return {
    listNames,
    openTaskCount,
    spaceCount: tree?.spaces.length ?? 0,
    firstSpaceId: tree?.spaces[0]?.id ?? null,
  };
}

// ---------------------------------------------------------------------------
// Workspace home (dashboard)
// ---------------------------------------------------------------------------

export function WorkspaceHome({ workspaceId }: { workspaceId: string }) {
  const { data: workspace } = useWorkspace(workspaceId);
  const { data: me } = useMe();
  const {
    data: tree,
    isPending: treePending,
    isError: treeError,
    refetch: refetchTree,
  } = useWorkspaceTree(workspaceId);
  const myTasks = useMyTasks(workspaceId);

  const summary = React.useMemo(() => summarizeTree(tree), [tree]);

  const openMyTasks = React.useMemo(
    () => (myTasks.data?.results ?? []).filter((t) => !t.completed_at),
    [myTasks.data],
  );
  const buckets = React.useMemo(() => groupByDue(openMyTasks), [openMyTasks]);

  const isGuest = workspace?.my_role === "guest";

  if (treePending) return <HomeSkeleton />;

  if (treeError) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-12 text-center">
        <p className="text-sm text-muted-foreground">
          Ish maydonini yuklab bo&apos;lmadi.
        </p>
        <Button variant="outline" size="sm" onClick={() => refetchTree()}>
          Qayta urinish
        </Button>
      </div>
    );
  }

  if (summary.listNames.size === 0) {
    return (
      <EmptyWorkspace
        workspaceId={workspaceId}
        firstSpaceId={summary.spaceCount > 0 ? summary.firstSpaceId : null}
        canCreate={!isGuest}
      />
    );
  }

  const firstName = (me?.full_name || me?.email || "").split(/[\s@]/)[0];

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl space-y-8 p-6 lg:p-8">
        <header>
          <h1 className="text-xl font-semibold">
            {firstName ? `Salom, ${firstName}!` : "Salom!"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {workspace?.name ?? "Ish maydoni"} — kunlik ko&apos;rinish
          </p>
        </header>

        <section
          className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
          aria-label="Qisqa statistika"
        >
          <StatCard
            icon={ListChecks}
            label="Ochiq vazifalar"
            hint="Ish maydoni bo'yicha"
            value={summary.openTaskCount}
            pending={false}
          />
          <StatCard
            icon={CircleAlert}
            label="Muddati o'tgan"
            hint="Sizga biriktirilgan"
            tone="text-danger"
            value={buckets.overdue.length}
            pending={myTasks.isPending}
          />
          <StatCard
            icon={CalendarDays}
            label="Bugun"
            hint="Sizga biriktirilgan"
            value={buckets.today.length}
            pending={myTasks.isPending}
          />
          <StatCard
            icon={Users}
            label="Jamoa a'zolari"
            hint="Ish maydonida"
            value={workspace?.member_count}
            pending={!workspace}
          />
        </section>

        <MyTasksSection
          workspaceId={workspaceId}
          buckets={buckets}
          tasks={openMyTasks}
          listNames={summary.listNames}
          isPending={myTasks.isPending}
          isError={myTasks.isError}
          onRetry={() => myTasks.refetch()}
        />

        {workspace && !isGuest ? (
          <TeamSection workspaceId={workspaceId} meId={me?.id ?? null} />
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

function StatCard({
  icon: Icon,
  label,
  hint,
  value,
  pending,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  hint: string;
  value: number | undefined;
  pending: boolean;
  tone?: string;
}) {
  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Icon className={cn("size-4", tone)} />
        {label}
      </div>
      {pending || value === undefined ? (
        <Skeleton className="mt-2 h-8 w-12" />
      ) : (
        <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      )}
      <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// My tasks
// ---------------------------------------------------------------------------

function MyTasksSection({
  workspaceId,
  buckets,
  tasks,
  listNames,
  isPending,
  isError,
  onRetry,
}: {
  workspaceId: string;
  buckets: Record<BucketKey, Task[]>;
  tasks: Task[];
  listNames: Map<string, string>;
  isPending: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  // Tasks carry only `status_id`; resolve names/colors from the status sets of
  // the lists actually shown (cached and shared with the list pages).
  const listIds = React.useMemo(
    () => Array.from(new Set(tasks.map((t) => t.list_id))),
    [tasks],
  );
  const { statusById } = useStatusesByListIds(listIds);

  return (
    <section aria-label="Mening vazifalarim">
      <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground uppercase">
        Mening vazifalarim
      </h2>

      {isPending ? (
        <div className="space-y-2" aria-hidden>
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-11 w-full" />
          ))}
        </div>
      ) : isError ? (
        <div className="flex flex-col items-start gap-2 rounded-lg border p-4">
          <p className="text-sm text-danger">
            Vazifalaringizni yuklab bo&apos;lmadi.
          </p>
          <Button variant="outline" size="sm" onClick={onRetry}>
            Qayta urinish
          </Button>
        </div>
      ) : tasks.length === 0 ? (
        <div className="rounded-lg border p-6 text-center">
          <p className="text-sm font-medium">
            Sizga biriktirilgan ochiq vazifa yo&apos;q.
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Ro&apos;yxatlardan o&apos;zingizga vazifa biriktiring — u shu yerda
            paydo bo&apos;ladi.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
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
                <span className="text-xs text-muted-foreground">
                  {buckets[key].length}
                </span>
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
        </div>
      )}
    </section>
  );
}

function TaskRow({
  workspaceId,
  task,
  status,
  listName,
  overdue,
}: {
  workspaceId: string;
  task: Task;
  status?: Status;
  listName?: string;
  overdue: boolean;
}) {
  return (
    <Link
      href={`/w/${workspaceId}/l/${task.list_id}?task=${task.id}`}
      className="flex items-center gap-3 border-b px-3 py-2 last:border-b-0 hover:bg-muted/40"
    >
      <StatusDot status={status} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm">{task.title}</p>
        <p className="flex items-center gap-1.5 truncate text-xs text-muted-foreground">
          {status ? <span>{status.name}</span> : null}
          {status && listName ? <span aria-hidden>·</span> : null}
          {listName ? <span className="truncate">{listName}</span> : null}
          {task.comment_count > 0 ? (
            <span className="flex items-center gap-0.5">
              <MessageSquare className="size-3" />
              {task.comment_count}
            </span>
          ) : null}
        </p>
      </div>
      {task.priority !== "none" ? (
        <span
          className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground max-sm:hidden"
          title={PRIORITY_META[task.priority].label}
        >
          <PriorityFlag priority={task.priority} />
          {PRIORITY_META[task.priority].label}
        </span>
      ) : null}
      <span
        className={cn(
          "w-24 shrink-0 text-right text-xs",
          overdue ? "font-medium text-danger" : "text-muted-foreground",
        )}
      >
        {task.due_date ? formatDueDate(task.due_date) : "—"}
      </span>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Team
// ---------------------------------------------------------------------------

function TeamSection({
  workspaceId,
  meId,
}: {
  workspaceId: string;
  meId: string | null;
}) {
  const members = useMembers(workspaceId);
  const workspaceTasks = useWorkspaceTasks(workspaceId);

  // One workspace-wide task page → counts for every member (no request per row).
  const openByUser = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const task of workspaceTasks.data?.results ?? []) {
      if (task.completed_at) continue;
      for (const assignee of task.assignees) {
        counts.set(assignee.id, (counts.get(assignee.id) ?? 0) + 1);
      }
    }
    return counts;
  }, [workspaceTasks.data]);

  const partial =
    !!workspaceTasks.data &&
    workspaceTasks.data.count > workspaceTasks.data.results.length;

  return (
    <section aria-label="Jamoa">
      <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground uppercase">
        Jamoa {members.data ? `(${members.data.count})` : ""}
      </h2>

      {members.isPending ? (
        <div className="grid gap-2 sm:grid-cols-2" aria-hidden>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : members.isError ? (
        <div className="flex flex-col items-start gap-2 rounded-lg border p-4">
          <p className="text-sm text-danger">
            Jamoa a&apos;zolarini yuklab bo&apos;lmadi.
          </p>
          <Button variant="outline" size="sm" onClick={() => members.refetch()}>
            Qayta urinish
          </Button>
        </div>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          {(members.data?.results ?? []).map((member) => {
            const count = openByUser.get(member.user.id) ?? 0;
            return (
              <div
                key={member.id}
                className="flex items-center gap-3 rounded-lg border p-3"
              >
                <Avatar className="size-8">
                  {member.user.avatar ? (
                    <AvatarImage src={member.user.avatar} alt="" />
                  ) : null}
                  <AvatarFallback
                    className="text-[11px] font-semibold text-primary-foreground"
                    style={{ backgroundColor: member.user.avatar_color || "#7B68EE" }}
                  >
                    {initials(member.user.full_name, member.user.email)}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {member.user.full_name || member.user.email}
                    {member.user.id === meId ? (
                      <span className="ml-1 text-xs font-normal text-muted-foreground">
                        (siz)
                      </span>
                    ) : null}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {member.user.email}
                  </p>
                </div>
                {workspaceTasks.isPending ? null : (
                  <span
                    className="shrink-0 text-xs text-muted-foreground tabular-nums"
                    title={
                      partial
                        ? "Yuklangan vazifalar bo'yicha taxminiy hisob"
                        : "Ochiq vazifalar soni"
                    }
                  >
                    {partial ? "~" : ""}
                    {count} ta
                  </span>
                )}
                <Badge variant="secondary" className="shrink-0">
                  {ROLE_LABEL[member.role]}
                </Badge>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Empty / loading
// ---------------------------------------------------------------------------

function EmptyWorkspace({
  workspaceId,
  firstSpaceId,
  canCreate,
}: {
  workspaceId: string;
  firstSpaceId: string | null;
  canCreate: boolean;
}) {
  const [creating, setCreating] = React.useState(false);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-16 text-center">
      <h2 className="text-lg font-semibold">Ish maydoningizga xush kelibsiz</h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        Vazifa qo&apos;shishni boshlash uchun yon paneldan bo&apos;lim va
        ro&apos;yxat yarating.
      </p>
      {canCreate ? (
        <Button className="mt-2" onClick={() => setCreating(true)}>
          {firstSpaceId ? "Ro'yxat yaratish" : "Bo'lim yaratish"}
        </Button>
      ) : null}
      {creating ? (
        <CreateEntityDialog
          workspaceId={workspaceId}
          target={
            firstSpaceId
              ? { kind: "list", spaceId: firstSpaceId, folderId: null }
              : { kind: "space" }
          }
          onClose={() => setCreating(false)}
        />
      ) : null}
    </div>
  );
}

function HomeSkeleton() {
  return (
    <div className="flex-1 overflow-hidden" aria-hidden>
      <div className="mx-auto w-full max-w-5xl space-y-8 p-6 lg:p-8">
        <Skeleton className="h-8 w-56" />
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
