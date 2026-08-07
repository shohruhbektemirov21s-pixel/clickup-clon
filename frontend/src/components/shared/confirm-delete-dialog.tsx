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

/**
 * Shared destructive-confirmation dialog. Nothing in the app deletes without
 * going through this. `requireNameMatch` implements the contract's
 * `confirm_name` guard (spaces, workspaces).
 */
export function ConfirmDeleteDialog({
  open,
  onOpenChange,
  entityName,
  warning,
  requireNameMatch = false,
  pending = false,
  confirmLabel = "O'chirish",
  children,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entityName: string;
  warning: string;
  requireNameMatch?: boolean;
  pending?: boolean;
  confirmLabel?: string;
  children?: React.ReactNode;
  onConfirm: () => void;
}) {
  const [typed, setTyped] = React.useState("");

  // Reset the typed confirmation whenever the dialog is reopened.
  const [lastOpen, setLastOpen] = React.useState(open);
  if (open !== lastOpen) {
    setLastOpen(open);
    if (open) setTyped("");
  }

  const nameOk = !requireNameMatch || typed === entityName;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Rostdan ham o&apos;chirasizmi?</DialogTitle>
          <DialogDescription>
            <span className="font-medium text-foreground">{entityName}</span> —{" "}
            {warning} Bu amalni ortga qaytarib bo&apos;lmaydi.
          </DialogDescription>
        </DialogHeader>

        {children}

        {requireNameMatch ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="confirm-name">
              Tasdiqlash uchun nomini kiriting: <b>{entityName}</b>
            </Label>
            <Input
              id="confirm-name"
              autoFocus
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={entityName}
              autoComplete="off"
            />
          </div>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Bekor qilish
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={pending || !nameOk}
            onClick={onConfirm}
          >
            {pending ? "O'chirilmoqda…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
