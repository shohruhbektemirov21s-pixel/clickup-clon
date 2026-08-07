"use client";

import * as React from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  pointerWithin,
  rectIntersection,
  useDroppable,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { MessageSquare, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useGroupedTasks } from "@/hooks/queries";
import { useCreateTask, useMoveTask } from "@/hooks/mutations";
import { AvatarStack, PriorityFlag, StatusDot, TagChips } from "@/components/task/pickers";
import { formatDueDate, isOverdue } from "@/lib/format";
import type { Status, Task } from "@/types/api";
import { cn } from "@/lib/utils";

const collisionDetection: CollisionDetection = (args) => {
  const within = pointerWithin(args);
  return within.length > 0 ? within : rectIntersection(args);
};

export function BoardView({
  listId,
  statuses,
  onOpenTask,
  canEdit,
}: {
  listId: string;
  statuses: Status[];
  onOpenTask: (taskId: string) => void;
  canEdit: boolean;
}) {
  const { data, isPending, isError, refetch } = useGroupedTasks(listId);
  const moveTask = useMoveTask(listId);
  const [activeTask, setActiveTask] = React.useState<Task | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const orderedStatuses = React.useMemo(
    () => [...statuses].sort((a, b) => a.order - b.order),
    [statuses],
  );
  const groupsByStatus = React.useMemo(
    () => new Map(data?.groups.map((g) => [g.status_id, g]) ?? []),
    [data],
  );

  const findColumnOf = React.useCallback(
    (taskId: string): string | null => {
      for (const group of data?.groups ?? []) {
        if (group.results.some((t) => t.id === taskId)) return group.status_id;
      }
      return null;
    },
    [data],
  );

  const onDragStart = (event: DragStartEvent) => {
    const task = event.active.data.current?.task as Task | undefined;
    setActiveTask(task ?? null);
  };

  const onDragEnd = (event: DragEndEvent) => {
    setActiveTask(null);
    const { active, over } = event;
    if (!over || !data) return;

    const taskId = String(active.id);
    const fromStatusId = findColumnOf(taskId);
    if (!fromStatusId) return;

    // Destination: a card (sortable) or a column body (droppable).
    let toStatusId: string;
    let toIndexWithSelf: number;
    const overData = over.data.current as
      | { type: "task"; task: Task }
      | { type: "column"; statusId: string }
      | undefined;

    if (overData?.type === "task") {
      toStatusId = overData.task.status_id;
      const destTasks = groupsByStatus.get(toStatusId)?.results ?? [];
      toIndexWithSelf = destTasks.findIndex((t) => t.id === overData.task.id);
      if (toIndexWithSelf < 0) return;
    } else if (overData?.type === "column") {
      toStatusId = overData.statusId;
      toIndexWithSelf = (groupsByStatus.get(toStatusId)?.results ?? []).length;
    } else {
      return;
    }

    const destTasks = groupsByStatus.get(toStatusId)?.results ?? [];
    // Neighbours are computed against the destination column WITHOUT the
    // dragged task (§6.3); the server derives the fractional position.
    const withoutSelf = destTasks.filter((t) => t.id !== taskId);
    const fromIndex = destTasks.findIndex((t) => t.id === taskId);
    let toIndex = toIndexWithSelf;
    if (fromIndex !== -1 && fromIndex < toIndexWithSelf) {
      // moving down within the same column: account for self-removal
      toIndex = toIndexWithSelf;
    }
    toIndex = Math.min(toIndex, withoutSelf.length);

    if (toStatusId === fromStatusId && fromIndex === toIndex) return;

    const before = withoutSelf[toIndex - 1] ?? null;
    const after = withoutSelf[toIndex] ?? null;

    moveTask.mutate({
      taskId,
      toStatusId,
      toIndex,
      beforeId: before?.id ?? null,
      afterId: after?.id ?? null,
    });
  };

  if (isPending) return <BoardSkeleton />;
  if (isError) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-12 text-center">
        <p className="text-sm text-muted-foreground">Doskani yuklab bo&apos;lmadi.</p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          Qayta urinish
        </Button>
      </div>
    );
  }

  return (
    <DndContext
      sensors={canEdit ? sensors : undefined}
      collisionDetection={collisionDetection}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragCancel={() => setActiveTask(null)}
    >
      <div className="flex flex-1 items-start gap-4 overflow-x-auto overflow-y-hidden p-4">
        {orderedStatuses.map((status) => (
          <BoardColumn
            key={status.id}
            listId={listId}
            status={status}
            tasks={groupsByStatus.get(status.id)?.results ?? []}
            count={groupsByStatus.get(status.id)?.count ?? 0}
            onOpenTask={onOpenTask}
            canEdit={canEdit}
          />
        ))}
      </div>
      <DragOverlay>
        {activeTask ? <TaskCardContent task={activeTask} dragging /> : null}
      </DragOverlay>
    </DndContext>
  );
}

