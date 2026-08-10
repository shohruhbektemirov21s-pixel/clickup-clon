"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, Check, Lock, Search, UserPlus, Users, X } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useMembers,
  useMyPermissions,
  useSpaceMembers,
  useWorkspaceTree,
} from "@/hooks/queries";
import { useBulkSpaceMembers } from "@/hooks/mutations";
import { initials } from "@/lib/format";
import { canInSpace } from "@/lib/permissions";
import { PROFESSION_LABEL, SPACE_ACCESS_LABEL } from "@/lib/roles";
import { cn } from "@/lib/utils";
import type { Member, SpaceAccess, SpaceMember, UserSummary } from "@/types/api";

/** Select order — least privilege first, so the safe choice is the near one. */
const ACCESS_OPTIONS: SpaceAccess[] = ["viewer", "contributor", "manager"];

/** One line of help per level; "PM" and "faqat ko'radi" do the work. */
const ACCESS_HINT: Record<SpaceAccess, string> = {
  viewer: "Faqat ko'radi — bo'lim ichida hech narsa yoza olmaydi.",
  contributor: "Ish maydonidagi roli bo'yicha ishlaydi.",
  manager: "Loyiha menejeri — shu bo'lim ichida jamoani va mazmunni boshqaradi.",
};

function UserCell({ user, subtitle }: { user: UserSummary; subtitle?: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <Avatar className="size-7 shrink-0">
        {user.avatar ? <AvatarImage src={user.avatar} alt="" /> : null}
        <AvatarFallback
          className="text-[10px] font-semibold text-primary-foreground"
          style={{ backgroundColor: user.avatar_color || "#7B68EE" }}
        >
          {initials(user.full_name, user.email ?? undefined)}
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{user.full_name || user.email}</p>
        <p className="truncate text-xs text-muted-foreground">{subtitle ?? user.email}</p>
      </div>
    </div>
  );
}

