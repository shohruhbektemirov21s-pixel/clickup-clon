"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ChevronDown,
  ChevronRight,
  Folder as FolderIcon,
  List as ListIcon,
  MessageSquare,
  Plus,
  Settings,
  Users,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMembers, useMyPermissions, useWorkspaceTree } from "@/hooks/queries";
import { CreateEntityDialog } from "@/components/shell/create-entity-dialog";
import { TreeNodeActions } from "@/components/shell/tree-node-actions";
import { InviteMemberDialog } from "@/components/workspace/invite-member-dialog";
import type { Member, MyPermissions, TreeFolder, TreeList, TreeSpace } from "@/types/api";
import { initials } from "@/lib/format";
import { can, canInSpace } from "@/lib/permissions";
import { ROLE_LABEL, ROLE_RANK } from "@/lib/roles";
import { cn } from "@/lib/utils";

type CreateTarget =
  | { kind: "space" }
  | { kind: "list"; spaceId: string; folderId?: string | null };

/**
 * Bitta bo'lim shoxobchasi uchun oldindan hisoblangan ruxsatlar.
 *
 * Ilgari daraxt `my_role === "owner" | "admin"` bo'yicha chizilardi, ya'ni
 * matritsada `member` ga `space.create` berish UI da hech narsani
 * o'zgartirmasdi, `list.create` si olib qo'yilgan a'zo esa baribir `＋` ni
 * ko'rardi. Endi har bir tugma o'z kodiga bog'langan va kod bo'lim doirasida
 * hal qilinadi (`canInSpace`), xuddi serverdagi `has_space_perm` kabi.
 */
interface SpaceTreePermissions {
  createList: boolean;
  renameSpace: boolean;
  deleteSpace: boolean;
  renameFolder: boolean;
  deleteFolder: boolean;
  cascadeFolder: boolean;
  renameList: boolean;
  deleteList: boolean;
  manageTeam: boolean;
}

function spaceTreePermissions(
  my: MyPermissions | undefined,
  spaceId: string,
): SpaceTreePermissions {
  return {
    createList: canInSpace(my, spaceId, "list.create"),
    renameSpace: canInSpace(my, spaceId, "space.update"),
    // `space.delete` ataylab PM'ning lokal grantiga kirmaydi (§B.5).
    deleteSpace: canInSpace(my, spaceId, "space.delete"),
    renameFolder: canInSpace(my, spaceId, "folder.update"),
    deleteFolder: canInSpace(my, spaceId, "folder.delete"),
    cascadeFolder: canInSpace(my, spaceId, "folder.delete_cascade"),
    renameList: canInSpace(my, spaceId, "list.update"),
    deleteList: canInSpace(my, spaceId, "list.delete"),
    manageTeam: canInSpace(my, spaceId, "space.manage_members"),
  };
}

