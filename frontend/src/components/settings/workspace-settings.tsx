"use client";

import * as React from "react";
import { MailPlus, RefreshCw, Trash2, X } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  useRemoveMember,
  useRenameWorkspace,
  useResendInvitation,
  useRevokeInvitation,
} from "@/hooks/mutations";
import { InviteMemberDialog } from "@/components/workspace/invite-member-dialog";
import { initials, timeAgo } from "@/lib/format";
import type { Member, Role } from "@/types/api";

import { ROLE_LABEL } from "@/lib/roles";

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
        Ish maydoni topilmadi yoki sizda endi ruxsat yo&apos;q.
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl overflow-y-auto p-8">
      <h1 className="mb-6 text-xl font-semibold">
        Ish maydoni sozlamalari — {workspace.name}
      </h1>

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
        Umumiy
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
          <Label htmlFor="ws-rename">Ish maydoni nomi</Label>
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
          {rename.isPending ? "Saqlanmoqda…" : "Saqlash"}
        </Button>
      </form>
      {!canRename ? (
        <p className="mt-1.5 text-xs text-muted-foreground">
          Ish maydoni nomini faqat egasi o&apos;zgartira oladi.
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
        A&apos;zolar {data ? `(${data.count})` : ""}
      </h2>
      {isPending ? (
        <div className="space-y-2" aria-hidden>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-danger">A&apos;zolarni yuklab bo&apos;lmadi.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ism</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Rol</TableHead>
              <TableHead>Qo&apos;shilgan</TableHead>
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
                      <span className="ml-1 text-xs text-muted-foreground">(siz)</span>
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
                      aria-label={`${member.user.email} a'zoni chiqarish`}
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
          Kutilayotgan takliflar ({pending.length})
        </h2>
        <Button size="sm" onClick={() => setInviteOpen(true)}>
          <MailPlus className="size-3.5" /> Taklif qilish
        </Button>
      </div>
      {isPending ? (
        <Skeleton className="h-16 w-full" aria-hidden />
      ) : pending.length === 0 ? (
        <p className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
          Kutilayotgan takliflar yo&apos;q.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Rol</TableHead>
              <TableHead>Taklif qilgan</TableHead>
              <TableHead>Muddati</TableHead>
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
                    aria-label="Taklifni qayta yuborish"
                    disabled={resend.isPending}
                    onClick={() => resend.mutate(invitation.id)}
                  >
                    <RefreshCw />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    className="text-danger"
                    aria-label="Taklifni bekor qilish"
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
      <InviteMemberDialog
        workspaceId={workspaceId}
        open={inviteOpen}
        onOpenChange={setInviteOpen}
      />
    </section>
  );
}

