"use client";

import Link from "next/link";
import { Users } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyPermissions, useSpaceMembers } from "@/hooks/queries";
import { displayName, initials } from "@/lib/format";
import { spacePermissionGate } from "@/lib/permissions";
import { SPACE_ACCESS_LABEL } from "@/lib/roles";

const MAX_AVATARS = 5;

/**
 * The space's team in a list header: overlapping avatars plus a "Jamoa" button.
 *
 * The button appears only for `space.manage_members` holders or a local
 * `manager` — everyone else who can see the space still sees *who* is on it,
 * read-only. That split mirrors §D.6 exactly: reading the roster needs no
 * permission code, changing it does.
 *
 * Ikkala so'rov ham yo'lda ekan, strip **skeleton** ko'rsatadi. Ilgari u
 * shunchaki `null` qaytarardi va javoblar kelgach sarlavhaga birdan
 * "sakrab" kirardi — yonidagi ulanish belgisini surib yuborib.
 */
export function SpaceTeamStrip({
  workspaceId,
  spaceId,
}: {
  workspaceId: string;
  spaceId: string | null | undefined;
}) {
  const { data: my, isPending: permsPending } = useMyPermissions(workspaceId);
  const { data, isPending: rowsPending } = useSpaceMembers(spaceId ?? null);

  if (!spaceId) return null;

  const manage = spacePermissionGate(my, permsPending, spaceId, "space.manage_members");

  // Javob noma'lum ekan, o'lchami barqaror joy band qilinadi.
  if (manage.isLoading || rowsPending) return <StripSkeleton />;

  const rows = data?.results ?? [];
  const canManage = manage.allowed;
  if (rows.length === 0 && !canManage) return null;

  const shown = rows.slice(0, MAX_AVATARS);
  const overflow = rows.length - shown.length;

  return (
    <div className="flex items-center gap-1.5">
      {/* Rolsiz <div> dagi `aria-label` ni ba'zi ekran o'quvchilari o'qimaydi. */}
      <div className="flex -space-x-1.5" role="group" aria-label="Bo'lim jamoasi">
        {shown.map((row) => {
          // Mehmon ko'ruvchiga `email` `null` keladi (§4) — "null — Ko'ruvchi"
          // ko'rinmasin.
          const label = `${displayName(row.user)} — ${SPACE_ACCESS_LABEL[row.access]}`;
          return (
            <Avatar
              key={row.id}
              className="size-6 ring-2 ring-background"
              // `role="img"` ichidagi bosh harflarni yashiradi va o'rniga
              // to'liq ismni e'lon qiladi.
              role="img"
              aria-label={label}
              title={label}
            >
              {row.user.avatar ? <AvatarImage src={row.user.avatar} alt="" /> : null}
              <AvatarFallback
                className="text-[9px] font-semibold text-primary-foreground"
                style={{ backgroundColor: row.user.avatar_color || "#7B68EE" }}
              >
                {initials(row.user.full_name, row.user.email ?? undefined)}
              </AvatarFallback>
            </Avatar>
          );
        })}
        {overflow > 0 ? (
          <span className="flex size-6 items-center justify-center rounded-full bg-muted text-[9px] font-semibold ring-2 ring-background">
            <span aria-hidden>+{overflow}</span>
            <span className="sr-only">yana {overflow} ta a&apos;zo</span>
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

/**
 * Uchta avatar o'rni — eng keng tarqalgan holatning o'lchami. "Jamoa"
 * tugmasining joyi ataylab band qilinmaydi: uni ko'rmaydigan foydalanuvchida
 * skeleton yo'qolib, yana surilish bo'lardi.
 */
function StripSkeleton() {
  return (
    <div className="flex -space-x-1.5" aria-hidden>
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="size-6 rounded-full ring-2 ring-background" />
      ))}
    </div>
  );
}
