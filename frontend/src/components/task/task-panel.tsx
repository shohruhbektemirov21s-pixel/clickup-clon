"use client";

import * as React from "react";
import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useMe, useMembers, useMyPermissions, useTags, useTask } from "@/hooks/queries";
import { can } from "@/lib/permissions";
import { useUpdateTask } from "@/hooks/mutations";
import { api, isApiError } from "@/lib/api";
import { keys } from "@/lib/keys";
import { richBodyToText, textToRichBody, timeAgo } from "@/lib/format";
import {
  AssigneePicker,
  AvatarStack,
  DueDatePicker,
  PriorityPicker,
  StatusPicker,
} from "@/components/task/pickers";
import { TagPicker } from "@/components/task/pickers";
import { CommentsThread } from "@/components/task/comments";
import { TaskAttachments } from "@/components/task/attachments";
import { TaskActionsMenu } from "@/components/task/task-actions-menu";
import type { ListPermissions } from "@/components/list/use-list-permissions";
import { resolveAssignees, resolveTags } from "@/lib/resolve-embedded";
import type { Status, Task } from "@/types/api";

export function TaskPanel({
  workspaceId,
  listId,
  taskId,
  statuses,
  perms,
  onClose,
}: {
  workspaceId: string;
  listId: string;
  taskId: string | null;
  statuses: Status[];
  /**
   * Ro'yxat qatoriga qanday qaror qo'llanilgan bo'lsa, panelda ham xuddi
   * shu. Ilgari panel `!isGuest || isAssignee` degan **rol** tekshiruvini
   * o'zi qilardi: to'g'ri "faqat o'qish" qatoridan ochilgan begona vazifa
   * panelda to'liq tahrirlanadigan bo'lib ko'rinardi va har bosish 403 bilan
   * qaytarilardi.
   */
  perms: ListPermissions;
  onClose: () => void;
}) {
  return (
    <Sheet open={!!taskId} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
        className="w-full gap-0 p-0 sm:max-w-[720px]!"
        aria-describedby={undefined}
      >
        {taskId ? (
          <TaskPanelBody
            workspaceId={workspaceId}
            listId={listId}
            taskId={taskId}
            statuses={statuses}
            perms={perms}
            onClose={onClose}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function TaskPanelBody({
  workspaceId,
  listId,
  taskId,
  statuses,
  perms,
  onClose,
}: {
  workspaceId: string;
  listId: string;
  taskId: string;
  statuses: Status[];
  perms: ListPermissions;
  onClose: () => void;
}) {
  const { data: task, isPending, isError } = useTask(taskId);
  const { data: me } = useMe();
  const canEdit = !!task && perms.canEditTask(task);

  if (isPending) return <PanelSkeleton />;
  if (isError || !task) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8">
        <p className="text-sm text-muted-foreground">Bu vazifa endi mavjud emas.</p>
        <Button variant="outline" size="sm" onClick={onClose}>
          Yopish
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <SheetHeader className="border-b px-6 py-4">
        <SheetTitle className="sr-only">{task.title}</SheetTitle>
        <SheetDescription className="sr-only">Vazifa tafsilotlari</SheetDescription>
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <TitleEditor
              task={task}
              listId={listId}
              canEdit={canEdit}
              hint={perms.hint(canEdit)}
            />
          </div>
          <TaskActionsMenu
            listId={listId}
            taskId={task.id}
            taskTitle={task.title}
            canDelete={perms.canDeleteTask}
            onDeleted={onClose}
          />
        </div>
      </SheetHeader>

      <div className="flex-1 overflow-y-auto">
        <FieldGrid
          workspaceId={workspaceId}
          listId={listId}
          task={task}
          statuses={statuses}
          perms={perms}
          canEdit={canEdit}
          meId={me?.id}
        />
        <Separator />
        <DescriptionEditor task={task} listId={listId} canEdit={canEdit} />
        <Separator />
        {/* Bajarilgan vazifada ham faol — `canEdit` bilan gate qilinmaydi.
            Yagona shart `attachment.*` ruxsatlari (§10.7). */}
        <TaskAttachments taskId={task.id} perms={perms} />
        <Separator />
        <CommentsThread taskId={task.id} perms={perms} />
      </div>

      <footer className="border-t px-6 py-2 text-xs text-muted-foreground">
        Yaratilgan: {timeAgo(task.created_at)}
        {task.created_by
          ? ` (${task.created_by.full_name || task.created_by.email})`
          : ""}{" "}
        · Yangilangan: {timeAgo(task.updated_at)}
      </footer>
    </div>
  );
}

function TitleEditor({
  task,
  listId,
  canEdit,
  hint,
}: {
  task: Task;
  listId: string;
  canEdit: boolean;
  hint?: string;
}) {
  const updateTask = useUpdateTask(listId);
  const [value, setValue] = React.useState(task.title);
  const [lastTitle, setLastTitle] = React.useState(task.title);
  // Sync when the server value changes (render-time adjustment, not an effect).
  if (task.title !== lastTitle) {
    setLastTitle(task.title);
    setValue(task.title);
  }

  const commit = () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed === task.title) {
      setValue(task.title);
      return;
    }
    updateTask.mutate({ taskId: task.id, patch: { title: trimmed } });
  };

  return (
    <Textarea
      value={value}
      readOnly={!canEdit}
      onChange={(e) => setValue(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.currentTarget.blur();
        }
        if (e.key === "Escape") setValue(task.title);
      }}
      rows={1}
      className="min-h-0 resize-none border-none p-0 text-lg font-semibold shadow-none focus-visible:ring-0"
      aria-label="Vazifa nomi"
      title={hint}
    />
  );
}

