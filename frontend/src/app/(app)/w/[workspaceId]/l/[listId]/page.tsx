import { Suspense } from "react";
import { ListPage } from "@/components/list/list-page";
import { FullPageSpinner } from "@/components/shared/full-page-spinner";

export default async function ListRoute({
  params,
}: PageProps<"/w/[workspaceId]/l/[listId]">) {
  const { workspaceId, listId } = await params;
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <ListPage workspaceId={workspaceId} listId={listId} />
    </Suspense>
  );
}
