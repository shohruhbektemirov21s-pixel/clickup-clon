"use client";

import Link from "next/link";
import { MessageSquare } from "lucide-react";
import { PriorityFlag, StatusDot } from "@/components/task/pickers";
import { formatDueDate, PRIORITY_META } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Status, Task } from "@/types/api";

/**
 * One compact task line. Shared by the workspace dashboard and the member
 * profile so both read identically; clicking opens the task in its own list
 * page (`?task=` deep link), never a separate detail route.
 */
export function TaskRow({
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
