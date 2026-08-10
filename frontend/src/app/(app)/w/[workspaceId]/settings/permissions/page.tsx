import { PermissionsMatrix } from "@/components/settings/permissions-matrix";

export default async function SettingsPermissionsPage({
  params,
}: PageProps<"/w/[workspaceId]/settings/permissions">) {
  const { workspaceId } = await params;
  return <PermissionsMatrix workspaceId={workspaceId} />;
}
