"use client";

import Link from "next/link";
import { Users } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useMyPermissions, useSpaceMembers } from "@/hooks/queries";
import { initials } from "@/lib/format";
import { canInSpace } from "@/lib/permissions";
import { SPACE_ACCESS_LABEL } from "@/lib/roles";

const MAX_AVATARS = 5;

/**
 * The space's team in a list header: overlapping avatars plus a "Jamoa" button.
 *
 * The button appears only for `space.manage_members` holders or a local
 * `manager` — everyone else who can see the space still sees *who* is on it,
 * read-only. That split mirrors §D.6 exactly: reading the roster needs no
 * permission code, changing it does.
 */
export function SpaceTeamStrip({
  workspaceId,
  spaceId,
}: {
  workspaceId: string;
  spaceId: string | null | undefined;
}) {
  const { data: my } = useMyPermissions(workspaceId);
  const { data } = useSpaceMembers(spaceId ?? null);

  if (!spaceId) return null;

  const rows = data?.results ?? [];
  const canManage = canInSpace(my, spaceId, "space.manage_members");
  if (rows.length === 0 && !canManage) return null;

  const shown = rows.slice(0, MAX_AVATARS);
  const overflow = rows.length - shown.length;

  return (
    <div className="flex items-center gap-1.5">
      <div className="flex -space-x-1.5" aria-label="Bo'lim jamoasi">
        {shown.map((row) => (
          <Avatar
            key={row.id}
            className="size-6 ring-2 ring-background"
            title={`${row.user.full_name || row.user.email} — ${SPACE_ACCESS_LABEL[row.access]}`}
          >
            {row.user.avatar ? <AvatarImage src={row.user.avatar} alt="" /> : null}
            <AvatarFallback
              className="text-[9px] font-semibold text-primary-foreground"
              style={{ backgroundColor: row.user.avatar_color || "#7B68EE" }}
            >
              {initials(row.user.full_name, row.user.email ?? undefined)}
            </AvatarFallback>
          </Avatar>
        ))}
        {overflow > 0 ? (
          <span className="flex size-6 items-center justify-center rounded-full bg-muted text-[9px] font-semibold ring-2 ring-background">
            +{overflow}
          </span>
        ) : null}
      </div>
      {canManage ? (
        <Button
          variant="ghost"
          size="xs"
          render={<Link href={`/w/${workspaceId}/s/${spaceId}/members`} />}
        >
          <Users className="size-3.5" /> Jamoa
        </Button>
      ) : null}
    </div>
  );
}
