"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateList, useCreateSpace } from "@/hooks/mutations";

type CreateTarget =
  | { kind: "space" }
  | { kind: "list"; spaceId: string; folderId?: string | null };

export function CreateEntityDialog({
  workspaceId,
  target,
  onClose,
}: {
  workspaceId: string;
  target: CreateTarget;
  onClose: () => void;
}) {
  const [name, setName] = React.useState("");
  const createSpace = useCreateSpace(workspaceId);
  const createList = useCreateList(workspaceId);
  const pending = createSpace.isPending || createList.isPending;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    try {
      if (target.kind === "space") {
        await createSpace.mutateAsync({ name: trimmed });
      } else {
        await createList.mutateAsync({
          spaceId: target.spaceId,
          name: trimmed,
          folderId: target.folderId ?? null,
        });
      }
      onClose();
    } catch {
      // Xato toast'ini mutatsiyaning o'zi ko'rsatadi. Oynani ochiq
      // qoldiramiz — 403/409 dan keyin foydalanuvchi nomni tuzata olsin va
      // `mutateAsync` ushlanmagan rejection tashlamasin.
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>
              {target.kind === "space" ? "Bo'lim yaratish" : "Ro'yxat yaratish"}
            </DialogTitle>
            <DialogDescription>
              {target.kind === "space"
                ? "Bo'limlar jildlar va ro'yxatlarni jamlaydi."
                : "Ro'yxatlarda vazifalaringiz saqlanadi."}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="entity-name">Nomi</Label>
            <Input
              id="entity-name"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={target.kind === "space" ? "Mahsulot" : "Sprint 1"}
              required
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>
              Bekor qilish
            </Button>
            <Button type="submit" disabled={pending || !name.trim()}>
              {pending ? "Yaratilmoqda…" : "Yaratish"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
