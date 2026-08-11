import * as React from "react";
import { Link } from "@/components/ui/link";
import { BarChart3, CircleAlert, CircleCheck, ListChecks, Users } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useMembers,
  useMyPermissions,
  useWorkspace,
  useWorkspaceTasks,
  useWorkspaceTree,
} from "@/hooks/queries";
import { can } from "@/lib/permissions";
import { initials, PRIORITY_META } from "@/lib/format";
import {
  COMMON,
  DASHBOARD,
  PRIORITY_ORDER,
  STATUS_COLOR,
  STATUS_LABEL,
  STATUS_ORDER,
} from "@/i18n/uz";
import { cn } from "@/lib/utils";
import type { Priority, TaskStatus, WorkspaceTree } from "@/types/api";

interface SpaceIndex {
  /** listId → {spaceId, spaceName, spaceColor} */
  listToSpace: Map<string, { id: string; name: string; color: string }>;
  openBySpace: Map<string, { name: string; color: string; open: number }>;
}

function indexTree(tree: WorkspaceTree | undefined): SpaceIndex {
  const listToSpace = new Map<string, { id: string; name: string; color: string }>();
  const openBySpace = new Map<string, { name: string; color: string; open: number }>();
  for (const space of tree?.spaces ?? []) {
    const meta = { id: space.id, name: space.name, color: space.color || "#7B68EE" };
    let open = 0;
    for (const list of [...space.lists, ...space.folders.flatMap((f) => f.lists)]) {
      listToSpace.set(list.id, meta);
      open += list.open_task_count;
    }
    openBySpace.set(space.id, { name: space.name, color: meta.color, open });
  }
  return { listToSpace, openBySpace };
}

/**
 * «Tahlil» — ish maydonining raqamli kesimi.
 *
 * Bosh sahifadan farqi: u shaxsiy ish stoli («menga nima tegishli»), bu esa
 * jamoaviy holat («ish qayerda to'planib qolgan»). Ikkalasi ham AYNAN bir
 * kesh yozuvlaridan o'qiydi (`useWorkspaceTasks` / `useWorkspaceTree`), ya'ni
 * bu sahifa bitta ham qo'shimcha so'rov qo'shmaydi.
 *
 * Barcha raqamlar chaqiruvchining ko'rish doirasidagi ma'lumotdan: server
 * ko'rinmaydigan bo'limlarni allaqachon kesib tashlagan.
 */
