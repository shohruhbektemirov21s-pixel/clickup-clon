"use client";

import * as React from "react";
import { ChevronDown, ChevronRight, MessageSquare, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useGroupedTasks, useMembers, useTags } from "@/hooks/queries";
import { useCreateTask, useDeleteTask, useUpdateTask } from "@/hooks/mutations";
import {
  AssigneePicker,
  DueDatePicker,
  PriorityPicker,
  StatusDot,
  StatusPicker,
  TagPicker,
} from "@/components/task/pickers";
import type { Status, Task } from "@/types/api";
import { cn } from "@/lib/utils";

export function ListView({
  workspaceId,
  listId,
  statuses,
  onOpenTask,
  canEdit,
}: {
  workspaceId: string;
  listId: string;
  statuses: Status[];
  onOpenTask: (taskId: string) => void;
  canEdit: boolean;
}) {
  const { data, isPending, isError, refetch } = useGroupedTasks(listId);

  if (isPending) return <ListSkeleton />;
  if (isError) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-12 text-center">
        <p className="text-sm text-muted-foreground">Couldn&apos;t load tasks.</p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  const orderedStatuses = [...statuses].sort((a, b) => a.order - b.order);
  const groupsByStatus = new Map(data?.groups.map((g) => [g.status_id, g]) ?? []);
  const total = data?.groups.reduce((sum, g) => sum + g.count, 0) ?? 0;

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3">
      {total === 0 && orderedStatuses.length === 0 ? (
        <EmptyState canEdit={canEdit} />
      ) : (
        orderedStatuses.map((status) => (
          <StatusGroup
            key={status.id}
            workspaceId={workspaceId}
            listId={listId}
            status={status}
            statuses={orderedStatuses}
            tasks={groupsByStatus.get(status.id)?.results ?? []}
            count={groupsByStatus.get(status.id)?.count ?? 0}
            onOpenTask={onOpenTask}
            canEdit={canEdit}
          />
        ))
      )}
    </div>
  );
}

function EmptyState({ canEdit }: { canEdit: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      <p className="text-sm font-medium">No tasks here yet.</p>
      {canEdit ? (
        <p className="text-sm text-muted-foreground">
          Use “+ New task” under a status group to add one.
        </p>
      ) : null}
    </div>
  );
}