function AccessSelect({
  value,
  onChange,
  label,
}: {
  value: SpaceAccess;
  onChange: (access: SpaceAccess) => void;
  label: string;
}) {
  return (
    <Select
      items={SPACE_ACCESS_LABEL}
      value={value}
      onValueChange={(next) => next && onChange(next as SpaceAccess)}
    >
      <SelectTrigger size="sm" className="w-[132px]" aria-label={label}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {ACCESS_OPTIONS.map((access) => (
          <SelectItem key={access} value={access}>
            {SPACE_ACCESS_LABEL[access]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function PanelSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2" aria-hidden>
      {[0, 1].map((pane) => (
        <div key={pane} className="space-y-2 rounded-xl border p-4">
          <Skeleton className="h-5 w-32" />
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-11 w-full" />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * `/w/{workspaceId}/s/{spaceId}/members` — the PM panel (§D.6 / §E.3).
 *
 * Left: the workspace roster with a search box. Right: this space's team, one
 * `access` select per person. Every edit is **staged locally** and committed by
 * a single `POST members/bulk/`, which the server runs in one transaction — so
 * a half-applied team is impossible even when one row is rejected.
 *
 * Gating mirrors the server: `space.manage_members` (workspace role) OR a local
 * `manager` row. Everyone else who can see the space gets the same list
 * read-only — the panel never hides *who* is on the team, only who may change it.
 */
export function SpaceMembersPanel({
  workspaceId,
  spaceId,
}: {
  workspaceId: string;
  spaceId: string;
}) {
  const { data: my } = useMyPermissions(workspaceId);
  const { data: tree } = useWorkspaceTree(workspaceId);
  const roster = useMembers(workspaceId);
  const spaceMembers = useSpaceMembers(spaceId);
  const bulk = useBulkSpaceMembers(spaceId);

  const [query, setQuery] = React.useState("");
  /** Desired final roster: `user_id → access`. `null` = untouched since load. */
  const [draft, setDraft] = React.useState<Record<string, SpaceAccess> | null>(null);

  const canManage = canInSpace(my, spaceId, "space.manage_members");
  const space = tree?.spaces.find((s) => s.id === spaceId);

  const serverRows: SpaceMember[] = React.useMemo(
    () => spaceMembers.data?.results ?? [],
    [spaceMembers.data],
  );
  const serverState = React.useMemo(() => {
    const map: Record<string, SpaceAccess> = {};
    for (const row of serverRows) map[row.user.id] = row.access;
    return map;
  }, [serverRows]);

  // The draft is dropped whenever a save lands, so a concurrent change by
  // another PM is never silently kept on top of stale data.
  const current = draft ?? serverState;

  const rowByUser = React.useMemo(() => {
    const map = new Map<string, SpaceMember>();
    for (const row of serverRows) map.set(row.user.id, row);
    return map;
  }, [serverRows]);

  const userById = React.useMemo(() => {
    const map = new Map<string, UserSummary>();
    for (const member of roster.data?.results ?? []) map.set(member.user.id, member.user);
    for (const row of serverRows) map.set(row.user.id, row.user);
    return map;
  }, [roster.data, serverRows]);

  const { add, remove } = React.useMemo(() => {
    const added = Object.entries(current)
      .filter(([userId, access]) => serverState[userId] !== access)
      .map(([user_id, access]) => ({ user_id, access }));
    const removed = Object.keys(serverState).filter((userId) => !(userId in current));
    return { add: added, remove: removed };
  }, [current, serverState]);
  const dirty = add.length > 0 || remove.length > 0;

  const setAccess = (userId: string, access: SpaceAccess) =>
    setDraft({ ...current, [userId]: access });

  const removeUser = (userId: string) => {
    const next = { ...current };
    delete next[userId];
    setDraft(next);
  };

  const candidates: Member[] = React.useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (roster.data?.results ?? []).filter(
      (member) =>
        !needle ||
        member.user.full_name.toLowerCase().includes(needle) ||
        (member.user.email?.toLowerCase().includes(needle) ?? false),
    );
  }, [roster.data, query]);

  const team = React.useMemo(
    () =>
      Object.keys(current)
        .map((userId) => ({ userId, user: userById.get(userId) }))
        .sort((a, b) =>
          (a.user?.full_name || a.user?.email || a.userId).localeCompare(
            b.user?.full_name || b.user?.email || b.userId,
          ),
        ),
    [current, userById],
  );

  const save = () => bulk.mutate({ add, remove }, { onSuccess: () => setDraft(null) });

  if (spaceMembers.isPending || roster.isPending) {
    return (
      <div className="mx-auto w-full max-w-5xl p-8">
        <PanelSkeleton />
      </div>
    );
  }

  if (spaceMembers.isError) {
    // 404 is the honest answer for an invisible space — never reveal it exists.
    return (
      <div className="mx-auto w-full max-w-5xl p-8">
        <p className="text-sm text-muted-foreground">
          Bu bo&apos;lim topilmadi yoki sizda unga kirish huquqi yo&apos;q.
        </p>
        <Button
          variant="outline"
          size="sm"
          className="mt-3"
          render={<Link href={`/w/${workspaceId}`} />}
        >
          <ArrowLeft className="size-3.5" /> Ish maydoniga qaytish
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-5xl p-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <Link
            href={`/w/${workspaceId}`}
            className="mb-1 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-3" /> Ish maydoni
          </Link>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            {space ? (
              <span
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: space.color || "#7B68EE" }}
              />
            ) : null}
            <span className="truncate">{space?.name ?? "Bo'lim"}</span>
            <span className="font-normal text-muted-foreground">— jamoa</span>
            {space?.is_private ? (
              <Badge variant="secondary" className="gap-1">
                <Lock className="size-3" /> Yopiq
              </Badge>
            ) : null}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {canManage
              ? "Loyihaga mos odamlarni tanlang va ularning darajasini belgilang."
              : "Bu bo'limda kim ishlayapti. O'zgartirish uchun bo'lim menejeriga murojaat qiling."}
          </p>
        </div>

        {canManage ? (
          <div className="flex items-center gap-2">
            {dirty ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setDraft(null)}
                disabled={bulk.isPending}
              >
                Bekor qilish
              </Button>
            ) : null}
            <Button size="sm" onClick={save} disabled={!dirty || bulk.isPending}>
              <Check className="size-3.5" />
              {bulk.isPending ? "Saqlanmoqda…" : "Saqlash"}
            </Button>
          </div>
        ) : null}
      </div>

      {dirty ? (
        <p className="mb-4 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-xs text-muted-foreground">
          Saqlanmagan o&apos;zgarishlar: {add.length} ta qo&apos;shish/o&apos;zgartirish,{" "}
          {remove.length} ta olib tashlash.
        </p>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        {/* ------------------------------------------------- workspace roster */}
        <section className="rounded-xl border">
          <header className="flex items-center gap-2 border-b px-4 py-3">
            <Users className="size-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold">Ish maydoni a&apos;zolari</h2>
            <span className="ml-auto text-xs text-muted-foreground">
              {candidates.length}
            </span>
          </header>
          <div className="border-b p-3">
            <div className="relative">
              <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ism yoki email bo'yicha qidirish"
                className="pl-8"
                aria-label="Ish maydoni a'zolarini qidirish"
              />
            </div>
          </div>
          <ul className="max-h-[26rem] overflow-y-auto">
            {candidates.length === 0 ? (
              <li className="px-4 py-6 text-center text-sm text-muted-foreground">
                Mos a&apos;zo topilmadi.
              </li>
            ) : (
              candidates.map((member) => {
                const inSpace = member.user.id in current;
                return (
                  <li
                    key={member.id}
                    className="flex items-center gap-3 border-b px-4 py-2.5 last:border-b-0"
                  >
                    <div className="min-w-0 flex-1">
                      <UserCell user={member.user} />
                    </div>
                    {member.user.profession ? (
                      <Badge
                        variant="outline"
                        className="hidden font-normal lg:inline-flex"
                      >
                        {PROFESSION_LABEL[member.user.profession]}
                      </Badge>
                    ) : null}
                    {inSpace ? (
                      <span className="shrink-0 text-xs text-muted-foreground">
                        Bo&apos;limda
                      </span>
                    ) : canManage ? (
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => setAccess(member.user.id, "contributor")}
                        aria-label={`${member.user.email} ni bo'limga qo'shish`}
                      >
                        <UserPlus className="size-3" /> Qo&apos;shish
                      </Button>
                    ) : null}
                  </li>
                );
              })
            )}
          </ul>
        </section>

        {/* ----------------------------------------------------- space team */}
        <section className="rounded-xl border">
          <header className="flex items-center gap-2 border-b px-4 py-3">
            <Users className="size-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold">Bo&apos;lim jamoasi</h2>
            <span className="ml-auto text-xs text-muted-foreground">{team.length}</span>
          </header>
          <ul className="max-h-[30rem] overflow-y-auto">
            {team.length === 0 ? (
              <li className="px-4 py-8 text-center text-sm text-muted-foreground">
                Hozircha hech kim biriktirilmagan.
              </li>
            ) : (
              team.map(({ userId, user }) => {
                const access = current[userId];
                const row = rowByUser.get(userId);
                const isNew = !(userId in serverState);
                const changed = !isNew && serverState[userId] !== access;
                return (
                  <li
                    key={userId}
                    className={cn(
                      "flex items-center gap-2 border-b px-4 py-2.5 last:border-b-0",
                      (isNew || changed) && "bg-primary/5",
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      {user ? (
                        <UserCell
                          user={user}
                          subtitle={
                            row?.source === "auto_assignee"
                              ? "Vazifa biriktirilgani uchun avtomatik qo'shilgan"
                              : row?.source === "auto_creator"
                                ? "Bo'lim yaratuvchisi"
                                : undefined
                          }
                        />
                      ) : (
                        <p className="text-sm text-muted-foreground">{userId}</p>
                      )}
                    </div>
                    {canManage ? (
                      <>
                        <AccessSelect
                          value={access}
                          onChange={(next) => setAccess(userId, next)}
                          label={`${user?.email ?? userId} darajasi`}
                        />
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          className="text-danger"
                          aria-label={`${user?.email ?? userId} ni bo'limdan olib tashlash`}
                          onClick={() => removeUser(userId)}
                        >
                          <X />
                        </Button>
                      </>
                    ) : (
                      <Badge variant="secondary">{SPACE_ACCESS_LABEL[access]}</Badge>
                    )}
                  </li>
                );
              })
            )}
          </ul>
          {canManage ? (
            <div className="space-y-1 border-t px-4 py-3 text-xs text-muted-foreground">
              {ACCESS_OPTIONS.map((access) => (
                <p key={access}>
                  <span className="font-medium text-foreground">
                    {SPACE_ACCESS_LABEL[access]}
                  </span>{" "}
                  — {ACCESS_HINT[access]}
                </p>
              ))}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