export function DashboardView({ workspaceId }: { workspaceId: string }) {
  const { data: workspace } = useWorkspace(workspaceId);
  const { data: myPermissions } = useMyPermissions(workspaceId);
  const canReadTasks = can(myPermissions, "task.read");
  const canReadMembers = can(myPermissions, "member.read");

  const tasks = useWorkspaceTasks(workspaceId, canReadTasks);
  const { data: tree } = useWorkspaceTree(workspaceId);
  const members = useMembers(workspaceId);

  const rows = React.useMemo(() => tasks.data?.results ?? [], [tasks.data]);
  const index = React.useMemo(() => indexTree(tree), [tree]);

  const open = React.useMemo(() => rows.filter((t) => !t.completed_at), [rows]);
  const completed = rows.length - open.length;
  const now = new Date();
  const overdue = open.filter((t) => t.due_date && new Date(t.due_date) < now).length;

  /**
   * Holat — vazifaning o'zida kelgan kod, ustunlar esa qat'iy to'rtta.
   * Tartib `STATUS_ORDER` bo'yicha (miqdor bo'yicha emas): doskadagi ustunlar
   * bilan bir xil o'qilsin, va bo'sh holat ham ko'rinib tursin.
   */
  const byStatus = React.useMemo(() => {
    const counts = new Map<TaskStatus, number>();
    for (const task of open) counts.set(task.status, (counts.get(task.status) ?? 0) + 1);
    return STATUS_ORDER.map((status) => ({
      status,
      name: STATUS_LABEL[status],
      color: STATUS_COLOR[status],
      count: counts.get(status) ?? 0,
    }));
  }, [open]);

  const byPriority = React.useMemo(() => {
    const counts = new Map<Priority, number>();
    for (const task of open) counts.set(task.priority, (counts.get(task.priority) ?? 0) + 1);
    return counts;
  }, [open]);

  const bySpace = React.useMemo(() => {
    const counts = new Map<string, { name: string; color: string; count: number }>();
    for (const task of open) {
      const space = index.listToSpace.get(task.list_id);
      if (!space) continue;
      const entry = counts.get(space.id) ?? {
        name: space.name,
        color: space.color,
        count: 0,
      };
      entry.count += 1;
      counts.set(space.id, entry);
    }
    return [...counts.values()].sort((a, b) => b.count - a.count);
  }, [open, index]);

  const byMember = React.useMemo(() => {
    const counts = new Map<string, number>();
    let unassigned = 0;
    for (const task of open) {
      if (task.assignees.length === 0) {
        unassigned += 1;
        continue;
      }
      for (const assignee of task.assignees) {
        counts.set(assignee.id, (counts.get(assignee.id) ?? 0) + 1);
      }
    }
    return { counts, unassigned };
  }, [open]);

  if (!canReadTasks) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-12 text-center">
        <BarChart3 className="size-6 text-muted-foreground" />
        <p className="text-sm font-medium">{DASHBOARD.deniedTitle}</p>
        <p className="max-w-sm text-sm text-muted-foreground">{DASHBOARD.deniedHint}</p>
      </div>
    );
  }

  const partial = !!tasks.data && tasks.data.count > rows.length;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl space-y-6 p-6 lg:p-8">
        <header>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <BarChart3 className="size-5 text-primary" />
            {DASHBOARD.title}
          </h1>
          <p className="text-sm text-muted-foreground">
            {workspace?.name ?? COMMON.workspaceFallback} {DASHBOARD.subtitleSuffix}
            {partial ? DASHBOARD.partialSuffix : ""}
          </p>
        </header>

        {tasks.isPending ? (
          <DashboardSkeleton />
        ) : tasks.isError ? (
          <div className="flex flex-col items-start gap-2 rounded-lg border p-4">
            <p className="text-sm text-danger">{DASHBOARD.loadFailed}</p>
            <Button variant="outline" size="sm" onClick={() => tasks.refetch()}>
              {COMMON.retry}
            </Button>
          </div>
        ) : (
          <>
            <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat icon={ListChecks} label={DASHBOARD.statOpen} value={open.length} />
              <Stat
                icon={CircleAlert}
                label={DASHBOARD.statOverdue}
                value={overdue}
                tone="text-danger"
              />
              <Stat icon={CircleCheck} label={DASHBOARD.statCompleted} value={completed} />
              <Stat
                icon={Users}
                label={DASHBOARD.statMembers}
                value={workspace?.member_count ?? members.data?.count ?? 0}
              />
            </section>

            <div className="grid gap-4 lg:grid-cols-2">
              <Panel title={DASHBOARD.panelStatus} empty={open.length === 0}>
                {byStatus.map((row) => (
                  <BarRow
                    key={row.status}
                    label={row.name}
                    color={row.color}
                    count={row.count}
                    total={open.length}
                  />
                ))}
              </Panel>

              <Panel title={DASHBOARD.panelPriority} empty={open.length === 0}>
                {PRIORITY_ORDER.filter((p) => (byPriority.get(p) ?? 0) > 0)
                  .map((priority) => (
                    <BarRow
                      key={priority}
                      label={PRIORITY_META[priority].label}
                      className={PRIORITY_META[priority].className}
                      count={byPriority.get(priority) ?? 0}
                      total={open.length}
                    />
                  ))}
              </Panel>

              <Panel title={DASHBOARD.panelSpaces} empty={bySpace.length === 0}>
                {bySpace.map((row) => (
                  <BarRow
                    key={row.name}
                    label={row.name}
                    color={row.color}
                    count={row.count}
                    total={open.length}
                  />
                ))}
              </Panel>

              {canReadMembers ? (
                <Panel
                  title={DASHBOARD.panelTeam}
                  empty={(members.data?.results ?? []).length === 0}
                >
                  {(members.data?.results ?? [])
                    .map((member) => ({
                      member,
                      count: byMember.counts.get(member.user.id) ?? 0,
                    }))
                    .sort((a, b) => b.count - a.count)
                    .map(({ member, count }) => (
                      <Link
                        key={member.id}
                        href={`/w/${workspaceId}/u/${member.user.id}`}
                        className="flex items-center gap-2.5 rounded-md px-1 py-1.5 hover:bg-muted/60"
                      >
                        <Avatar className="size-6 shrink-0">
                          {member.user.avatar ? (
                            <AvatarImage src={member.user.avatar} alt="" />
                          ) : null}
                          <AvatarFallback
                            className="text-[10px] font-semibold text-primary-foreground"
                            style={{
                              backgroundColor: member.user.avatar_color || "#7B68EE",
                            }}
                          >
                            {initials(member.user.full_name, member.user.email ?? undefined)}
                          </AvatarFallback>
                        </Avatar>
                        <span className="min-w-0 flex-1 truncate text-sm">
                          {member.user.full_name || member.user.email}
                        </span>
                        <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                          {count} ta
                        </span>
                      </Link>
                    ))}
                  {byMember.unassigned > 0 ? (
                    <p className="px-1 pt-1 text-xs text-muted-foreground">
                      Biriktirilmagan: {byMember.unassigned} ta
                    </p>
                  ) : null}
                </Panel>
              ) : null}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
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
    </div>
  );
}

function Panel({
  title,
  empty,
  children,
}: {
  title: string;
  empty: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border p-4">
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {empty ? (
        <p className="py-4 text-center text-sm text-muted-foreground">
          {DASHBOARD.panelEmpty}
        </p>
      ) : (
        <div className="space-y-1.5">{children}</div>
      )}
    </section>
  );
}

/** Bitta qator: yorliq, nisbat chizig'i va son. */
function BarRow({
  label,
  count,
  total,
  color,
  className,
}: {
  label: string;
  count: number;
  total: number;
  color?: string;
  className?: string;
}) {
  const percent = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        aria-hidden
        className={cn("size-2 shrink-0 rounded-full", !color && "bg-current", className)}
        style={color ? { backgroundColor: color } : undefined}
      />
      <span className="w-32 shrink-0 truncate text-[13px]">{label}</span>
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <span
          className="block h-full rounded-full bg-primary"
          style={{ width: `${percent}%` }}
        />
      </span>
      <span className="w-12 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
        {count} ta
      </span>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-4" aria-hidden>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-48 w-full" />
        ))}
      </div>
    </div>
  );
}
