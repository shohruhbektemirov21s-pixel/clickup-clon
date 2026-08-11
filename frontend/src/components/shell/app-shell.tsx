import * as React from "react";
import { TopBar } from "@/components/shell/top-bar";
import { NavRail } from "@/components/shell/nav-rail";
import { Sidebar } from "@/components/shell/sidebar";
import { WorkspaceRealtimeProvider } from "@/components/shell/workspace-realtime";

export function AppShell({
  workspaceId,
  children,
}: {
  workspaceId: string;
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = React.useState(true);

  return (
    // Soket shu yerda, shellning eng tashqarisida ochiladi: qo'ng'iroqcha
    // (`TopBar`) har bir sahifada turadi va `notification.created` freymi
    // aynan shu ulanishdan keladi.
    <WorkspaceRealtimeProvider workspaceId={workspaceId}>
      <div className="flex h-screen flex-col overflow-hidden">
        <TopBar
          workspaceId={workspaceId}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
        />
        <div className="flex min-h-0 flex-1">
          {/* Reyk yon panel yig'ilganda ham qoladi — u rejim tanlovi,
              yon panel esa tanlangan rejim ichidagi daraxt. */}
          <NavRail workspaceId={workspaceId} />
          {sidebarOpen ? <Sidebar workspaceId={workspaceId} /> : null}
          <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
            {children}
          </main>
        </div>
      </div>
    </WorkspaceRealtimeProvider>
  );
}
