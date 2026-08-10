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
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
  type SensorDescriptor,
  type SensorOptions,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { useGroupedTasks } from "@/hooks/queries";
import { useMoveTask } from "@/hooks/mutations";
import { BoardCard } from "@/components/board/board-card";
import { BoardColumn } from "@/components/board/board-column";
import { BoardError, BoardSkeleton } from "@/components/board/board-states";
import { useBoardPermissions } from "@/components/board/use-board-permissions";
import type { Status, Task } from "@/types/api";

const collisionDetection: CollisionDetection = (args) => {
  const within = pointerWithin(args);
  return within.length > 0 ? within : rectIntersection(args);
};

/** Stable identity — a fresh `[]` each render would remount every sensor. */
const NO_SENSORS: SensorDescriptor<SensorOptions>[] = [];

type DropTarget = { statusId: string; index: number | null };

type OverData =
  | { type: "task"; task: Task }
  | { type: "column"; statusId: string }
  | undefined;

export function BoardView({
  workspaceId,
  listId,
  spaceId,
  statuses,
  onOpenTask,
}: {
  workspaceId: string;
  listId: string;
  /** `List.space_id`. `undefined` bo'lsa sudrash umuman yoqilmaydi. */
  spaceId: string | undefined;
  statuses: Status[];
  onOpenTask: (taskId: string) => void;
}) {
  const { data, isPending, isError, isFetching, refetch } = useGroupedTasks(listId);
  const moveTask = useMoveTask(listId);
  const { canCreateTask, canDragSome, canMoveTask } = useBoardPermissions(
    workspaceId,
    spaceId,
  );

  const [activeTask, setActiveTask] = React.useState<Task | null>(null);
  const [dropTarget, setDropTarget] = React.useState<DropTarget | null>(null);
  const [announcement, setAnnouncement] = React.useState("");
  const [focusTaskId, setFocusTaskId] = React.useState<string | null>(null);

  const allSensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
    // `Space` lifts; `Enter` is left free so it can open the task (UI_SPEC §S6.5).
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
      keyboardCodes: { start: ["Space"], cancel: ["Escape"], end: ["Space", "Enter"] },
    }),
  );
  // Passing `undefined` would fall back to dnd-kit's *default* sensors, which is
  // how a read-only board used to stay draggable. An empty array truly disables.
  const sensors = canDragSome ? allSensors : NO_SENSORS;

  const orderedStatuses = React.useMemo(
    () => [...statuses].sort((a, b) => a.order - b.order),
    [statuses],
  );
  const groupsByStatus = React.useMemo(
    () => new Map(data?.groups.map((g) => [g.status_id, g]) ?? []),
    [data],
  );
  const statusNameById = React.useMemo(
    () => new Map(orderedStatuses.map((s) => [s.id, s.name])),
    [orderedStatuses],
  );

  const clearFocusRequest = React.useCallback(() => setFocusTaskId(null), []);

  /**
   * Single write path for both pointer drops and keyboard moves.
   * `toIndex` is an index into the destination column **without** the moved task,
   * which is exactly what `applyLocalMove` and the server's neighbour contract
   * (`before_id` / `after_id`) expect.
   */
  const commitMove = React.useCallback(
    (task: Task, toStatusId: string, toIndex: number) => {
      const destTasks = groupsByStatus.get(toStatusId)?.results ?? [];
      const withoutSelf = destTasks.filter((t) => t.id !== task.id);
      const index = Math.max(0, Math.min(toIndex, withoutSelf.length));

      const fromStatusId = task.status_id;
      if (fromStatusId === toStatusId) {
        const currentIndex = destTasks.findIndex((t) => t.id === task.id);
        if (currentIndex === index) return;
      }

      const before = withoutSelf[index - 1] ?? null;
      const after = withoutSelf[index] ?? null;

      moveTask.mutate({
        taskId: task.id,
        toStatusId,
        toIndex: index,
        beforeId: before?.id ?? null,
        afterId: after?.id ?? null,
      });

      const statusName = statusNameById.get(toStatusId) ?? "";
      setAnnouncement(
        fromStatusId === toStatusId
          ? `«${task.title}» vazifasi ${statusName} ustunida ${index + 1}-o'ringa ko'chirildi.`
          : `«${task.title}» vazifasi ${statusName} ustuniga ko'chirildi.`,
      );
    },
    [groupsByStatus, moveTask, statusNameById],
  );

  /** `Ctrl+←/→` on a focused card — the keyboard equivalent of a cross-column drag. */
  const moveByKeyboard = React.useCallback(
    (task: Task, direction: -1 | 1) => {
      if (!canMoveTask(task)) return;
      const fromIndex = orderedStatuses.findIndex((s) => s.id === task.status_id);
      if (fromIndex < 0) return;
      const target = orderedStatuses[fromIndex + direction];
      setFocusTaskId(task.id);
      if (!target) {
        setAnnouncement(
          direction === -1
            ? `«${task.title}» allaqachon birinchi ustunda.`
            : `«${task.title}» allaqachon oxirgi ustunda.`,
        );
        return;
      }
      const destCount = (groupsByStatus.get(target.id)?.results ?? []).filter(
        (t) => t.id !== task.id,
      ).length;
      commitMove(task, target.id, destCount);
    },
    [canMoveTask, commitMove, groupsByStatus, orderedStatuses],
  );

  const onDragStart = (event: DragStartEvent) => {
    const task = event.active.data.current?.task as Task | undefined;
    setActiveTask(task ?? null);
  };

  // `onDragOver` fires on every pointer move, so only commit a *changed* target;
  // otherwise the whole board re-renders dozens of times per second.
  const setDropTargetIfChanged = React.useCallback((next: DropTarget | null) => {
    setDropTarget((prev) => {
      if (prev === next) return prev;
      if (prev && next && prev.statusId === next.statusId && prev.index === next.index) return prev;
      return next;
    });
  }, []);

  const onDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    const overData = over?.data.current as OverData;
    if (!overData) {
      setDropTargetIfChanged(null);
      return;
    }
    if (overData.type === "column") {
      const results = groupsByStatus.get(overData.statusId)?.results ?? [];
      setDropTargetIfChanged({ statusId: overData.statusId, index: results.length });
      return;
    }
    const statusId = overData.task.status_id;
    const results = groupsByStatus.get(statusId)?.results ?? [];
    const overIndex = results.findIndex((t) => t.id === overData.task.id);
    if (overIndex < 0) {
      setDropTargetIfChanged(null);
      return;
    }
    const activeIndex = results.findIndex((t) => t.id === String(active.id));
    // Dragging downwards inside one column lands *after* the hovered card.
    const index = activeIndex !== -1 && overIndex > activeIndex ? overIndex + 1 : overIndex;
    setDropTargetIfChanged({ statusId, index: index === activeIndex ? null : index });
  };

  const resetDrag = () => {
    setActiveTask(null);
    setDropTarget(null);
  };

  const onDragEnd = (event: DragEndEvent) => {
    resetDrag();
    const { active, over } = event;
    if (!over || !data) return;

    const task = active.data.current?.task as Task | undefined;
    if (!task || !canMoveTask(task)) return;

    const overData = over.data.current as OverData;
    if (!overData) return;

    if (overData.type === "column") {
      const destTasks = groupsByStatus.get(overData.statusId)?.results ?? [];
      commitMove(task, overData.statusId, destTasks.length);
      return;
    }

    const toStatusId = overData.task.status_id;
    const destTasks = groupsByStatus.get(toStatusId)?.results ?? [];
    const overIndex = destTasks.findIndex((t) => t.id === overData.task.id);
    if (overIndex < 0) return;
    commitMove(task, toStatusId, overIndex);
  };

  if (isPending) return <BoardSkeleton />;
  if (isError) return <BoardError onRetry={() => void refetch()} isRetrying={isFetching} />;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={collisionDetection}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragEnd={onDragEnd}
      onDragCancel={resetDrag}
    >
      <div className="flex flex-1 items-start gap-4 overflow-x-auto overflow-y-hidden p-4">
        {orderedStatuses.map((status) => (
          <BoardColumn
            key={status.id}
            listId={listId}
            status={status}
            tasks={groupsByStatus.get(status.id)?.results ?? []}
            count={groupsByStatus.get(status.id)?.count ?? 0}
            dropIndex={dropTarget?.statusId === status.id ? dropTarget.index : null}
            isDropTarget={dropTarget?.statusId === status.id}
            isDragActive={activeTask !== null}
            canCreate={canCreateTask}
            canMoveTask={canMoveTask}
            focusTaskId={focusTaskId}
            onOpenTask={onOpenTask}
            onMoveColumn={moveByKeyboard}
            onFocusHandled={clearFocusRequest}
          />
        ))}
      </div>

      <DragOverlay dropAnimation={{ duration: 180, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" }}>
        {activeTask ? <BoardCard task={activeTask} dragging /> : null}
      </DragOverlay>

      {/* Screen-reader narration for every completed move, pointer or keyboard. */}
      <div role="status" aria-live="polite" aria-atomic className="sr-only">
        {announcement}
      </div>
    </DndContext>
  );
}
