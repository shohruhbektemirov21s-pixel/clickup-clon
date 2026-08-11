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
import { STATUS_LABEL } from "@/i18n/uz";
import type { Task, TaskGroup, TaskStatus } from "@/types/api";

const collisionDetection: CollisionDetection = (args) => {
  const within = pointerWithin(args);
  return within.length > 0 ? within : rectIntersection(args);
};

/** Stable identity — a fresh `[]` each render would remount every sensor. */
const NO_SENSORS: SensorDescriptor<SensorOptions>[] = [];

/** Same reason: an empty board must not hand `useMemo` a new array each render. */
const NO_GROUPS: TaskGroup[] = [];

type DropTarget = { status: TaskStatus; index: number | null };

type OverData =
  | { type: "task"; task: Task }
  | { type: "column"; status: TaskStatus }
  | undefined;

export function BoardView({
  workspaceId,
  listId,
  spaceId,
  onOpenTask,
}: {
  workspaceId: string;
  listId: string;
  /** `List.space_id`. `undefined` bo'lsa sudrash umuman yoqilmaydi. */
  spaceId: string | undefined;
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

  /**
   * Ustunlar SERVERDAN keladi (§10.4): javob doim to'rtta guruhni
   * `STATUS_ORDER` tartibida qaytaradi, ustun bo'sh bo'lsa ham. Klient
   * ularni ma'lumotdagi kodlardan yig'maydi — aks holda bo'sh ustun
   * doskadan yo'qolib qolardi va u yerga hech narsani tashlab bo'lmasdi.
   */
  const groups = data?.groups ?? NO_GROUPS;
  const groupByStatus = React.useMemo(
    () => new Map(groups.map((g) => [g.status, g])),
    [groups],
  );
  const statusOrder = React.useMemo(() => groups.map((g) => g.status), [groups]);

  const clearFocusRequest = React.useCallback(() => setFocusTaskId(null), []);

  /**
   * Single write path for both pointer drops and keyboard moves.
   * `toIndex` is an index into the destination column **without** the moved task,
   * which is exactly what `applyLocalMove` and the server's neighbour contract
   * (`before_id` / `after_id`) expect.
   */
  const commitMove = React.useCallback(
    (task: Task, toStatus: TaskStatus, toIndex: number) => {
      const destTasks = groupByStatus.get(toStatus)?.tasks ?? [];
      const withoutSelf = destTasks.filter((t) => t.id !== task.id);
      const index = Math.max(0, Math.min(toIndex, withoutSelf.length));

      const fromStatus = task.status;
      if (fromStatus === toStatus) {
        const currentIndex = destTasks.findIndex((t) => t.id === task.id);
        if (currentIndex === index) return;
      }

      const before = withoutSelf[index - 1] ?? null;
      const after = withoutSelf[index] ?? null;

      moveTask.mutate({
        taskId: task.id,
        toStatus,
        toIndex: index,
        beforeId: before?.id ?? null,
        afterId: after?.id ?? null,
      });

      const statusName = STATUS_LABEL[toStatus];
      setAnnouncement(
        fromStatus === toStatus
          ? `«${task.title}» vazifasi ${statusName} ustunida ${index + 1}-o'ringa ko'chirildi.`
          : `«${task.title}» vazifasi ${statusName} ustuniga ko'chirildi.`,
      );
    },
    [groupByStatus, moveTask],
  );

  /** `Ctrl+←/→` on a focused card — the keyboard equivalent of a cross-column drag. */
  const moveByKeyboard = React.useCallback(
    (task: Task, direction: -1 | 1) => {
      if (!canMoveTask(task)) return;
      const fromIndex = statusOrder.indexOf(task.status);
      if (fromIndex < 0) return;
      const target = statusOrder[fromIndex + direction];
      setFocusTaskId(task.id);
      if (!target) {
        setAnnouncement(
          direction === -1
            ? `«${task.title}» allaqachon birinchi ustunda.`
            : `«${task.title}» allaqachon oxirgi ustunda.`,
        );
        return;
      }
      const destCount = (groupByStatus.get(target)?.tasks ?? []).filter(
        (t) => t.id !== task.id,
      ).length;
      commitMove(task, target, destCount);
    },
    [canMoveTask, commitMove, groupByStatus, statusOrder],
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
      if (prev && next && prev.status === next.status && prev.index === next.index) return prev;
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
      const tasks = groupByStatus.get(overData.status)?.tasks ?? [];
      setDropTargetIfChanged({ status: overData.status, index: tasks.length });
      return;
    }
    const status = overData.task.status;
    const tasks = groupByStatus.get(status)?.tasks ?? [];
    const overIndex = tasks.findIndex((t) => t.id === overData.task.id);
    if (overIndex < 0) {
      setDropTargetIfChanged(null);
      return;
    }
    const activeIndex = tasks.findIndex((t) => t.id === String(active.id));
    // Dragging downwards inside one column lands *after* the hovered card.
    const index = activeIndex !== -1 && overIndex > activeIndex ? overIndex + 1 : overIndex;
    setDropTargetIfChanged({ status, index: index === activeIndex ? null : index });
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
      const destTasks = groupByStatus.get(overData.status)?.tasks ?? [];
      commitMove(task, overData.status, destTasks.length);
      return;
    }

    const toStatus = overData.task.status;
    const destTasks = groupByStatus.get(toStatus)?.tasks ?? [];
    const overIndex = destTasks.findIndex((t) => t.id === overData.task.id);
    if (overIndex < 0) return;
    commitMove(task, toStatus, overIndex);
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
        {groups.map((group) => (
          <BoardColumn
            key={group.status}
            listId={listId}
            status={group.status}
            label={group.label || STATUS_LABEL[group.status]}
            tasks={group.tasks}
            count={group.count}
            dropIndex={dropTarget?.status === group.status ? dropTarget.index : null}
            isDropTarget={dropTarget?.status === group.status}
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
