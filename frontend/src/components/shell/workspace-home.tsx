"use client";

import * as React from "react";
import Link from "next/link";
import { ListFilter, CalendarDays, CircleAlert, ListChecks, Plus, Users, X } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useMe,
  useMembers,
  useMyPermissions,
  useMyTasks,
  useStatusesByListIds,
  useWorkspace,
  useWorkspaceTasks,
  useWorkspaceTree,
} from "@/hooks/queries";
import { useWorkspaceChannel } from "@/hooks/use-workspace-channel";
import type { WorkspaceConnectionStatus } from "@/hooks/use-workspace-channel";
import { CreateEntityDialog } from "@/components/shell/create-entity-dialog";
import { TaskRow } from "@/components/shared/task-row";
import { initials } from "@/lib/format";
import { can } from "@/lib/permissions";
import { ROLE_LABEL } from "@/lib/roles";
import {
  BUCKET_LABEL,
  BUCKET_ORDER,
  byDueDate,
  groupByDue,
  type BucketKey,
} from "@/lib/task-buckets";
import { cn } from "@/lib/utils";
import type { Member, Task, UserSummary, WorkspaceTree } from "@/types/api";

// ---------------------------------------------------------------------------
// Tree helpers
// ---------------------------------------------------------------------------

interface TreeSummary {
  /** listId → list name, for the "which list" column. */
  listNames: Map<string, string>;
  openTaskCount: number;
  spaceCount: number;
  firstSpaceId: string | null;
  /** Target of the "create a task" CTAs — tasks are always created in a list. */
  firstListId: string | null;
}

function summarizeTree(tree: WorkspaceTree | undefined): TreeSummary {
  const listNames = new Map<string, string>();
  let openTaskCount = 0;
  let firstListId: string | null = null;
  for (const space of tree?.spaces ?? []) {
    const lists = [...space.lists, ...space.folders.flatMap((f) => f.lists)];
    for (const list of lists) {
      listNames.set(list.id, list.name);
      openTaskCount += list.open_task_count;
      if (!firstListId) firstListId = list.id;
    }
  }
  return {
    listNames,
    openTaskCount,
    spaceCount: tree?.spaces.length ?? 0,
    firstSpaceId: tree?.spaces[0]?.id ?? null,
    firstListId,
  };
}

// ---------------------------------------------------------------------------
// Team grouping
// ---------------------------------------------------------------------------

const UNASSIGNED = "__unassigned__";

interface AssigneeGroup {
  key: string;
  user: UserSummary | null;
  role: Member["role"] | null;
  tasks: Task[];
}

/**
 * One workspace-wide response → one group per assignee. A task with several
 * assignees appears under each of them (that is what "kimga biriktirilgan"
 * means on a shared task); unassigned work gets its own bucket. Members are
 * looked up from the already-cached member list, so no request per row.
 */
function groupByAssignee(tasks: Task[], members: Member[]): AssigneeGroup[] {
  const roleByUser = new Map(members.map((m) => [m.user.id, m.role]));
  const groups = new Map<string, AssigneeGroup>();

  for (const task of tasks) {
    if (task.assignees.length === 0) {
      const group = groups.get(UNASSIGNED) ?? {
        key: UNASSIGNED,
        user: null,
        role: null,
        tasks: [],
      };
      group.tasks.push(task);
      groups.set(UNASSIGNED, group);
      continue;
    }
    for (const assignee of task.assignees) {
      const group = groups.get(assignee.id) ?? {
        key: assignee.id,
        user: assignee,
        role: roleByUser.get(assignee.id) ?? null,
        tasks: [],
      };
      group.tasks.push(task);
      groups.set(assignee.id, group);
    }
  }

  const ordered = [...groups.values()];
  for (const group of ordered) group.tasks.sort(byDueDate);
  ordered.sort((a, b) => {
    if (a.key === UNASSIGNED) return 1;
    if (b.key === UNASSIGNED) return -1;
    if (a.tasks.length !== b.tasks.length) return b.tasks.length - a.tasks.length;
    const an = a.user?.full_name || a.user?.email || "";
    const bn = b.user?.full_name || b.user?.email || "";
    return an.localeCompare(bn);
  });
  return ordered;
}

// ---------------------------------------------------------------------------
// Workspace home (dashboard)
// ---------------------------------------------------------------------------

type HomeView = "mine" | "team";

