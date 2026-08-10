import { SpaceMembersPanel } from "@/components/workspace/space-members-panel";

export default async function SpaceMembersPage({
  params,
}: PageProps<"/w/[workspaceId]/s/[spaceId]/members">) {
  const { workspaceId, spaceId } = await params;
  return <SpaceMembersPanel workspaceId={workspaceId} spaceId={spaceId} />;
}
