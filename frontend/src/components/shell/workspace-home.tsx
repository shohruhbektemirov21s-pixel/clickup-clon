"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useWorkspaceTree } from "@/hooks/queries";
import { FullPageSpinner } from "@/components/shared/full-page-spinner";
import type { WorkspaceTree } from "@/types/api";

function firstListId(tree: WorkspaceTree): string | null {
  for (const space of tree.spaces) {
    for (const folder of space.folders) {
      if (folder.lists.length > 0) return folder.lists[0].id;
    }
    if (space.lists.length > 0) return space.lists[0].id;
  }
  return null;
}

/** Workspace home — redirects to the first list, or shows an empty state. */
export function WorkspaceHome({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const { data: tree, isPending } = useWorkspaceTree(workspaceId);

  React.useEffect(() => {
    if (!tree) return;
    const listId = firstListId(tree);
    if (listId) router.replace(`/w/${workspaceId}/l/${listId}`);
  }, [tree, router, workspaceId]);

  if (isPending || (tree && firstListId(tree))) return <FullPageSpinner />;

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-16 text-center">
      <h2 className="text-lg font-semibold">Ish maydoningizga xush kelibsiz</h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        Vazifa qo&apos;shishni boshlash uchun yon paneldan bo&apos;lim va
        ro&apos;yxat yarating.
      </p>
    </div>
  );
}