function FieldGrid({
  workspaceId,
  listId,
  task,
  statuses,
  perms,
  canEdit,
  meId,
}: {
  workspaceId: string;
  listId: string;
  task: Task;
  statuses: Status[];
  perms: ListPermissions;
  canEdit: boolean;
  meId?: string;
}) {
  const { data: members } = useMembers(workspaceId);
  const { data: tags } = useTags(workspaceId);
  // Mas'ul topilmaganda taklif blokini ko'rsatish uchun (`member.invite`).
  const { data: my } = useMyPermissions(workspaceId);
  const updateTask = useUpdateTask(listId);
  const queryClient = useQueryClient();
  const watching = !!meId && task.watchers.some((w) => w.id === meId);

  // Mas'ullarni almashtirish tahrirdan alohida, admin darajasidagi
  // `task.assign` kodini talab qiladi (server: `assignees_are_changing`).
  const canAssign = perms.canAssignTask(task);
  const canWatch = perms.canWatchTask;
  const editHint = perms.hint(canEdit);

  const patch = (p: Parameters<typeof updateTask.mutate>[0]["patch"]) =>
    updateTask.mutate({ taskId: task.id, patch: p });

  const toggleWatch = async () => {
    try {
      if (watching) {
        await api.delete(`tasks/${task.id}/watch/`);
      } else {
        await api.post(`tasks/${task.id}/watch/`);
      }
      queryClient.invalidateQueries({ queryKey: keys.task(task.id) });
    } catch (err) {
      toast.error(
        isApiError(err) ? err.message : "Kuzatish holatini yangilab bo'lmadi.",
      );
    }
  };

  return (
    <dl className="grid grid-cols-[110px_1fr] items-center gap-x-4 gap-y-2 px-6 py-4 text-sm">
      <dt className="text-muted-foreground">Holat</dt>
      <dd title={editHint}>
        <StatusPicker
          value={task.status_id}
          statuses={statuses}
          disabled={!canEdit}
          onChange={(statusId) => patch({ status_id: statusId })}
        />
      </dd>

      <dt className="text-muted-foreground">Mas&apos;ullar</dt>
      <dd className="flex flex-wrap items-center gap-1" title={perms.hint(canAssign)}>
        <AssigneePicker
          value={task.assignees}
          members={members?.results ?? []}
          disabled={!canAssign}
          workspaceId={workspaceId}
          canInvite={can(my, "member.invite")}
          onChange={(ids) =>
            updateTask.mutate({
              taskId: task.id,
              patch: { assignee_ids: ids },
              optimistic: { assignees: resolveAssignees(ids, members?.results ?? []) },
            })
          }
        />
        {/* Avatarning o'zi tanlash popoverini ochadi, shuning uchun profilga
            o'tish alohida matnli havola bo'lib turadi. */}
        {task.assignees.map((assignee) => (
          <Link
            key={assignee.id}
            href={`/w/${workspaceId}/u/${assignee.id}`}
            title={`${assignee.full_name || assignee.email} profilini ochish`}
            className="max-w-[9rem] truncate rounded px-1 text-xs text-muted-foreground hover:text-foreground hover:underline"
          >
            {assignee.full_name || assignee.email}
          </Link>
        ))}
      </dd>

      <dt className="text-muted-foreground">Muhimlik</dt>
      <dd title={editHint}>
        <PriorityPicker
          value={task.priority}
          disabled={!canEdit}
          showLabel
          onChange={(p) => patch({ priority: p })}
        />
      </dd>

      <dt className="text-muted-foreground">Muddat</dt>
      <dd title={editHint}>
        <DueDatePicker
          value={task.due_date}
          disabled={!canEdit}
          onChange={(iso) => patch({ due_date: iso })}
        />
      </dd>

      <dt className="text-muted-foreground">Teglar</dt>
      <dd title={editHint}>
        <TagPicker
          value={task.tags}
          tags={tags?.results ?? []}
          disabled={!canEdit}
          onChange={(ids) =>
            updateTask.mutate({
              taskId: task.id,
              patch: { tag_ids: ids },
              optimistic: { tags: resolveTags(ids, tags?.results ?? []) },
            })
          }
        />
      </dd>

      <dt className="text-muted-foreground">Kuzatuvchilar</dt>
      <dd className="flex items-center gap-2">
        <AvatarStack users={task.watchers} max={4} />
        <Button
          variant="ghost"
          size="xs"
          onClick={toggleWatch}
          disabled={!canWatch}
          title={perms.hint(canWatch)}
          className="text-muted-foreground"
        >
          {watching ? (
            <>
              <EyeOff className="size-3.5" /> Kuzatishni to&apos;xtatish
            </>
          ) : (
            <>
              <Eye className="size-3.5" /> Kuzatish
            </>
          )}
        </Button>
      </dd>

    </dl>
  );
}

