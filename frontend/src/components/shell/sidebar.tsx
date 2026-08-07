"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronDown, ChevronRight, Folder as FolderIcon, List as ListIcon, Plus, Settings } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useWorkspace, useWorkspaceTree } from "@/hooks/queries";
import { CreateEntityDialog } from "@/components/shell/create-entity-dialog";
import type { TreeFolder, TreeList, TreeSpace } from "@/types/api";
import { cn } from "@/lib/utils";

type CreateTarget =
  | { kind: "space" }
  | { kind: "list"; spaceId: string; folderId?: string | null };

export function Sidebar({ workspaceId }: { workspaceId: string }) {
  const { data: tree, isPending, isError, refetch } = useWorkspaceTree(workspaceId);
  const { data: workspace } = useWorkspace(workspaceId);
  const [createTarget, setCreateTarget] = React.useState<CreateTarget | null>(null);

  const canManage =
    workspace?.my_role === "owner" || workspace?.my_role === "admin";
  const canCreateList = workspace ? workspace.my_role !== "guest" : false;

  return (
    <aside className="flex w-[260px] shrink-0 flex-col border-r bg-card">
      <div className="flex-1 overflow-y-auto p-2">
        <div className="mb-1 flex items-center justify-between px-2 pt-1">
          <span className="text-xs font-semibold tracking-wide text-muted-foreground">
            SPACES
          </span>
          {canManage ? (
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label="New space"
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
            Couldn&apos;t load your spaces.{" "}
            <button className="text-primary hover:underline" onClick={() => refetch()}>
              Retry
            </button>
          </div>
        ) : tree && tree.spaces.length === 0 ? (
          <div className="px-2 py-4 text-sm text-muted-foreground">
            No spaces yet.
            {canManage ? (
              <Button
                variant="outline"
                size="sm"
                className="mt-2 w-full"
                onClick={() => setCreateTarget({ kind: "space" })}
              >
                Create a space
              </Button>
            ) : (
              <p className="mt-1 text-xs">Ask an admin to create a space.</p>
            )}
          </div>
        ) : (
          tree?.spaces.map((space) => (
            <SpaceNode
              key={space.id}
              workspaceId={workspaceId}
              space={space}
              canCreateList={canCreateList}
              onCreateList={(spaceId, folderId) =>
                setCreateTarget({ kind: "list", spaceId, folderId })
              }
            />
          ))
        )}
      </div>

      <div className="border-t p-2">
        <Link
          href={`/w/${workspaceId}/settings`}
          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Settings className="size-4" />
          Settings
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
  canCreateList,
  onCreateList,
}: {
  workspaceId: string;
  space: TreeSpace;
  canCreateList: boolean;
  onCreateList: (spaceId: string, folderId?: string | null) => void;
}) {
  const [expanded, setExpanded] = React.useState(true);

  return (
    <div>
      <div className="group flex h-8 items-center gap-1 rounded-md px-1 hover:bg-muted">
        <button
          className="flex size-4 shrink-0 items-center justify-center text-muted-foreground"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? `Collapse ${space.name}` : `Expand ${space.name}`}
          aria-expanded={expanded}
        >
          {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        </button>
        <span
          className="size-2 shrink-0 rounded-full"
          style={{ backgroundColor: space.color || "#7B68EE" }}
        />
        <span className="truncate text-[13px] font-medium">{space.name}</span>
        {canCreateList ? (
          <Button
            variant="ghost"
            size="icon-xs"
            className="ml-auto opacity-0 group-hover:opacity-100"
            aria-label={`New list in ${space.name}`}
            onClick={() => onCreateList(space.id, null)}
          >
            <Plus />
          </Button>
        ) : null}
      </div>
      {expanded ? (
        <div>
          {space.folders.map((folder) => (
            <FolderNode
              key={folder.id}
              workspaceId={workspaceId}
              folder={folder}
              spaceId={space.id}
              canCreateList={canCreateList}
              onCreateList={onCreateList}
            />
          ))}
          {space.lists.map((list) => (
            <ListNode key={list.id} workspaceId={workspaceId} list={list} depth={1} />
          ))}
          {space.folders.length === 0 && space.lists.length === 0 ? (
            <p className="py-1 pl-8 text-xs text-muted-foreground">No lists here</p>
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
  canCreateList,
  onCreateList,
}: {
  workspaceId: string;
  folder: TreeFolder;
  spaceId: string;
  canCreateList: boolean;
  onCreateList: (spaceId: string, folderId?: string | null) => void;
}) {
  const [expanded, setExpanded] = React.useState(true);

  return (
    <div>
      <div className="group flex h-8 items-center gap-1 rounded-md pr-1 pl-4 hover:bg-muted">
        <button
          className="flex size-4 shrink-0 items-center justify-center text-muted-foreground"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? `Collapse ${folder.name}` : `Expand ${folder.name}`}
          aria-expanded={expanded}
        >
          {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        </button>
        <FolderIcon className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate text-[13px]">{folder.name}</span>
        {canCreateList ? (
          <Button
            variant="ghost"
            size="icon-xs"
            className="ml-auto opacity-0 group-hover:opacity-100"
            aria-label={`New list in ${folder.name}`}
            onClick={() => onCreateList(spaceId, folder.id)}
          >
            <Plus />
          </Button>
        ) : null}
      </div>
      {expanded
        ? folder.lists.map((list) => (
            <ListNode key={list.id} workspaceId={workspaceId} list={list} depth={2} />
          ))
        : null}
    </div>
  );
}

function ListNode({
  workspaceId,
  list,
  depth,
}: {
  workspaceId: string;
  list: TreeList;
  depth: 1 | 2;
}) {
  const params = useParams<{ listId?: string }>();
  const isActive = params?.listId === list.id;

  return (
    <Link
      href={`/w/${workspaceId}/l/${list.id}`}
      className={cn(
        "flex h-8 items-center gap-1.5 rounded-md pr-2 text-[13px] hover:bg-muted",
        depth === 1 ? "pl-8" : "pl-12",
        isActive && "bg-primary/10 font-medium text-primary",
      )}
      aria-current={isActive ? "page" : undefined}
    >
      <ListIcon className="size-3.5 shrink-0 text-muted-foreground" />
      <span className="truncate">{list.name}</span>
      {list.open_task_count > 0 ? (
        <Badge variant="secondary" className="ml-auto h-4 px-1 text-[10px]">
          {list.open_task_count}
        </Badge>
      ) : null}
    </Link>
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
