"use client";

import * as React from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { MessageSquare, Paperclip } from "lucide-react";
import { AvatarStack, PriorityFlag, TagChips } from "@/components/task/pickers";
import { formatDueDate, isOverdue } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Task } from "@/types/api";

/** Pointer travel (px) above which a pointer-up is a drop, not a click. */
const CLICK_SLOP = 4;

/**
 * Presentational card. Shared by the sortable card and the `DragOverlay`
 * so the lifted card is pixel-identical to the one it replaced.
 */
export function BoardCard({
  task,
  dragging,
  className,
}: {
  task: Task;
  dragging?: boolean;
  className?: string;
}) {
  const overdue = isOverdue(task.due_date);
  return (
    <div
      className={cn(
        "flex min-h-[68px] flex-col gap-2 rounded-lg border bg-card p-3 shadow-sm transition-shadow",
        dragging && "rotate-2 scale-[1.02] shadow-md ring-2 ring-primary",
        className,
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
          <span className={cn(overdue && "font-medium text-danger")}>
            {formatDueDate(task.due_date)}
          </span>
        ) : null}
        {task.comment_count > 0 ? (
          <span className="flex items-center gap-0.5" title={`${task.comment_count} izoh`}>
            <MessageSquare className="size-3" />
            {task.comment_count}
          </span>
        ) : null}
        {task.attachment_count > 0 ? (
          <span className="flex items-center gap-0.5" title={`${task.attachment_count} biriktirma`}>
            <Paperclip className="size-3" />
            {task.attachment_count}
          </span>
        ) : null}
        <span className="ml-auto">
          <AvatarStack users={task.assignees} max={3} />
        </span>
      </div>
    </div>
  );
}

/**
 * Draggable / focusable wrapper.
 *
 * - `canDrag === false` → no dnd-kit listeners at all and `cursor: default`,
 *   but the card stays focusable and openable (reading is always allowed).
 * - `Ctrl+←/→` moves the focused card to the neighbouring column, which is the
 *   only non-pointer way to reorder across columns (dnd-kit's `Space` lift only
 *   works reliably inside one column).
 */
export function SortableBoardCard({
  task,
  canDrag,
  showDropIndicator,
  focusRequested,
  onOpen,
  onMoveColumn,
  onFocusHandled,
}: {
  task: Task;
  canDrag: boolean;
  showDropIndicator: boolean;
  focusRequested: boolean;
  onOpen: () => void;
  onMoveColumn: (task: Task, direction: -1 | 1) => void;
  onFocusHandled: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: task.id,
    data: { type: "task", task },
    disabled: !canDrag,
  });

  const nodeRef = React.useRef<HTMLDivElement | null>(null);
  const pointerOrigin = React.useRef<{ x: number; y: number } | null>(null);

  const setRefs = React.useCallback(
    (node: HTMLDivElement | null) => {
      nodeRef.current = node;
      setNodeRef(node);
    },
    [setNodeRef],
  );

  // A keyboard move re-parents the card into another column, so React unmounts
  // and remounts it and focus would otherwise fall back to <body>.
  React.useEffect(() => {
    if (!focusRequested) return;
    nodeRef.current?.focus();
    onFocusHandled();
  }, [focusRequested, onFocusHandled]);

  const {
    onKeyDown: dndKeyDown,
    onPointerDown: dndPointerDown,
    ...restListeners
  } = listeners ?? {};

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    // During an active keyboard lift, `Enter` belongs to dnd-kit (it drops the
    // card); only a card at rest opens on `Enter`.
    if (event.key === "Enter" && !isDragging) {
      event.preventDefault();
      onOpen();
      return;
    }
    if (event.ctrlKey && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
      event.preventDefault();
      event.stopPropagation();
      if (canDrag) onMoveColumn(task, event.key === "ArrowLeft" ? -1 : 1);
      return;
    }
    if (canDrag) (dndKeyDown as React.KeyboardEventHandler<HTMLDivElement> | undefined)?.(event);
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    pointerOrigin.current = { x: event.clientX, y: event.clientY };
    if (canDrag) {
      (dndPointerDown as React.PointerEventHandler<HTMLDivElement> | undefined)?.(event);
    }
  };

  // Swallow the synthetic click that follows a real drag; dnd-kit lets it through.
  const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const origin = pointerOrigin.current;
    pointerOrigin.current = null;
    if (isDragging) return;
    if (origin) {
      const travelled = Math.hypot(event.clientX - origin.x, event.clientY - origin.y);
      if (travelled > CLICK_SLOP) return;
    }
    onOpen();
  };

  return (
    <div
      ref={setRefs}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        "relative rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
        canDrag ? "cursor-grab active:cursor-grabbing" : "cursor-default",
        isDragging && "opacity-40",
      )}
      {...(canDrag ? attributes : { role: "button", tabIndex: 0 })}
      {...(canDrag ? restListeners : {})}
      aria-keyshortcuts={canDrag ? "Control+ArrowLeft Control+ArrowRight" : undefined}
      onPointerDown={handlePointerDown}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
    >
      {showDropIndicator ? (
        <span
          aria-hidden
          className="pointer-events-none absolute -top-1.5 right-0 left-0 h-0.5 rounded-full bg-primary shadow-[0_0_0_2px] shadow-primary/25"
        />
      ) : null}
      <BoardCard task={task} className={canDrag ? "hover:shadow-md" : undefined} />
    </div>
  );
}