export function WorkspaceHome({ workspaceId }: { workspaceId: string }) {
  const { data: workspace } = useWorkspace(workspaceId);
  const { data: me } = useMe();
  const { data: myPermissions } = useMyPermissions(workspaceId);
  const {
    data: tree,
    isPending: treePending,
    isError: treeError,
    refetch: refetchTree,
  } = useWorkspaceTree(workspaceId);
  const myTasks = useMyTasks(workspaceId);

  // `task.read` is held by every role by default, but the tab is still gated
  // on the effective matrix — a workspace may have revoked it for a role.
  const canReadTasks = can(myPermissions, "task.read");
  // Single workspace-wide page shared by the team tab AND the member counters.
  const teamTasks = useWorkspaceTasks(workspaceId, canReadTasks);

  // Live workspace channel: task.* / list.updated / permission.updated.
  const connection = useWorkspaceChannel(workspaceId);

  const [view, setView] = React.useState<HomeView>("mine");
  const [assigneeFilter, setAssigneeFilter] = React.useState<string | null>(null);
  const tasksRef = React.useRef<HTMLDivElement | null>(null);

  const summary = React.useMemo(() => summarizeTree(tree), [tree]);

  const openMyTasks = React.useMemo(
    () => (myTasks.data?.results ?? []).filter((t) => !t.completed_at),
    [myTasks.data],
  );
  const buckets = React.useMemo(() => groupByDue(openMyTasks), [openMyTasks]);

  const openTeamTasks = React.useMemo(
    () => (teamTasks.data?.results ?? []).filter((t) => !t.completed_at),
    [teamTasks.data],
  );

  const isGuest = workspace?.my_role === "guest";

  const showMember = React.useCallback((userId: string) => {
    setView("team");
    setAssigneeFilter((current) => (current === userId ? null : userId));
    requestAnimationFrame(() =>
      tasksRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
  }, []);

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
        <header className="flex items-start gap-3">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold">
              {firstName ? `Salom, ${firstName}!` : "Salom!"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {workspace?.name ?? "Ish maydoni"} — kunlik ko&apos;rinish
            </p>
          </div>
          <LiveBadge status={connection} />
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

        <div ref={tasksRef} className="space-y-3">
          <Tabs
            value={view}
            onValueChange={(value) => setView(value as HomeView)}
          >
            <TabsList>
              <TabsTrigger value="mine">Mening vazifalarim</TabsTrigger>
              {canReadTasks ? (
                <TabsTrigger value="team">Jamoa vazifalari</TabsTrigger>
              ) : null}
            </TabsList>
          </Tabs>

          {view === "team" && canReadTasks ? (
            <TeamTasksSection
              workspaceId={workspaceId}
              tasks={openTeamTasks}
              listNames={summary.listNames}
              meId={me?.id ?? null}
              filterUserId={assigneeFilter}
              onClearFilter={() => setAssigneeFilter(null)}
              onShowMine={() => setView("mine")}
              firstListId={summary.firstListId}
              isPending={teamTasks.isPending}
              isError={teamTasks.isError}
              onRetry={() => teamTasks.refetch()}
            />
          ) : (
            <MyTasksSection
              workspaceId={workspaceId}
              buckets={buckets}
              tasks={openMyTasks}
              listNames={summary.listNames}
              firstListId={summary.firstListId}
              canSeeTeam={canReadTasks}
              onShowTeam={() => setView("team")}
              isPending={myTasks.isPending}
              isError={myTasks.isError}
              onRetry={() => myTasks.refetch()}
            />
          )}
        </div>

        {workspace && !isGuest ? (
          <TeamSection
            workspaceId={workspaceId}
            meId={me?.id ?? null}
            tasks={openTeamTasks}
            // Without `task.read` the workspace-wide read never runs — hide the
            // counters rather than showing a misleading "0 ta" for everyone.
            tasksPending={!canReadTasks || teamTasks.isPending}
            partial={
              !!teamTasks.data &&
              teamTasks.data.count > teamTasks.data.results.length
            }
            selectedUserId={assigneeFilter}
            onSelectMember={showMember}
          />
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Realtime badge
// ---------------------------------------------------------------------------

function LiveBadge({ status }: { status: WorkspaceConnectionStatus }) {
  return (
    <Badge
      variant="secondary"
      className="ml-auto shrink-0 gap-1.5 font-normal text-muted-foreground"
      title={`Real vaqt holati: ${status}`}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          status === "live" && "bg-brand-green",
          status === "connecting" && "animate-pulse bg-brand-yellow",
          status === "offline" && "bg-danger",
        )}
      />
      {status === "live" ? "Jonli" : status === "offline" ? "Oflayn" : "Ulanmoqda…"}
    </Badge>
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
  firstListId,
  canSeeTeam,
  onShowTeam,
  isPending,
  isError,
  onRetry,
}: {
  workspaceId: string;
  buckets: Record<BucketKey, Task[]>;
  tasks: Task[];
  listNames: Map<string, string>;
  firstListId: string | null;
  canSeeTeam: boolean;
  onShowTeam: () => void;
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
      {/* The visible label is the tab; the section still needs its own heading. */}
      <h2 className="sr-only">Mening vazifalarim</h2>
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
        <div className="rounded-lg border p-8 text-center">
          <p className="text-sm font-medium">
            Sizga biriktirilgan ochiq vazifa yo&apos;q.
          </p>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
            Ro&apos;yxatdan o&apos;zingizga vazifa biriktiring — u shu yerda
            darhol paydo bo&apos;ladi.
          </p>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            {firstListId ? (
              <Button
                size="sm"
                nativeButton={false}
                render={<Link href={`/w/${workspaceId}/l/${firstListId}`} />}
              >
                <Plus className="size-4" />
                Vazifa yaratish
              </Button>
            ) : null}
            {canSeeTeam ? (
              <Button size="sm" variant="outline" onClick={onShowTeam}>
                Jamoa vazifalarini ko&apos;rish
              </Button>
            ) : null}
          </div>
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

// ---------------------------------------------------------------------------
// Team tasks (grouped by assignee)
// ---------------------------------------------------------------------------

function TeamTasksSection({
  workspaceId,
  tasks,
  listNames,
  meId,
  filterUserId,
  onClearFilter,
  onShowMine,
  firstListId,
  isPending,
  isError,
  onRetry,
}: {
  workspaceId: string;
  tasks: Task[];
  listNames: Map<string, string>;
  meId: string | null;
  filterUserId: string | null;
  onClearFilter: () => void;
  onShowMine: () => void;
  firstListId: string | null;
  isPending: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  // Same cache entry the team grid reads — no second request.
  const members = useMembers(workspaceId);
  const listIds = React.useMemo(
    () => Array.from(new Set(tasks.map((t) => t.list_id))),
    [tasks],
  );
  const { statusById } = useStatusesByListIds(listIds);

  const groups = React.useMemo(
    () => groupByAssignee(tasks, members.data?.results ?? []),
    [tasks, members.data],
  );
  const visible = filterUserId
    ? groups.filter((g) => g.key === filterUserId)
    : groups;

  const filteredMember = filterUserId
    ? members.data?.results.find((m) => m.user.id === filterUserId)
    : undefined;

  const now = new Date();

  return (
    <section aria-label="Jamoa vazifalari" className="space-y-3">
      <h2 className="sr-only">Jamoa vazifalari</h2>
      {filterUserId ? (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Filtr:</span>
          <Button
            variant="secondary"
            size="sm"
            className="h-7 gap-1.5"
            onClick={onClearFilter}
          >
            {filteredMember?.user.full_name ||
              filteredMember?.user.email ||
              "Tanlangan a'zo"}
            <X className="size-3.5" />
          </Button>
        </div>
      ) : null}

      {isPending ? (
        <div className="space-y-2" aria-hidden>
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-11 w-full" />
          ))}
        </div>
      ) : isError ? (
        <div className="flex flex-col items-start gap-2 rounded-lg border p-4">
          <p className="text-sm text-danger">
            Jamoa vazifalarini yuklab bo&apos;lmadi.
          </p>
          <Button variant="outline" size="sm" onClick={onRetry}>
            Qayta urinish
          </Button>
        </div>
      ) : tasks.length === 0 ? (
        <div className="rounded-lg border p-8 text-center">
          <p className="text-sm font-medium">
            Ish maydonida hali vazifa yo&apos;q — birinchisini yarating.
          </p>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
            Vazifa yaratilgach, u kim bajarayotganiga qarab shu yerda
            guruhlanadi.
          </p>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            {firstListId ? (
              <Button
                size="sm"
                nativeButton={false}
                render={<Link href={`/w/${workspaceId}/l/${firstListId}`} />}
              >
                <Plus className="size-4" />
                Birinchi vazifani yaratish
              </Button>
            ) : null}
            <Button size="sm" variant="outline" onClick={onShowMine}>
              Mening vazifalarim
            </Button>
          </div>
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-lg border p-6 text-center">
          <p className="text-sm font-medium">
            Bu a&apos;zoga biriktirilgan ochiq vazifa yo&apos;q.
          </p>
          <Button
            className="mt-3"
            size="sm"
            variant="outline"
            onClick={onClearFilter}
          >
            Filtrni tozalash
          </Button>
        </div>
      ) : (
        <div className="space-y-5">
          {visible.map((group) => (
            <div key={group.key}>
              <div className="mb-1.5 flex items-center gap-2">
                {group.user ? (
                  <Avatar className="size-6">
                    {group.user.avatar ? (
                      <AvatarImage src={group.user.avatar} alt="" />
                    ) : null}
                    <AvatarFallback
                      className="text-[10px] font-semibold text-primary-foreground"
                      style={{
                        backgroundColor: group.user.avatar_color || "#7B68EE",
                      }}
                    >
                      {initials(group.user.full_name, group.user.email ?? undefined)}
                    </AvatarFallback>
                  </Avatar>
                ) : (
                  <span className="flex size-6 items-center justify-center rounded-full border border-dashed text-[10px] text-muted-foreground">
                    ?
                  </span>
                )}
                <span className="truncate text-sm font-medium">
                  {group.user ? (
                    <Link
                      href={`/w/${workspaceId}/u/${group.user.id}`}
                      className="hover:underline"
                    >
                      {group.user.full_name || group.user.email}
                    </Link>
                  ) : (
                    "Biriktirilmagan"
                  )}
                  {group.user && group.user.id === meId ? (
                    <span className="ml-1 text-xs font-normal text-muted-foreground">
                      (siz)
                    </span>
                  ) : null}
                </span>
                {group.role ? (
                  <Badge variant="secondary" className="shrink-0 font-normal">
                    {ROLE_LABEL[group.role]}
                  </Badge>
                ) : null}
                <span className="text-xs text-muted-foreground tabular-nums">
                  {group.tasks.length} ta
                </span>
              </div>
              <div className="overflow-hidden rounded-lg border">
                {group.tasks.map((task) => (
                  <TaskRow
                    key={`${group.key}:${task.id}`}
                    workspaceId={workspaceId}
                    task={task}
                    status={statusById.get(task.status_id)}
                    listName={listNames.get(task.list_id)}
                    overdue={!!task.due_date && new Date(task.due_date) < now}
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

// ---------------------------------------------------------------------------
// Team
// ---------------------------------------------------------------------------

function TeamSection({
  workspaceId,
  meId,
  tasks,
  tasksPending,
  partial,
  selectedUserId,
  onSelectMember,
}: {
  workspaceId: string;
  meId: string | null;
  tasks: Task[];
  tasksPending: boolean;
  partial: boolean;
  selectedUserId: string | null;
  onSelectMember: (userId: string) => void;
}) {
  const members = useMembers(workspaceId);

  // Counts come from the one workspace-wide page the team tab already reads.
  const openByUser = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const task of tasks) {
      for (const assignee of task.assignees) {
        counts.set(assignee.id, (counts.get(assignee.id) ?? 0) + 1);
      }
    }
    return counts;
  }, [tasks]);

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
            const selected = selectedUserId === member.user.id;
            const name = member.user.full_name || member.user.email;
            return (
              // Kartaning o'zi profilga olib boradi ("stretched link"), filtr
              // esa alohida tugma bo'lib qoladi — bitta kartada ikkita
              // interaktiv element ichma-ich joylashmaydi.
              <div
                key={member.id}
                className={cn(
                  "relative flex items-center gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-muted/40",
                  selected && "border-primary bg-muted/40",
                )}
              >
                <Avatar className="size-8">
                  {member.user.avatar ? (
                    <AvatarImage src={member.user.avatar} alt="" />
                  ) : null}
                  <AvatarFallback
                    className="text-[11px] font-semibold text-primary-foreground"
                    style={{ backgroundColor: member.user.avatar_color || "#7B68EE" }}
                  >
                    {initials(member.user.full_name, member.user.email ?? undefined)}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    <Link
                      href={`/w/${workspaceId}/u/${member.user.id}`}
                      title={`${name} profilini ochish`}
                      className="after:absolute after:inset-0 hover:underline"
                    >
                      {name}
                    </Link>
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
                {tasksPending ? null : (
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
                <Button
                  variant="ghost"
                  size="icon-xs"
                  className="relative z-10 shrink-0"
                  aria-pressed={selected}
                  aria-label={`${name} vazifalarini shu yerda filtrlash`}
                  title="Vazifalarini shu sahifada filtrlash"
                  onClick={() => onSelectMember(member.user.id)}
                >
                  <ListFilter />
                </Button>
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
