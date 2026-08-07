import { WorkspaceHome } from "@/components/shell/workspace-home";

export default async function WorkspacePage({
  params,
}: PageProps<"/w/[workspaceId]">) {
  const { workspaceId } = await params;
  return <WorkspaceHome workspaceId={workspaceId} />;
}
