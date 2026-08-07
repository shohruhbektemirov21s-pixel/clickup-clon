"use client";

import * as React from "react";
import { MailPlus, RefreshCw, Trash2, X } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useInvitations, useMe, useMembers, useWorkspace } from "@/hooks/queries";
import {
  useChangeMemberRole,
  useCreateInvitation,
  useRemoveMember,
  useRenameWorkspace,
  useResendInvitation,
  useRevokeInvitation,
} from "@/hooks/mutations";
import { initials, timeAgo } from "@/lib/format";
import type { InvitableRole, Member, Role } from "@/types/api";

const ROLE_LABEL: Record<Role, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  guest: "Guest",
};

export function WorkspaceSettings({ workspaceId }: { workspaceId: string }) {
  const { data: workspace, isPending } = useWorkspace(workspaceId);
  const myRole = workspace?.my_role;
  const isAdmin = myRole === "owner" || myRole === "admin";

  if (isPending) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4 p-8" aria-hidden>
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!workspace) {
    return (
      <div className="flex flex-1 items-center justify-center p-12 text-sm text-muted-foreground">
        Workspace not found or you no longer have access.
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl overflow-y-auto p-8">
      <h1 className="mb-6 text-xl font-semibold">Workspace settings — {workspace.name}</h1>

      <GeneralSection
        workspaceId={workspaceId}
        currentName={workspace.name}
        canRename={isAdmin && myRole === "owner"}
      />

      {myRole !== "guest" ? (
        <MembersSection workspaceId={workspaceId} myRole={myRole ?? "member"} />
      ) : null}

      {isAdmin ? <InvitationsSection workspaceId={workspaceId} /> : null}
    </div>
  );
}

function GeneralSection({
  workspaceId,
  currentName,
  canRename,
}: {
  workspaceId: string;
  currentName: string;
  canRename: boolean;
}) {
  const rename = useRenameWorkspace(workspaceId);
  const [name, setName] = React.useState(currentName);
  const [lastName, setLastName] = React.useState(currentName);
  // Sync when the server value changes (render-time adjustment, not an effect).
  if (currentName !== lastName) {
    setLastName(currentName);
    setName(currentName);
  }

  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground uppercase">
        General
      </h2>
      <form
        className="flex max-w-md items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const trimmed = name.trim();
          if (trimmed && trimmed !== currentName) rename.mutate({ name: trimmed });
        }}
      >
        <div className="flex flex-1 flex-col gap-1.5">
          <Label htmlFor="ws-rename">Workspace name</Label>
          <Input
            id="ws-rename"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!canRename}
          />
        </div>
        <Button
          type="submit"
          disabled={!canRename || rename.isPending || !name.trim() || name.trim() === currentName}
        >
          {rename.isPending ? "Saving…" : "Save"}
        </Button>
      </form>
      {!canRename ? (
        <p className="mt-1.5 text-xs text-muted-foreground">
          Only the workspace owner can rename this workspace.
        </p>
      ) : null}
    </section>
  );
}

