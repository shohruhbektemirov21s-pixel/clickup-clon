import { CommandPalette } from "@/components/search/command-palette";
import { AppShell } from "@/components/shell/app-shell";

export default async function WorkspaceLayout({
  children,
  params,
}: LayoutProps<"/w/[workspaceId]">) {
  const { workspaceId } = await params;
  return (
    <AppShell workspaceId={workspaceId}>
      {children}
      {/* S12 — global `Ctrl/Cmd+K` paneli. Ish maydoni layout'ida bir marta
          mount qilinadi: klaviatura tinglovchisi komponentning o'zida. */}
      <CommandPalette workspaceId={workspaceId} />
    </AppShell>
  );
}
