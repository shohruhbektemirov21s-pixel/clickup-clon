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
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>
              {target.kind === "space" ? "Create a space" : "Create a list"}
            </DialogTitle>
            <DialogDescription>
              {target.kind === "space"
                ? "Spaces group folders and lists."
                : "Lists hold your tasks."}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="entity-name">Name</Label>
            <Input
              id="entity-name"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={target.kind === "space" ? "Product" : "Sprint 1"}
              required
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending || !name.trim()}>
              {pending ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
