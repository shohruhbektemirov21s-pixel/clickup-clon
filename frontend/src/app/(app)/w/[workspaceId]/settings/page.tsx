import { WorkspaceSettings } from "@/components/settings/workspace-settings";

export default async function SettingsPage({
  params,
}: PageProps<"/w/[workspaceId]/settings">) {
  const { workspaceId } = await params;
  return <WorkspaceSettings workspaceId={workspaceId} />;
}