function DescriptionEditor({
  task,
  listId,
  canEdit,
}: {
  task: Task;
  listId: string;
  canEdit: boolean;
}) {
  const updateTask = useUpdateTask(listId);
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState("");
  const text = richBodyToText(task.description_html);

  const startEdit = () => {
    if (!canEdit) return;
    setDraft(text);
    setEditing(true);
  };

  const commit = () => {
    setEditing(false);
    const trimmed = draft.trim();
    if (trimmed === text) return;
    if (!trimmed) {
      updateTask.mutate({
        taskId: task.id,
        patch: { description_html: null, description_json: null },
      });
      return;
    }
    const { body_html, body_json } = textToRichBody(trimmed);
    // description_html and description_json must travel together (§10.2).
    updateTask.mutate({
      taskId: task.id,
      patch: { description_html: body_html, description_json: body_json },
    });
  };

  return (
    <div className="px-6 py-4">
      <h3 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        Tavsif
      </h3>
      {editing ? (
        <Textarea
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") commit();
            if (e.key === "Escape") setEditing(false);
          }}
          rows={5}
          placeholder="Tavsif qo'shing…"
        />
      ) : text ? (
        <div
          className="cursor-text text-sm whitespace-pre-wrap"
          onClick={startEdit}
          role={canEdit ? "button" : undefined}
        >
          {text}
        </div>
      ) : (
        <button
          className="text-sm text-muted-foreground hover:text-foreground"
          onClick={startEdit}
          disabled={!canEdit}
        >
          {canEdit ? "Tavsif qo'shing…" : "Tavsif yo'q."}
        </button>
      )}
    </div>
  );
}

function PanelSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-6" aria-hidden>
      <Skeleton className="h-7 w-3/5" />
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-48" />
        </div>
      ))}
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-16 w-full" />
    </div>
  );
}
