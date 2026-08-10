import { SettingsShell } from "@/components/settings/settings-shell";

export default async function WorkspaceSettingsLayout({
  children,
  params,
}: LayoutProps<"/w/[workspaceId]/settings">) {
  const { workspaceId } = await params;
  return <SettingsShell workspaceId={workspaceId}>{children}</SettingsShell>;
}