export function Sidebar({ workspaceId }: { workspaceId: string }) {
  const { data: tree, isPending, isError, refetch } = useWorkspaceTree(workspaceId);
  const { data: my } = useMyPermissions(workspaceId);
  const [createTarget, setCreateTarget] = React.useState<CreateTarget | null>(null);
  const params = useParams<{ listId?: string }>();
  const router = useRouter();
  const activeListId = params?.listId;

  // Bo'lim hali yo'q — bu yagona chinakam ish maydoni darajasidagi kod.
  const canCreateSpace = can(my, "space.create");
  const canInvite = can(my, "member.invite");

  /** After deleting the container holding the open list, fall back to home. */
  const leaveIfActive = (containsActive: boolean) => {
    if (containsActive) router.push(`/w/${workspaceId}`);
  };

  return (
    <aside className="flex w-[260px] shrink-0 flex-col border-r bg-card">
      <div className="flex-1 overflow-y-auto p-2">
        <div className="mb-1 flex items-center justify-between px-2 pt-1">
          <span className="text-xs font-semibold tracking-wide text-muted-foreground">
            BO&apos;LIMLAR
          </span>
          {canCreateSpace ? (
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label="Yangi bo'lim"
              onClick={() => setCreateTarget({ kind: "space" })}
            >
              <Plus />
            </Button>
          ) : null}
        </div>

        {isPending ? (
          <TreeSkeleton />
        ) : isError ? (
          <div className="px-2 py-4 text-sm text-muted-foreground">
            Bo&apos;limlarni yuklab bo&apos;lmadi.{" "}
            <button className="text-primary hover:underline" onClick={() => refetch()}>
              Qayta urinish
            </button>
          </div>
        ) : tree && tree.spaces.length === 0 ? (
          <div className="px-2 py-4 text-sm text-muted-foreground">
            Hozircha bo&apos;limlar yo&apos;q.
            {canCreateSpace ? (
              <Button
                variant="outline"
                size="sm"
                className="mt-2 w-full"
                onClick={() => setCreateTarget({ kind: "space" })}
              >
                Bo&apos;lim yaratish
              </Button>
            ) : (
              <p className="mt-1 text-xs">
                Bo&apos;lim yaratish uchun administratorga murojaat qiling.
              </p>
            )}
          </div>
        ) : (
          tree?.spaces.map((space) => (
            <SpaceNode
              key={space.id}
              workspaceId={workspaceId}
              space={space}
              perms={spaceTreePermissions(my, space.id)}
              activeListId={activeListId}
              onLeaveIfActive={leaveIfActive}
              onCreateList={(spaceId, folderId) =>
                setCreateTarget({ kind: "list", spaceId, folderId })
              }
            />
          ))
        )}
      </div>

      <TeamSection workspaceId={workspaceId} canInvite={canInvite} />

      <div className="border-t p-2">
        <Link
          href={`/w/${workspaceId}/chat`}
          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <MessageSquare className="size-4" />
          Chat
        </Link>
        <Link
          href={`/w/${workspaceId}/settings`}
          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Settings className="size-4" />
          Sozlamalar
        </Link>
      </div>

      {createTarget ? (
        <CreateEntityDialog
          workspaceId={workspaceId}
          target={createTarget}
          onClose={() => setCreateTarget(null)}
        />
      ) : null}
    </aside>
  );
}

