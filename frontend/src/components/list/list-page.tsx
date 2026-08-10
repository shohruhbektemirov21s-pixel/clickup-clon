"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Columns3, Rows3 } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { useList, useStatusSet, useWorkspace } from "@/hooks/queries";
import { useListChannel } from "@/hooks/use-list-channel";
import { ListView } from "@/components/list/list-view";
import { BoardView } from "@/components/board/board-view";
import { TaskPanel } from "@/components/task/task-panel";
import { SpaceTeamStrip } from "@/components/workspace/space-team-strip";
import type { ViewKind } from "@/types/api";
import { cn } from "@/lib/utils";

export function ListPage({
  workspaceId,
  listId,
}: {
  workspaceId: string;
  listId: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const { data: list } = useList(listId);
  const { data: statusSet } = useStatusSet(listId);
  const { data: workspace } = useWorkspace(workspaceId);
  const connection = useListChannel(listId);

  const view: ViewKind =
    searchParams.get("view") === "board"
      ? "board"
      : searchParams.get("view") === "list"
        ? "list"
        : (list?.default_view ?? "list");

  const openTaskId = searchParams.get("task");

  const setParam = React.useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(searchParams.toString());
      if (value === null) next.delete(key);
      else next.set(key, value);
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, searchParams],
  );

  const openTask = React.useCallback(
    (taskId: string) => setParam("task", taskId),
    [setParam],
  );
  const closeTask = React.useCallback(() => setParam("task", null), [setParam]);

  const isGuest = workspace?.my_role === "guest";
  const statuses = statusSet?.statuses ?? [];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold leading-tight">
            {list?.name ?? "…"}
          </h1>
        </div>
        <Tabs
          value={view}
          onValueChange={(v) => setParam("view", v as string)}
          className="ml-4"
        >
          <TabsList>
            <TabsTrigger value="list" className="gap-1.5">
              <Rows3 className="size-3.5" /> Ro&apos;yxat
            </TabsTrigger>
            <TabsTrigger value="board" className="gap-1.5">
              <Columns3 className="size-3.5" /> Doska
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="ml-auto flex items-center gap-3">
          <SpaceTeamStrip workspaceId={workspaceId} spaceId={list?.space_id} />
          <Badge
            variant="secondary"
            className="gap-1.5 font-normal text-muted-foreground"
            title={`Real vaqt holati: ${connection}`}
          >
            <span
              className={cn(
                "size-1.5 rounded-full",
                connection === "open" && "bg-brand-green",
                (connection === "connecting" || connection === "reconnecting") &&
                  "animate-pulse bg-brand-yellow",
                connection === "offline" && "bg-danger",
              )}
            />
            {connection === "open"
              ? "Jonli"
              : connection === "offline"
                ? "Oflayn"
                : "Ulanmoqda…"}
          </Badge>
        </div>
      </div>

      {view === "board" ? (
        <BoardView
          listId={listId}
          statuses={statuses}
          onOpenTask={openTask}
          canEdit={!isGuest}
        />
      ) : (
        <ListView
          workspaceId={workspaceId}
          listId={listId}
          statuses={statuses}
          onOpenTask={openTask}
          canEdit={!isGuest}
        />
      )}

      <TaskPanel
        workspaceId={workspaceId}
        listId={listId}
        taskId={openTaskId}
        statuses={statuses}
        onClose={closeTask}
      />
    </div>
  );
}