function StatusGroup({
  workspaceId,
  listId,
  status,
  statuses,
  tasks,
  count,
  onOpenTask,
  canEdit,
}: {
  workspaceId: string;
  listId: string;
  status: Status;
  statuses: Status[];
  tasks: Task[];
  count: number;
  onOpenTask: (taskId: string) => void;
  canEdit: boolean;
}) {
  const [collapsed, setCollapsed] = React.useState(false);
  const [composing, setComposing] = React.useState(false);

  return (
    <section className="mb-4" aria-label={status.name}>
      <div className="sticky top-0 z-10 flex h-8 items-center gap-2 bg-background">
        <button
          className="flex items-center gap-1.5 rounded-md px-1 py-0.5 hover:bg-muted"
          onClick={() => setCollapsed((v) => !v)}
          aria-expanded={!collapsed}
        >
          {collapsed ? (
            <ChevronRight className="size-3.5 text-muted-foreground" />
          ) : (
            <ChevronDown className="size-3.5 text-muted-foreground" />
          )}
          <StatusDot status={status} />
          <span className="text-xs font-semibold tracking-wide uppercase">
            {status.name}
          </span>
          <span className="text-xs text-muted-foreground">{count}</span>
        </button>
        {canEdit && !collapsed ? (
          <Button
            variant="ghost"
            size="xs"
            className="ml-auto text-muted-foreground"
            onClick={() => setComposing(true)}
          >
            <Plus className="size-3.5" /> New task
          </Button>
        ) : null}
      </div>

      {!collapsed ? (
        <div className="mt-1 overflow-hidden rounded-lg border">
          <div className="grid grid-cols-[minmax(240px,1fr)_140px_110px_90px_140px_40px] items-center gap-2 border-b bg-muted/50 px-3 py-1.5 text-xs font-medium text-muted-foreground max-lg:grid-cols-[minmax(200px,1fr)_110px_90px]">
            <span>Name</span>
            <span>Assignees</span>
            <span>Due date</span>
            <span className="max-lg:hidden">Priority</span>
            <span className="max-lg:hidden">Tags</span>
            <span className="max-lg:hidden" />
          </div>
          {tasks.length === 0 && !composing ? (
            <div className="px-3 py-2.5 text-xs text-muted-foreground">No tasks</div>
          ) : (
            tasks.map((task) => (
              <TaskRow
                key={task.id}
                workspaceId={workspaceId}
                listId={listId}
                task={task}
                statuses={statuses}
                onOpen={() => onOpenTask(task.id)}
                canEdit={canEdit}
              />
            ))
          )}
          {canEdit ? (
            composing ? (
              <InlineComposer
                listId={listId}
                statusId={status.id}
                onDone={() => setComposing(false)}
              />
            ) : (
              <button
                className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-xs text-muted-foreground hover:bg-muted/50"
                onClick={() => setComposing(true)}
              >
                <Plus className="size-3.5" /> New task
              </button>
            )
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function TaskRow({
  workspaceId,
  listId,
  task,
  statuses,
  onOpen,
  canEdit,
}: {
  workspaceId: string;
  listId: string;
  task: Task;
  statuses: Status[];
  onOpen: () => void;
  canEdit: boolean;
}) {
  const { data: members } = useMembers(workspaceId);
  const { data: tags } = useTags(workspaceId);
  const updateTask = useUpdateTask(listId);
  const deleteTask = useDeleteTask(listId);
  const status = statuses.find((s) => s.id === task.status_id);
  const closed = status?.type === "closed";

  const patch = (p: Parameters<typeof updateTask.mutate>[0]["patch"]) =>
    updateTask.mutate({ taskId: task.id, patch: p });

  return (
    <div className="group grid h-9 grid-cols-[minmax(240px,1fr)_140px_110px_90px_140px_40px] items-center gap-2 border-b px-3 last:border-b-0 hover:bg-muted/40 max-lg:grid-cols-[minmax(200px,1fr)_110px_90px]">
      <div className="flex min-w-0 items-center gap-2">
        <StatusPicker
          value={task.status_id}
          statuses={statuses}
          disabled={!canEdit}
          onChange={(statusId) => patch({ status_id: statusId })}
          trigger={
            <button
              className="shrink-0 rounded-full p-0.5 hover:bg-muted"
              aria-label={`Status: ${status?.name ?? "unknown"}`}
            >
              <StatusDot status={status} />
            </button>
          }
        />
        <button
          className={cn(
            "truncate text-left text-sm hover:text-primary",
            closed && "text-muted-foreground line-through",
          )}
          onClick={onOpen}
        >
          {task.title}
        </button>
        {task.comment_count > 0 ? (
          <span className="flex shrink-0 items-center gap-0.5 text-xs text-muted-foreground">
            <MessageSquare className="size-3" />
            {task.comment_count}
          </span>
        ) : null}
      </div>

      <AssigneePicker
        value={task.assignees}
        members={members?.results ?? []}
        disabled={!canEdit}
        onChange={(ids) => patch({ assignee_ids: ids })}
      />

      <DueDatePicker
        value={task.due_date}
        disabled={!canEdit}
        overdue={!closed && !!task.due_date && new Date(task.due_date) < new Date()}
        onChange={(iso) => patch({ due_date: iso })}
      />

      <span className="max-lg:hidden">
        <PriorityPicker
          value={task.priority}
          disabled={!canEdit}
          onChange={(p) => patch({ priority: p })}
        />
      </span>

      <span className="max-lg:hidden">
        <TagPicker
          value={task.tags}
          tags={tags?.results ?? []}
          disabled={!canEdit}
          onChange={(ids) => patch({ tag_ids: ids })}
        />
      </span>

      <span className="flex justify-end max-lg:hidden">
        {canEdit ? (
          <Button
            variant="ghost"
            size="icon-xs"
            className="text-muted-foreground opacity-0 group-hover:opacity-100"
            aria-label={`Delete ${task.title}`}
            onClick={() => deleteTask.mutate(task.id)}
          >
            <Trash2 />
          </Button>
        ) : null}
      </span>
    </div>
  );
}

function InlineComposer({
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
    <div className="flex items-center gap-2 border-t px-3 py-1.5">
      <Input
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Task name…  (Enter to create, Esc to close)"
        className="h-7 border-none bg-transparent px-1 shadow-none focus-visible:ring-0"
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

function ListSkeleton() {
  return (
    <div className="flex-1 space-y-2 overflow-hidden px-4 py-4" aria-hidden>
      <Skeleton className="h-5 w-32" />
      {Array.from({ length: 12 }).map((_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  );
}
