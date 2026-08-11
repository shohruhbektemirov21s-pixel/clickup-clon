import * as React from "react";
import { Link } from "@/components/ui/link";
import { addDays, format, isSameDay, startOfDay } from "date-fns";
import { uz } from "date-fns/locale";
import { CalendarDays, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TaskRow } from "@/components/shared/task-row";
import {
  useMyTasks,
  useWorkspaceTree,
} from "@/hooks/queries";
import {
  BUCKET_LABEL,
  BUCKET_ORDER,
  byDueDate,
  groupByDue,
} from "@/lib/task-buckets";
import { COMMON, PLANNER } from "@/i18n/uz";
import { cn } from "@/lib/utils";
import type { Task, WorkspaceTree } from "@/types/api";

/** Reykdagi «Rejalar» — 14 kunlik oyna. */
const HORIZON_DAYS = 14;

function listNamesOf(tree: WorkspaceTree | undefined): Map<string, string> {
  const names = new Map<string, string>();
  for (const space of tree?.spaces ?? []) {
    for (const list of [...space.lists, ...space.folders.flatMap((f) => f.lists)]) {
      names.set(list.id, list.name);
    }
  }
  return names;
}

/**
 * «Rejalar» — SIZGA biriktirilgan ochiq vazifalar, muddat bo'yicha.
 *
 * Bosh sahifadagi «Mening vazifalarim» bilan bir xil ma'lumot manbai
 * (`useMyTasks`), lekin boshqa savolga javob beradi: bosh sahifa "hozir
 * nima muhim" desa, bu yerda "qaysi kunga nima to'planib qolgan" ko'rinadi.
 * Shuning uchun tepada kunlar tasmasi, pastda esa tanlangan kunning (yoki
 * tanlov bo'lmasa — barcha muddat guruhlarining) ro'yxati turadi.
 */
