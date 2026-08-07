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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useCreateInvitation } from "@/hooks/mutations";
import { ROLE_LABEL } from "@/lib/roles";
import type { InvitableRole } from "@/types/api";

/**
 * Single implementation of "Jamoaga qo'shish" — used by both the workspace
 * settings page and the sidebar JAMOA section. Posts to
 * `POST workspaces/{id}/invitations/` per contract §5.
 */
export function InviteMemberDialog({
  workspaceId,
  open,
  onOpenChange,
}: {
  workspaceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createInvitation = useCreateInvitation(workspaceId);
  const [email, setEmail] = React.useState("");
  const [role, setRole] = React.useState<InvitableRole>("member");

  // Reset the form each time the dialog is opened.
  const [lastOpen, setLastOpen] = React.useState(open);
  if (open !== lastOpen) {
    setLastOpen(open);
    if (open) {
      setEmail("");
      setRole("member");
    }
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) return;
    try {
      await createInvitation.mutateAsync({ email: trimmed, role });
      onOpenChange(false);
    } catch {
      // Error toast is raised by the mutation; keep the dialog open so the
      // user can correct the address.
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Jamoaga qo&apos;shish</DialogTitle>
            <DialogDescription>
              Ularga ish maydoniga qo&apos;shilish havolasi emailda yuboriladi.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="invite-email">Email manzili</Label>
            <Input
              id="invite-email"
              type="email"
              autoFocus
              placeholder="yangi.dev@kompaniya.uz"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Rol</Label>
            <RadioGroup
              value={role}
              onValueChange={(v) => setRole(v as InvitableRole)}
              className="flex gap-4"
            >
              {(["admin", "member", "guest"] as const).map((r) => (
                <label key={r} className="flex items-center gap-1.5 text-sm">
                  <RadioGroupItem value={r} /> {ROLE_LABEL[r]}
                </label>
              ))}
            </RadioGroup>
            <p className="text-xs text-muted-foreground">
              Mehmonlar o&apos;qishi va komment yozishi mumkin, lekin ro&apos;yxat
              yarata olmaydi.
            </p>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Bekor qilish
            </Button>
            <Button type="submit" disabled={createInvitation.isPending || !email.trim()}>
              {createInvitation.isPending ? "Yuborilmoqda…" : "Taklif yuborish"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