function BoardColumn({
  listId,
  status,
  tasks,
  count,
  onOpenTask,
  canEdit,
}: {
  listId: string;
  status: Status;
  tasks: Task[];
  count: number;
  onOpenTask: (taskId: string) => void;
  canEdit: boolean;
}) {
  const [composing, setComposing] = React.useState(false);
  const { setNodeRef, isOver } = useDroppable({
    id: `column:${status.id}`,
    data: { type: "column", statusId: status.id },
  });

  return (
    <div className="flex max-h-full w-72 shrink-0 flex-col rounded-lg bg-muted/50">
      <div className="flex items-center gap-2 px-3 py-2.5">
        <StatusDot status={status} />
        <span className="text-xs font-semibold tracking-wide uppercase">{status.name}</span>
        <span className="text-xs text-muted-foreground">{count}</span>
        {canEdit ? (
          <Button
            variant="ghost"
            size="icon-xs"
            className="ml-auto text-muted-foreground"
            aria-label={`${status.name} ustuniga vazifa qo'shish`}
            onClick={() => setComposing(true)}
          >
            <Plus />
          </Button>
        ) : null}
      </div>
      <div
        ref={setNodeRef}
        className={cn(
          "flex min-h-16 flex-col gap-2 overflow-y-auto px-2 pb-2",
          isOver && "rounded-md ring-2 ring-primary/40",
        )}
      >
        {composing ? (
          <ColumnComposer
            listId={listId}
            statusId={status.id}
            onDone={() => setComposing(false)}
          />
        ) : null}
        <SortableContext
          items={tasks.map((t) => t.id)}
          strategy={verticalListSortingStrategy}
        >
          {tasks.map((task) => (
            <SortableTaskCard
              key={task.id}
              task={task}
              onOpen={() => onOpenTask(task.id)}
              canDrag={canEdit}
            />
          ))}
        </SortableContext>
        {tasks.length === 0 && !composing ? (
          <div className="flex h-16 items-center justify-center rounded-lg border border-dashed border-primary/40 text-xs text-muted-foreground">
            Vazifani shu yerga tashlang
          </div>
        ) : null}
      </div>
    </div>
  );
}

function SortableTaskCard({
  task,
  onOpen,
  canDrag,
}: {
  task: Task;
  onOpen: () => void;
  canDrag: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({
      id: task.id,
      data: { type: "task", task },
      disabled: !canDrag,
    });

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(isDragging && "opacity-40")}
      {...attributes}
      {...listeners}
    >
      <TaskCardContent task={task} onOpen={onOpen} />
    </div>
  );
}

function TaskCardContent({
  task,
  onOpen,
  dragging,
}: {
  task: Task;
  onOpen?: () => void;
  dragging?: boolean;
}) {
  const overdue = isOverdue(task.due_date);
  return (
    <div
      role={onOpen ? "button" : undefined}
      tabIndex={onOpen ? 0 : undefined}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (onOpen && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          onOpen();
        }
      }}
      className={cn(
        "flex min-h-[68px] cursor-pointer flex-col gap-2 rounded-lg border bg-card p-3 shadow-sm transition-shadow hover:shadow-md",
        dragging && "rotate-2 scale-[1.02] shadow-md ring-2 ring-primary",
      )}
    >
      <div className="flex items-start gap-1.5">
        {task.priority !== "none" ? (
          <PriorityFlag priority={task.priority} className="mt-0.5" />
        ) : null}
        <span className="text-[13px] leading-snug font-medium">{task.title}</span>
      </div>
      {task.tags.length > 0 ? <TagChips value={task.tags} max={3} /> : null}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {task.due_date ? (
          <span className={cn(overdue && "text-danger")}>{formatDueDate(task.due_date)}</span>
        ) : null}
        {task.comment_count > 0 ? (
          <span className="flex items-center gap-0.5">
            <MessageSquare className="size-3" />
            {task.comment_count}
          </span>
        ) : null}
        <span className="ml-auto">
          <AvatarStack users={task.assignees} max={3} />
        </span>
      </div>
    </div>
  );
}

function ColumnComposer({
  listId,
  statusId,
  onDone,
}: {
  listId: string;
  statusId: string;
  onDone: () => void;
}) {
  const [title, setTitle] = React.useState("");
  const createTask = useCreateTask(listId);

  const submit = () => {
    const trimmed = title.trim();
    if (!trimmed) return;
    createTask.mutate({ title: trimmed, status_id: statusId });
    setTitle("");
  };

  return (
    <div className="rounded-lg border bg-card p-2 shadow-sm">
      <Input
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Vazifa nomi…"
        className="h-7 border-none px-1 shadow-none focus-visible:ring-0"
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            submit();
          } else if (e.key === "Escape") {
            onDone();
          }
        }}
        onBlur={() => {
          if (!title.trim()) onDone();
        }}
      />
    </div>
  );
}

function BoardSkeleton() {
  return (
    <div className="flex flex-1 gap-4 overflow-hidden p-4" aria-hidden>
      {Array.from({ length: 4 }).map((_, col) => (
        <div key={col} className="flex w-72 shrink-0 flex-col gap-2">
          <Skeleton className="h-5 w-32" />
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-[68px] w-full rounded-lg" />
          ))}
        </div>
      ))}
    </div>
  );
}
