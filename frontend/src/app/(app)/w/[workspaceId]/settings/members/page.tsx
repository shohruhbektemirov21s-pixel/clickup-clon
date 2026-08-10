import { MembersSection } from "@/components/settings/workspace-settings";

export default async function SettingsMembersPage({
  params,
}: PageProps<"/w/[workspaceId]/settings/members">) {
  const { workspaceId } = await params;
  return <MembersSection workspaceId={workspaceId} />;
}
