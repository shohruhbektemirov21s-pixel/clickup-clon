import * as React from "react";
import { MoreHorizontal, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ConfirmDeleteDialog } from "@/components/shared/confirm-delete-dialog";
import { useDeleteTask } from "@/hooks/mutations";
import { COMMON, TASK } from "@/i18n/uz";
import { cn } from "@/lib/utils";

/**
 * "…" menu for a task (list row + task panel). Delete is a soft delete per
 * contract §10.2 and always goes through the confirmation dialog.
 *
 * `canDelete` **must** come from the `task.delete` code, not from a role and
 * not from "can I edit this task": the server has no own-task exception for
 * deletion (`TaskDetailView.delete` → `require_space_perm(…, "task.delete")`).
 */
export function TaskActionsMenu({
  listId,
  taskId,
  taskTitle,
  canDelete,
  className,
  onDeleted,
}: {
  listId: string;
  taskId: string;
  taskTitle: string;
  /** `task.delete`, bo'lim doirasida hal qilingan. */
  canDelete: boolean;
  className?: string;
  onDeleted?: () => void;
}) {
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const deleteTask = useDeleteTask(listId);

  if (!canDelete) return null;

  /**
   * `ConfirmDeleteDialog.onConfirm` `() => void` — qaytgan promise tashlab
   * yuboriladi, shuning uchun bu funksiya HECH QACHON reject qilmasligi
   * kerak. Aks holda 403/404/409 da dialog ochiq qolib, konsolga
   * "unhandled rejection" tushardi (`invite-member-dialog` dagi naqsh).
   */
  const onConfirm = async () => {
    try {
      await deleteTask.mutateAsync(taskId);
      setConfirmOpen(false);
      onDeleted?.();
    } catch {
      // Xato toast'i mutatsiyadan chiqadi; dialog ochiq qoladi, chunki
      // 409 (masalan, allaqachon o'chirilgan) qayta urinishga arziydi.
    }
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon-xs"
              className={cn("text-muted-foreground", className)}
              aria-label={`${taskTitle} — amallar`}
            />
          }
        >
          <MoreHorizontal />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuItem variant="destructive" onClick={() => setConfirmOpen(true)}>
            <Trash2 className="size-4" />
            {COMMON.delete}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <ConfirmDeleteDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        entityName={taskTitle}
        warning={TASK.deleteWarning}
        pending={deleteTask.isPending}
        onConfirm={onConfirm}
      />
    </>
  );
}
