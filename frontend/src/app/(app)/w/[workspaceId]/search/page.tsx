import { Suspense } from "react";
import { SearchResults } from "@/components/search/search-results";
import { FullPageSpinner } from "@/components/shared/full-page-spinner";

export default async function SearchPage({
  params,
}: PageProps<"/w/[workspaceId]/search">) {
  const { workspaceId } = await params;
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <SearchResults workspaceId={workspaceId} />
    </Suspense>
  );
}
