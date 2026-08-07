"use client";

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
import { cn } from "@/lib/utils";

/**
 * "…" menu for a task (list row + task panel). Delete is a soft delete per
 * contract §10.2 and always goes through the confirmation dialog.
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
  canDelete: boolean;
  className?: string;
  onDeleted?: () => void;
}) {
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const deleteTask = useDeleteTask(listId);

  if (!canDelete) return null;

  const onConfirm = async () => {
    await deleteTask.mutateAsync(taskId);
    setConfirmOpen(false);
    onDeleted?.();
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
            O&apos;chirish
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <ConfirmDeleteDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        entityName={taskTitle}
        warning="vazifasi va uning kommentlari o'chiriladi."
        pending={deleteTask.isPending}
        onConfirm={onConfirm}
      />
    </>
  );
}
