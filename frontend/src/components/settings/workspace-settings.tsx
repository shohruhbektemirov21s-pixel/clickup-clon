"use client";

import * as React from "react";
import Link from "next/link";
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
import {
  useInvitations,
  useMe,
  useMembers,
  useMyPermissions,
  useWorkspace,
} from "@/hooks/queries";
import {
  useChangeMemberRole,
  useRemoveMember,
  useRenameWorkspace,
  useResendInvitation,
  useRevokeInvitation,
} from "@/hooks/mutations";
import { InviteMemberDialog } from "@/components/workspace/invite-member-dialog";
import { displayName, initials, timeAgo } from "@/lib/format";
import { can } from "@/lib/permissions";
import type { Member, Role } from "@/types/api";

import { PROFESSION_LABEL, ROLE_LABEL, ROLE_RANK } from "@/lib/roles";

function SectionSkeleton() {
  return (
    <div className="space-y-2" aria-hidden>
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

/** "Umumiy" — workspace name. Gated on `workspace.update` (owner by default). */
export function GeneralSection({ workspaceId }: { workspaceId: string }) {
  const { data: workspace, isPending } = useWorkspace(workspaceId);
  const { data: my } = useMyPermissions(workspaceId);
  const canRename = can(my, "workspace.update");

  if (isPending) return <SectionSkeleton />;
  if (!workspace) {
    return (
      <p className="text-sm text-muted-foreground">
        Ish maydoni topilmadi yoki sizda endi ruxsat yo&apos;q.
      </p>
    );
  }

  return (
    <GeneralForm
      workspaceId={workspaceId}
      currentName={workspace.name}
      canRename={canRename}
    />
  );
}

function GeneralForm({
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
          disabled={
            !canRename || rename.isPending || !name.trim() || name.trim() === currentName
          }
        >
          {rename.isPending ? "Saqlanmoqda…" : "Saqlash"}
        </Button>
      </form>
      {!canRename ? (
        <p className="mt-1.5 text-xs text-muted-foreground">
          Ish maydoni nomini o&apos;zgartirish uchun ruxsatingiz yo&apos;q.
        </p>
      ) : null}
    </section>
  );
}

/** "A'zolar" — the roster. */
export function MembersSection({ workspaceId }: { workspaceId: string }) {
  const { data, isPending, isError } = useMembers(workspaceId);
  const { data: me } = useMe();
  const { data: my } = useMyPermissions(workspaceId);
  const changeRole = useChangeMemberRole(workspaceId);
  const removeMember = useRemoveMember(workspaceId);

  const myRole: Role = my?.role ?? "guest";
  const canChangeRole = can(my, "member.role_change");
  const canRemove = can(my, "member.remove");

  /**
   * Permission answers *what* is allowed; ROLE_RANK still answers *on whom*
   * (AD-8). Both must pass, exactly like the server.
   */
  const outranks = (target: Member) =>
    target.user.id !== me?.id && ROLE_RANK[target.role] >= ROLE_RANK[myRole];

  const roleOptions = (target: Member): Role[] => {
    if (myRole === "owner") return ["owner", "admin", "member", "guest"];
    return target.role === "owner" ? [] : ["admin", "member", "guest"];
  };

  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground uppercase">
        A&apos;zolar {data ? `(${data.count})` : ""}
      </h2>
      {isPending ? (
        <SectionSkeleton />
      ) : isError ? (
        <p className="text-sm text-danger">A&apos;zolarni yuklab bo&apos;lmadi.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ism</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Kasbi</TableHead>
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
                      {initials(member.user.full_name, member.user.email ?? undefined)}
                    </AvatarFallback>
                  </Avatar>
                  <span className="font-medium">
                    <Link
                      href={`/w/${workspaceId}/u/${member.user.id}`}
                      className="hover:underline"
                      title={`${displayName(member.user)} profilini ochish`}
                    >
                      {displayName(member.user)}
                    </Link>
                    {member.user.id === me?.id ? (
                      <span className="ml-1 text-xs text-muted-foreground">(siz)</span>
                    ) : null}
                  </span>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {/* Mehmon ko'ruvchiga email `null` keladi (§4) — bo'sh katak
                      o'rniga chiziqcha. */}
                  {member.user.email ?? "—"}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {member.user.profession ? (
                    <Badge variant="outline" className="font-normal">
                      {PROFESSION_LABEL[member.user.profession]}
                    </Badge>
                  ) : (
                    "—"
                  )}
                </TableCell>
                <TableCell>
                  {canChangeRole &&
                  outranks(member) &&
                  roleOptions(member).length > 0 ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button
                            variant="outline"
                            size="xs"
                            className="w-24 justify-between"
                          />
                        }
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
                  {canRemove && outranks(member) ? (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      className="text-danger"
                      aria-label={`${member.user.email ?? displayName(member.user)} a'zoni chiqarish`}
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

/** "Takliflar" — pending invitations. */
export function InvitationsSection({ workspaceId }: { workspaceId: string }) {
  const { data: my } = useMyPermissions(workspaceId);
  const canRead = can(my, "invitation.read");
  const canInvite = can(my, "member.invite");
  const canManage = can(my, "invitation.manage");
  const { data, isPending } = useInvitations(workspaceId, canRead);
  const revoke = useRevokeInvitation(workspaceId);
  const resend = useResendInvitation(workspaceId);
  const [inviteOpen, setInviteOpen] = React.useState(false);

  const pending = (data?.results ?? []).filter((i) => i.status === "pending");

  if (!canRead) {
    return (
      <p className="text-sm text-muted-foreground">
        Takliflarni ko&apos;rish uchun ruxsatingiz yo&apos;q.
      </p>
    );
  }

  return (
    <section className="mb-8">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
          Kutilayotgan takliflar ({pending.length})
        </h2>
        {canInvite ? (
          <Button size="sm" onClick={() => setInviteOpen(true)}>
            <MailPlus className="size-3.5" /> Taklif qilish
          </Button>
        ) : null}
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
                  {canManage ? (
                    <>
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
                    </>
                  ) : null}
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
