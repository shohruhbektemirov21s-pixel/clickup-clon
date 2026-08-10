"use client";

import * as React from "react";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateTask } from "@/hooks/mutations";
import { StatusDot } from "@/components/task/pickers";
import { STATUS_TYPE_COLOR } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Status, Task } from "@/types/api";
import { SortableBoardCard } from "@/components/board/board-card";

/** Soft WIP ceiling — above this the header count turns amber and shows `20+`. */
export const WIP_LIMIT = 20;

export function BoardColumn({
  listId,
  status,
  tasks,
  count,
  dropIndex,
  isDropTarget,
  isDragActive,
  canCreate,
  canMoveTask,
  focusTaskId,
  onOpenTask,
  onMoveColumn,
  onFocusHandled,
}: {
  listId: string;
  status: Status;
  tasks: Task[];
  count: number;
  /** Index the lifted card would land at, or `null` when this is not the target. */
  dropIndex: number | null;
  isDropTarget: boolean;
  isDragActive: boolean;
  canCreate: boolean;
  canMoveTask: (task: Task) => boolean;
  focusTaskId: string | null;
  onOpenTask: (taskId: string) => void;
  onMoveColumn: (task: Task, direction: -1 | 1) => void;
  onFocusHandled: () => void;
}) {
  const [composing, setComposing] = React.useState(false);
  const { setNodeRef } = useDroppable({
    id: `column:${status.id}`,
    data: { type: "column", statusId: status.id },
  });

  const overWip = count > WIP_LIMIT;
  const accent = status.color || STATUS_TYPE_COLOR[status.type];
  const wipHint = `Ustunda ${count} ta vazifa — tavsiya etilgan chegara ${WIP_LIMIT} ta`;

  return (
    <section
      aria-label={`${status.name} ustuni, ${count} ta vazifa`}
      className={cn(
        "flex max-h-full w-72 shrink-0 flex-col overflow-hidden rounded-lg bg-muted/50 transition-colors",
        isDropTarget && "bg-primary/5 ring-1 ring-primary/30",
      )}
    >
      <span aria-hidden className="h-0.5 w-full shrink-0" style={{ backgroundColor: accent }} />

      <header className="flex shrink-0 items-center gap-2 px-3 py-2.5">
        <StatusDot status={status} />
        <span className="min-w-0 truncate text-xs font-semibold tracking-wide uppercase">
          {status.name}
        </span>
        <span
          className={cn(
            "shrink-0 rounded-full px-1.5 py-px text-[11px] font-medium tabular-nums",
            overWip
              ? "bg-brand-yellow/25 text-amber-700 dark:text-brand-yellow"
              : "bg-foreground/8 text-muted-foreground",
          )}
        >
          {count}
        </span>
        {overWip ? (
          <span
            title={wipHint}
            className="shrink-0 rounded-full bg-brand-yellow/25 px-1.5 py-px text-[11px] font-semibold text-amber-700 dark:text-brand-yellow"
          >
            {WIP_LIMIT}+<span className="sr-only"> — {wipHint}</span>
          </span>
        ) : null}
        {canCreate ? (
          <Button
            variant="ghost"
            size="icon-xs"
            className="ml-auto shrink-0 text-muted-foreground"
            aria-label={`${status.name} ustuniga vazifa qo'shish`}
            onClick={() => setComposing(true)}
          >
            <Plus />
          </Button>
        ) : null}
      </header>

      <div ref={setNodeRef} className="flex min-h-16 flex-1 flex-col gap-2 overflow-y-auto px-2 pb-2">
        {composing ? (
          <ColumnComposer listId={listId} statusId={status.id} onDone={() => setComposing(false)} />
        ) : null}

        <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
          {tasks.map((task, index) => (
            <SortableBoardCard
              key={task.id}
              task={task}
              canDrag={canMoveTask(task)}
              showDropIndicator={dropIndex === index}
              focusRequested={focusTaskId === task.id}
              onOpen={() => onOpenTask(task.id)}
              onMoveColumn={onMoveColumn}
              onFocusHandled={onFocusHandled}
            />
          ))}
        </SortableContext>

        {/* Tail indicator: always mounted so appearing mid-drag never reflows. */}
        <span
          aria-hidden
          className={cn(
            "h-0.5 shrink-0 rounded-full transition-colors",
            tasks.length > 0 && dropIndex === tasks.length ? "bg-primary" : "bg-transparent",
          )}
        />

        {tasks.length === 0 && !composing ? (
          <EmptyColumn
            statusName={status.name}
            isDragActive={isDragActive}
            isDropTarget={isDropTarget}
            canCreate={canCreate}
            onCompose={() => setComposing(true)}
          />
        ) : null}

        {tasks.length > 0 && canCreate && !composing ? (
          <Button
            variant="ghost"
            size="sm"
            className="justify-start text-muted-foreground"
            onClick={() => setComposing(true)}
          >
            <Plus /> Vazifa qo&apos;shish
          </Button>
        ) : null}
      </div>
    </section>
  );
}

function EmptyColumn({
  statusName,
  isDragActive,
  isDropTarget,
  canCreate,
  onCompose,
}: {
  statusName: string;
  isDragActive: boolean;
  isDropTarget: boolean;
  canCreate: boolean;
  onCompose: () => void;
}) {
  if (isDragActive) {
    return (
      <div
        className={cn(
          "flex h-[68px] shrink-0 items-center justify-center rounded-lg border border-dashed text-xs transition-colors",
          isDropTarget
            ? "border-primary bg-primary/10 text-primary"
            : "border-primary/40 text-muted-foreground",
        )}
      >
        Vazifani shu yerga tashlang
      </div>
    );
  }

  return (
    <div className="flex shrink-0 flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-border px-3 py-5 text-center">
      <p className="text-xs font-medium text-muted-foreground">Bu ustun bo&apos;sh</p>
      <p className="text-[11px] text-muted-foreground/80">
        {canCreate
          ? `«${statusName}» holatidagi vazifalar shu yerda ko'rinadi.`
          : "Hozircha bu holatda vazifa yo'q."}
      </p>
      {canCreate ? (
        <Button variant="outline" size="sm" className="mt-1" onClick={onCompose}>
          <Plus /> Vazifa qo&apos;shish
        </Button>
      ) : null}
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
    <div className="shrink-0 rounded-lg border bg-card p-2 shadow-sm">
      <Input
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Vazifa nomi…"
        aria-label="Yangi vazifa nomi"
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
