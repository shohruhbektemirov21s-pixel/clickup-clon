import { GeneralSection } from "@/components/settings/workspace-settings";

export default async function SettingsPage({
  params,
}: PageProps<"/w/[workspaceId]/settings">) {
  const { workspaceId } = await params;
  return <GeneralSection workspaceId={workspaceId} />;
}
