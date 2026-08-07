"use client";

import * as React from "react";
import { TopBar } from "@/components/shell/top-bar";
import { Sidebar } from "@/components/shell/sidebar";

export function AppShell({
  workspaceId,
  children,
}: {
  workspaceId: string;
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = React.useState(true);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar
        workspaceId={workspaceId}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
      />
      <div className="flex min-h-0 flex-1">
        {sidebarOpen ? <Sidebar workspaceId={workspaceId} /> : null}
        <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
          {children}
        </main>
      </div>
    </div>
  );
}