function SpaceNode({
  workspaceId,
  space,
  perms,
  activeListId,
  onLeaveIfActive,
  onCreateList,
}: {
  workspaceId: string;
  space: TreeSpace;
  perms: SpaceTreePermissions;
  activeListId?: string;
  onLeaveIfActive: (containsActive: boolean) => void;
  onCreateList: (spaceId: string, folderId?: string | null) => void;
}) {
  const [expanded, setExpanded] = React.useState(true);

  const holdsActiveList =
    !!activeListId &&
    (space.lists.some((l) => l.id === activeListId) ||
      space.folders.some((f) => f.lists.some((l) => l.id === activeListId)));

  return (
    <div>
      <div className="group flex h-8 items-center gap-1 rounded-md px-1 hover:bg-muted">
        <button
          className="flex size-4 shrink-0 items-center justify-center text-muted-foreground"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? `${space.name} bo'limini yig'ish` : `${space.name} bo'limini ochish`}
          aria-expanded={expanded}
        >
          {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        </button>
        <span
          className="size-2 shrink-0 rounded-full"
          style={{ backgroundColor: space.color || "#7B68EE" }}
        />
        <span className="truncate text-[13px] font-medium">{space.name}</span>
        <span className="ml-auto flex items-center">
          {/* §D.6 — "Jamoa" faqat bo'lim a'zolarini boshqara oladiganga.
              Qolganlar jamoani baribir ko'radi, lekin bo'lim sahifasidagi
              read-only avatarlar orqali (SpaceTeamStrip). */}
          {perms.manageTeam ? (
            <Button
              variant="ghost"
              size="icon-xs"
              className="opacity-0 group-hover:opacity-100"
              aria-label={`${space.name} jamoasi`}
              title="Jamoa"
              render={<Link href={`/w/${workspaceId}/s/${space.id}/members`} />}
            >
              <Users />
            </Button>
          ) : null}
          {perms.createList ? (
            <Button
              variant="ghost"
              size="icon-xs"
              className="opacity-0 group-hover:opacity-100"
              aria-label={`${space.name} ichida yangi ro'yxat`}
              onClick={() => onCreateList(space.id, null)}
            >
              <Plus />
            </Button>
          ) : null}
          <TreeNodeActions
            workspaceId={workspaceId}
            kind="space"
            id={space.id}
            name={space.name}
            canRename={perms.renameSpace}
            canDelete={perms.deleteSpace}
            canCascade={perms.deleteSpace}
            onDeleted={() => onLeaveIfActive(holdsActiveList)}
          />
        </span>
      </div>
      {expanded ? (
        <div>
          {space.folders.map((folder) => (
            <FolderNode
              key={folder.id}
              workspaceId={workspaceId}
              folder={folder}
              spaceId={space.id}
              perms={perms}
              activeListId={activeListId}
              onLeaveIfActive={onLeaveIfActive}
              onCreateList={onCreateList}
            />
          ))}
          {space.lists.map((list) => (
            <ListNode
              key={list.id}
              workspaceId={workspaceId}
              list={list}
              depth={1}
              perms={perms}
              onLeaveIfActive={onLeaveIfActive}
            />
          ))}
          {space.folders.length === 0 && space.lists.length === 0 ? (
            <p className="py-1 pl-8 text-xs text-muted-foreground">
              Bu yerda ro&apos;yxatlar yo&apos;q
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function FolderNode({
  workspaceId,
  folder,
  spaceId,
  perms,
  activeListId,
  onLeaveIfActive,
  onCreateList,
}: {
  workspaceId: string;
  folder: TreeFolder;
  spaceId: string;
  perms: SpaceTreePermissions;
  activeListId?: string;
  onLeaveIfActive: (containsActive: boolean) => void;
  onCreateList: (spaceId: string, folderId?: string | null) => void;
}) {
  const [expanded, setExpanded] = React.useState(true);

  const holdsActiveList =
    !!activeListId && folder.lists.some((l) => l.id === activeListId);

  return (
    <div>
      <div className="group flex h-8 items-center gap-1 rounded-md pr-1 pl-4 hover:bg-muted">
        <button
          className="flex size-4 shrink-0 items-center justify-center text-muted-foreground"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? `${folder.name} jildini yig'ish` : `${folder.name} jildini ochish`}
          aria-expanded={expanded}
        >
          {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        </button>
        <FolderIcon className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate text-[13px]">{folder.name}</span>
        <span className="ml-auto flex items-center">
          {perms.createList ? (
            <Button
              variant="ghost"
              size="icon-xs"
              className="opacity-0 group-hover:opacity-100"
              aria-label={`${folder.name} ichida yangi ro'yxat`}
              onClick={() => onCreateList(spaceId, folder.id)}
            >
              <Plus />
            </Button>
          ) : null}
          <TreeNodeActions
            workspaceId={workspaceId}
            kind="folder"
            id={folder.id}
            name={folder.name}
            canRename={perms.renameFolder}
            canDelete={perms.deleteFolder}
            canCascade={perms.cascadeFolder}
            onDeleted={() => onLeaveIfActive(holdsActiveList)}
          />
        </span>
      </div>
      {expanded
        ? folder.lists.map((list) => (
            <ListNode
              key={list.id}
              workspaceId={workspaceId}
              list={list}
              depth={2}
              perms={perms}
              onLeaveIfActive={onLeaveIfActive}
            />
          ))
        : null}
    </div>
  );
}

function ListNode({
  workspaceId,
  list,
  depth,
  perms,
  onLeaveIfActive,
}: {
  workspaceId: string;
  list: TreeList;
  depth: 1 | 2;
  perms: SpaceTreePermissions;
  onLeaveIfActive: (containsActive: boolean) => void;
}) {
  const params = useParams<{ listId?: string }>();
  const isActive = params?.listId === list.id;

  return (
    <div
      className={cn(
        "group flex h-8 items-center gap-1.5 rounded-md pr-1 text-[13px] hover:bg-muted",
        depth === 1 ? "pl-8" : "pl-12",
        isActive && "bg-primary/10 font-medium text-primary",
      )}
    >
      <Link
        href={`/w/${workspaceId}/l/${list.id}`}
        className="flex min-w-0 flex-1 items-center gap-1.5"
        aria-current={isActive ? "page" : undefined}
      >
        <ListIcon className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate">{list.name}</span>
      </Link>
      {list.open_task_count > 0 ? (
        <Badge variant="secondary" className="h-4 shrink-0 px-1 text-[10px]">
          {list.open_task_count}
        </Badge>
      ) : null}
      <TreeNodeActions
        workspaceId={workspaceId}
        kind="list"
        id={list.id}
        name={list.name}
        canRename={perms.renameList}
        canDelete={perms.deleteList}
        canCascade={perms.deleteList}
        onDeleted={() => onLeaveIfActive(isActive)}
      />
    </div>
  );
}

/** Workspace roster in the sidebar; a member links to the settings roster. */
function TeamSection({
  workspaceId,
  canInvite,
}: {
  workspaceId: string;
  /** `member.invite` — rol emas: matritsa uni istalgan rolga bera oladi. */
  canInvite: boolean;
}) {
  const { data, isPending } = useMembers(workspaceId);
  const [expanded, setExpanded] = React.useState(true);
  const [inviteOpen, setInviteOpen] = React.useState(false);

  const members: Member[] = React.useMemo(() => {
    const rows = data?.results ?? [];
    return [...rows].sort(
      (a, b) =>
        ROLE_RANK[a.role] - ROLE_RANK[b.role] ||
        // Mehmon emailni ko'rmaydi (§4), shuning uchun ism birlamchi kalit.
        a.user.full_name.localeCompare(b.user.full_name) ||
        (a.user.email ?? "").localeCompare(b.user.email ?? ""),
    );
  }, [data]);

  return (
    <div className="border-t p-2">
      <div className="flex items-center justify-between px-2 py-1">
        <button
          className="flex items-center gap-1 text-xs font-semibold tracking-wide text-muted-foreground hover:text-foreground"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          {expanded ? (
            <ChevronDown className="size-3.5" />
          ) : (
            <ChevronRight className="size-3.5" />
          )}
          JAMOA
        </button>
        <span className="flex items-center gap-1">
          {members.length > 0 ? (
            <span className="text-xs text-muted-foreground">{members.length}</span>
          ) : null}
          {canInvite ? (
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label="Jamoaga qo'shish"
              title="Jamoaga qo'shish"
              onClick={() => setInviteOpen(true)}
            >
              <Plus />
            </Button>
          ) : null}
        </span>
      </div>

      <InviteMemberDialog
        workspaceId={workspaceId}
        open={inviteOpen}
        onOpenChange={setInviteOpen}
      />

      {expanded ? (
        isPending ? (
          <div className="flex flex-col gap-1.5 px-2 py-1" aria-hidden>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-6 w-full" />
            ))}
          </div>
        ) : members.length === 0 ? (
          <p className="px-2 py-1 text-xs text-muted-foreground">A&apos;zolar yo&apos;q</p>
        ) : (
          <ul className="max-h-48 overflow-y-auto">
            {members.map((member) => (
              <li key={member.id}>
                <Link
                  href={`/w/${workspaceId}/settings`}
                  className="flex h-8 w-full items-center gap-2 rounded-md px-2 text-left text-[13px] hover:bg-muted"
                  title={member.user.email ?? member.user.full_name}
                >
                  <Avatar className="size-5 shrink-0">
                    {member.user.avatar ? (
                      <AvatarImage src={member.user.avatar} alt="" />
                    ) : null}
                    <AvatarFallback
                      className="text-[9px] font-semibold text-primary-foreground"
                      style={{ backgroundColor: member.user.avatar_color || "#7B68EE" }}
                    >
                      {initials(member.user.full_name, member.user.email ?? undefined)}
                    </AvatarFallback>
                  </Avatar>
                  <span className="truncate">
                    {member.user.full_name || member.user.email}
                  </span>
                  <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                    {ROLE_LABEL[member.role]}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </div>
  );
}

function TreeSkeleton() {
  return (
    <div className="flex flex-col gap-2 px-2 py-2" aria-hidden>
      {[0, 1, 2].map((group) => (
        <div key={group} className="flex flex-col gap-2">
          <Skeleton className="h-4 w-2/5" />
          <Skeleton className="ml-4 h-4 w-3/5" />
          <Skeleton className="ml-4 h-4 w-1/2" />
        </div>
      ))}
    </div>
  );
}