export function PlannerView({ workspaceId }: { workspaceId: string }) {
  const myTasks = useMyTasks(workspaceId);
  const { data: tree } = useWorkspaceTree(workspaceId);
  const [selectedDay, setSelectedDay] = React.useState<Date | null>(null);

  const openTasks = React.useMemo(
    () => (myTasks.data?.results ?? []).filter((t) => !t.completed_at),
    [myTasks.data],
  );
  const buckets = React.useMemo(() => groupByDue(openTasks), [openTasks]);
  const listNames = React.useMemo(() => listNamesOf(tree), [tree]);


  const days = React.useMemo(() => {
    const today = startOfDay(new Date());
    return Array.from({ length: HORIZON_DAYS }, (_, i) => addDays(today, i));
  }, []);

  const countForDay = React.useCallback(
    (day: Date) =>
      openTasks.filter((t) => t.due_date && isSameDay(new Date(t.due_date), day))
        .length,
    [openTasks],
  );

  const selectedTasks = React.useMemo(() => {
    if (!selectedDay) return [];
    return openTasks
      .filter((t) => t.due_date && isSameDay(new Date(t.due_date), selectedDay))
      .sort(byDueDate);
  }, [openTasks, selectedDay]);

  const now = new Date();

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl space-y-6 p-6 lg:p-8">
        <header>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <CalendarDays className="size-5 text-primary" />
            {PLANNER.title}
          </h1>
          <p className="text-sm text-muted-foreground">{PLANNER.subtitle}</p>
        </header>

        {myTasks.isPending ? (
          <PlannerSkeleton />
        ) : myTasks.isError ? (
          <div className="flex flex-col items-start gap-2 rounded-lg border p-4">
            <p className="text-sm text-danger">{COMMON.tasksLoadFailed}</p>
            <Button variant="outline" size="sm" onClick={() => myTasks.refetch()}>
              {COMMON.retry}
            </Button>
          </div>
        ) : (
          <>
            <section aria-label={PLANNER.daysAria} className="overflow-x-auto">
              <div className="flex gap-2 pb-1">
                {days.map((day) => {
                  const count = countForDay(day);
                  const selected = !!selectedDay && isSameDay(day, selectedDay);
                  const isToday = isSameDay(day, now);
                  return (
                    <button
                      key={day.toISOString()}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => setSelectedDay(selected ? null : day)}
                      className={cn(
                        "flex w-16 shrink-0 flex-col items-center rounded-lg border p-2 transition-colors hover:bg-muted/60",
                        selected && "border-primary bg-primary/10",
                        isToday && !selected && "border-primary/40",
                      )}
                    >
                      <span className="text-[10px] tracking-wide text-muted-foreground uppercase">
                        {format(day, "EEEEEE", { locale: uz })}
                      </span>
                      <span className="text-lg leading-tight font-semibold tabular-nums">
                        {format(day, "d")}
                      </span>
                      <span
                        className={cn(
                          "mt-0.5 text-[11px] tabular-nums",
                          count > 0 ? "font-medium text-primary" : "text-muted-foreground",
                        )}
                      >
                        {count > 0 ? `${count} ta` : "—"}
                      </span>
                    </button>
                  );
                })}
              </div>
            </section>

            {selectedDay ? (
              <section className="space-y-2" aria-label="Tanlangan kun">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold">
                    {format(selectedDay, "d MMMM, EEEE", { locale: uz })}
                  </h2>
                  <span className="text-xs text-muted-foreground">
                    {selectedTasks.length} ta
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="ml-auto h-7 text-xs"
                    onClick={() => setSelectedDay(null)}
                  >
                    {PLANNER.allDates}
                  </Button>
                </div>
                {selectedTasks.length === 0 ? (
                  <p className="rounded-lg border p-6 text-center text-sm text-muted-foreground">
                    {PLANNER.dayEmpty}
                  </p>
                ) : (
                  <div className="overflow-hidden rounded-lg border">
                    {selectedTasks.map((task) => (
                      <TaskRow
                        key={task.id}
                        workspaceId={workspaceId}
                        task={task}
                        listName={listNames.get(task.list_id)}
                        overdue={!!task.due_date && new Date(task.due_date) < now}
                      />
                    ))}
                  </div>
                )}
              </section>
            ) : openTasks.length === 0 ? (
              <EmptyPlanner workspaceId={workspaceId} tree={tree} />
            ) : (
              <div className="space-y-5">
                {BUCKET_ORDER.filter((key) => buckets[key].length > 0).map((key) => (
                  <section key={key} aria-label={BUCKET_LABEL[key]}>
                    <div className="mb-1.5 flex items-center gap-2">
                      <span
                        className={cn(
                          "text-xs font-semibold tracking-wide uppercase",
                          key === "overdue" ? "text-danger" : "text-muted-foreground",
                        )}
                      >
                        {BUCKET_LABEL[key]}
                      </span>
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {buckets[key].length}
                      </span>
                    </div>
                    <div className="overflow-hidden rounded-lg border">
                      {[...buckets[key]].sort(byDueDate).map((task: Task) => (
                        <TaskRow
                          key={task.id}
                          workspaceId={workspaceId}
                          task={task}
                          listName={listNames.get(task.list_id)}
                          overdue={key === "overdue"}
                        />
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function EmptyPlanner({
  workspaceId,
  tree,
}: {
  workspaceId: string;
  tree: WorkspaceTree | undefined;
}) {
  const firstListId =
    tree?.spaces.flatMap((s) => [...s.lists, ...s.folders.flatMap((f) => f.lists)])[0]
      ?.id ?? null;

  return (
    <div className="rounded-lg border p-10 text-center">
      <CalendarDays className="mx-auto size-6 text-muted-foreground" />
      <p className="mt-2 text-sm font-medium">{PLANNER.emptyTitle}</p>
      <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
        {PLANNER.emptyHint}
      </p>
      {firstListId ? (
        <Button
          className="mt-4"
          size="sm"
          nativeButton={false}
          render={<Link href={`/w/${workspaceId}/l/${firstListId}`} />}
        >
          <Plus className="size-4" />
          {COMMON.createTask}
        </Button>
      ) : null}
    </div>
  );
}

function PlannerSkeleton() {
  return (
    <div className="space-y-4" aria-hidden>
      <div className="flex gap-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-16 shrink-0" />
        ))}
      </div>
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-11 w-full" />
      ))}
    </div>
  );
}
