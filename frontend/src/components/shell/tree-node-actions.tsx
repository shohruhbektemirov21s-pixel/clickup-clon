"use client";

import * as React from "react";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { ConfirmDeleteDialog } from "@/components/shared/confirm-delete-dialog";
import {
  useDeleteFolder,
  useDeleteList,
  useDeleteSpace,
  useRenameEntity,
  type FolderDeleteStrategy,
} from "@/hooks/mutations";

export type TreeEntityKind = "space" | "folder" | "list";

const KIND_LABEL: Record<TreeEntityKind, string> = {
  space: "Bo'lim",
  folder: "Jild",
  list: "Ro'yxat",
};

const DELETE_WARNING: Record<TreeEntityKind, string> = {
  space: "ichidagi barcha jildlar, ro'yxatlar va vazifalar bilan birga o'chiriladi.",
  folder: "o'chiriladi.",
  list: "barcha vazifalari va kommentlari bilan birga o'chiriladi.",
};

/**
 * Hover "…" menu on a sidebar tree row: rename + delete.
 * Role gating follows the contract: spaces are admin+, folders/lists member+,
 * and the folder `cascade` strategy is admin+ while `detach` is member+.
 */
export function TreeNodeActions({
  workspaceId,
  kind,
  id,
  name,
  canManage,
  canCascade,
  onDeleted,
}: {
  workspaceId: string;
  kind: TreeEntityKind;
  id: string;
  name: string;
  canManage: boolean;
  canCascade: boolean;
  onDeleted?: () => void;
}) {
  const [renameOpen, setRenameOpen] = React.useState(false);
  const [deleteOpen, setDeleteOpen] = React.useState(false);
  const [draftName, setDraftName] = React.useState(name);
  const [strategy, setStrategy] = React.useState<FolderDeleteStrategy>(
    canCascade ? "cascade" : "detach",
  );

  const rename = useRenameEntity(workspaceId);
  const deleteSpace = useDeleteSpace(workspaceId);
  const deleteFolder = useDeleteFolder(workspaceId);
  const deleteList = useDeleteList(workspaceId);

  const deleting =
    deleteSpace.isPending || deleteFolder.isPending || deleteList.isPending;

  if (!canManage) return null;

  const onRenameSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = draftName.trim();
    if (!trimmed || trimmed === name) {
      setRenameOpen(false);
      return;
    }
    await rename.mutateAsync({ kind, id, name: trimmed });
    setRenameOpen(false);
  };

  const onDeleteConfirm = async () => {
    if (kind === "space") {
      await deleteSpace.mutateAsync({ id, confirmName: name });
    } else if (kind === "folder") {
      await deleteFolder.mutateAsync({ id, strategy });
    } else {
      await deleteList.mutateAsync(id);
    }
    setDeleteOpen(false);
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
              className="opacity-0 group-hover:opacity-100 aria-expanded:opacity-100 data-[popup-open]:opacity-100"
              aria-label={`${name} — amallar`}
              onClick={(e) => e.preventDefault()}
            />
          }
        >
          <MoreHorizontal />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-52">
          <DropdownMenuItem
            onClick={() => {
              setDraftName(name);
              setRenameOpen(true);
            }}
          >
            <Pencil className="size-4" />
            Nomini o&apos;zgartirish
          </DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="size-4" />
            O&apos;chirish
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent className="sm:max-w-sm">
          <form onSubmit={onRenameSubmit} className="flex flex-col gap-4">
            <DialogHeader>
              <DialogTitle>{KIND_LABEL[kind]} nomini o&apos;zgartirish</DialogTitle>
            </DialogHeader>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`rename-${id}`}>Nomi</Label>
              <Input
                id={`rename-${id}`}
                autoFocus
                value={draftName}
                onChange={(e) => setDraftName(e.target.value)}
                required
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setRenameOpen(false)}>
                Bekor qilish
              </Button>
              <Button type="submit" disabled={rename.isPending || !draftName.trim()}>
                {rename.isPending ? "Saqlanmoqda…" : "Saqlash"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        entityName={name}
        warning={DELETE_WARNING[kind]}
        // Spaces require the exact name per contract §6 (`confirm_name`).
        requireNameMatch={kind === "space"}
        pending={deleting}
        onConfirm={onDeleteConfirm}
      >
        {kind === "folder" ? (
          <div className="flex flex-col gap-2">
            <Label>Ro&apos;yxatlar bilan nima qilinsin?</Label>
            <RadioGroup
              value={strategy}
              onValueChange={(v) => setStrategy(v as FolderDeleteStrategy)}
              className="gap-2"
            >
              <label className="flex items-start gap-2 text-sm">
                <RadioGroupItem value="cascade" className="mt-0.5" disabled={!canCascade} />
                <span>
                  Ichidagilari bilan o&apos;chirish
                  {!canCascade ? (
                    <span className="block text-xs text-muted-foreground">
                      Faqat admin yoki ega uchun
                    </span>
                  ) : null}
                </span>
              </label>
              <label className="flex items-start gap-2 text-sm">
                <RadioGroupItem value="detach" className="mt-0.5" />
                <span>Ro&apos;yxatlarni bo&apos;limga chiqarish</span>
              </label>
            </RadioGroup>
          </div>
        ) : null}
      </ConfirmDeleteDialog>
    </>
  );
}