function MembersSection({
  workspaceId,
  myRole,
}: {
  workspaceId: string;
  myRole: Role;
}) {
  const { data, isPending, isError } = useMembers(workspaceId);
  const { data: me } = useMe();
  const changeRole = useChangeMemberRole(workspaceId);
  const removeMember = useRemoveMember(workspaceId);
  const isAdmin = myRole === "owner" || myRole === "admin";

  const canManage = (target: Member): boolean => {
    if (!isAdmin) return false;
    if (target.user.id === me?.id) return false; // never manage yourself here
    if (target.role === "owner") return myRole === "owner";
    return true;
  };

  const roleOptions = (target: Member): Role[] => {
    if (myRole === "owner") return ["owner", "admin", "member", "guest"];
    // Admins may change roles among admin/member/guest for non-owners.
    return target.role === "owner" ? [] : ["admin", "member", "guest"];
  };

  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground uppercase">
        Members {data ? `(${data.count})` : ""}
      </h2>
      {isPending ? (
        <div className="space-y-2" aria-hidden>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-danger">Couldn&apos;t load members.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Joined</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data?.results ?? []).map((member) => (
              <TableRow key={member.id}>
                <TableCell className="flex items-center gap-2">
                  <Avatar className="size-6">
                    {member.user.avatar ? (
                      <AvatarImage src={member.user.avatar} alt="" />
                    ) : null}
                    <AvatarFallback
                      className="text-[10px] font-semibold text-primary-foreground"
                      style={{ backgroundColor: member.user.avatar_color || "#7B68EE" }}
                    >
                      {initials(member.user.full_name, member.user.email)}
                    </AvatarFallback>
                  </Avatar>
                  <span className="font-medium">
                    {member.user.full_name || member.user.email}
                    {member.user.id === me?.id ? (
                      <span className="ml-1 text-xs text-muted-foreground">(you)</span>
                    ) : null}
                  </span>
                </TableCell>
                <TableCell className="text-muted-foreground">{member.user.email}</TableCell>
                <TableCell>
                  {canManage(member) && roleOptions(member).length > 0 ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={<Button variant="outline" size="xs" className="w-24 justify-between" />}
                      >
                        {ROLE_LABEL[member.role]}
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start">
                        {roleOptions(member).map((role) => (
                          <DropdownMenuItem
                            key={role}
                            onClick={() =>
                              role !== member.role &&
                              changeRole.mutate({ userId: member.user.id, role })
                            }
                          >
                            {ROLE_LABEL[role]}
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : (
                    <Badge variant="secondary">{ROLE_LABEL[member.role]}</Badge>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {timeAgo(member.joined_at)}
                </TableCell>
                <TableCell>
                  {canManage(member) ? (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      className="text-danger"
                      aria-label={`Remove ${member.user.email}`}
                      onClick={() => removeMember.mutate(member.user.id)}
                    >
                      <Trash2 />
                    </Button>
                  ) : null}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}

function InvitationsSection({ workspaceId }: { workspaceId: string }) {
  const { data, isPending } = useInvitations(workspaceId, true);
  const revoke = useRevokeInvitation(workspaceId);
  const resend = useResendInvitation(workspaceId);
  const [inviteOpen, setInviteOpen] = React.useState(false);

  const pending = (data?.results ?? []).filter((i) => i.status === "pending");

  return (
    <section className="mb-8">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
          Pending invitations ({pending.length})
        </h2>
        <Button size="sm" onClick={() => setInviteOpen(true)}>
          <MailPlus className="size-3.5" /> Invite
        </Button>
      </div>
      {isPending ? (
        <Skeleton className="h-16 w-full" aria-hidden />
      ) : pending.length === 0 ? (
        <p className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
          No pending invitations.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Invited by</TableHead>
              <TableHead>Expires</TableHead>
              <TableHead className="w-20" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {pending.map((invitation) => (
              <TableRow key={invitation.id}>
                <TableCell className="font-medium">{invitation.email}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{ROLE_LABEL[invitation.role]}</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {invitation.invited_by.full_name || invitation.invited_by.email}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {timeAgo(invitation.expires_at)}
                </TableCell>
                <TableCell className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label="Resend invitation"
                    disabled={resend.isPending}
                    onClick={() => resend.mutate(invitation.id)}
                  >
                    <RefreshCw />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    className="text-danger"
                    aria-label="Revoke invitation"
                    disabled={revoke.isPending}
                    onClick={() => revoke.mutate(invitation.id)}
                  >
                    <X />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {inviteOpen ? (
        <InviteDialog workspaceId={workspaceId} onClose={() => setInviteOpen(false)} />
      ) : null}
    </section>
  );
}

function InviteDialog({
  workspaceId,
  onClose,
}: {
  workspaceId: string;
  onClose: () => void;
}) {
  const createInvitation = useCreateInvitation(workspaceId);
  const [email, setEmail] = React.useState("");
  const [role, setRole] = React.useState<InvitableRole>("member");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) return;
    await createInvitation.mutateAsync({ email: trimmed, role });
    onClose();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Invite people</DialogTitle>
            <DialogDescription>
              They&apos;ll receive an email with a link to join this workspace.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="invite-email">Email address</Label>
            <Input
              id="invite-email"
              type="email"
              autoFocus
              placeholder="new.dev@acme.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Role</Label>
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
              Guests can read and comment, but can&apos;t create lists.
            </p>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={createInvitation.isPending || !email.trim()}>
              {createInvitation.isPending ? "Sending…" : "Send invite"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
