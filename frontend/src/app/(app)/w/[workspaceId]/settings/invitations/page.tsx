import { InvitationsSection } from "@/components/settings/workspace-settings";

export default async function SettingsInvitationsPage({
  params,
}: PageProps<"/w/[workspaceId]/settings/invitations">) {
  const { workspaceId } = await params;
  return <InvitationsSection workspaceId={workspaceId} />;
}
