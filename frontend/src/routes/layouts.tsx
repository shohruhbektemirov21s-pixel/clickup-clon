/**
 * Marshrut layoutlari.
 *
 * Next'ning `src/app/**` daraxtidagi `layout.tsx` fayllari shu yerga bir xil
 * markup bilan ko'chirildi: `(app)` guruhi → `<AppAreaLayout>`, `(auth)` →
 * `<AuthLayout>`, `invite/` → `<InviteLayout>`. Yagona farq — `children`
 * o'rniga React Router'ning `<Outlet />` i.
 */

import { Outlet, useParams } from "react-router";
import { AuthGate } from "@/components/auth/auth-gate";
import { APP } from "@/i18n/uz";
import { CommandPalette } from "@/components/search/command-palette";
import { SettingsShell } from "@/components/settings/settings-shell";
import { AppShell } from "@/components/shell/app-shell";

export function AppAreaLayout() {
  return (
    <AuthGate>
      <Outlet />
    </AuthGate>
  );
}

export function AuthLayout() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-muted/40 p-6">
      <div className="mb-8 flex items-center gap-2.5">
        <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-lg font-bold text-primary-foreground">
          {APP.brandInitial}
        </div>
        <span className="text-xl font-semibold">{APP.brand}</span>
      </div>
      <Outlet />
    </main>
  );
}

/**
 * Public taklif sahifasi uchun markazlashtirilgan karta — `(auth)` guruhidagi
 * layout bilan bir xil ko'rinish, lekin bu marshrut autentifikatsiya
 * talab qilmaydi.
 */
export function InviteLayout() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-muted/40 p-6">
      <div className="mb-8 flex items-center gap-2.5">
        <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-lg font-bold text-primary-foreground">
          {APP.brandInitial}
        </div>
        <span className="text-xl font-semibold">{APP.brand}</span>
      </div>
      <div className="w-full max-w-[420px] rounded-xl border bg-background p-8 shadow-lg">
        <Outlet />
      </div>
    </main>
  );
}

export function WorkspaceLayout() {
  const { workspaceId = "" } = useParams<{ workspaceId: string }>();
  return (
    <AppShell workspaceId={workspaceId}>
      <Outlet />
      {/* S12 — global `Ctrl/Cmd+K` paneli. Ish maydoni layout'ida bir marta
          mount qilinadi: klaviatura tinglovchisi komponentning o'zida. */}
      <CommandPalette workspaceId={workspaceId} />
    </AppShell>
  );
}

export function WorkspaceSettingsLayout() {
  const { workspaceId = "" } = useParams<{ workspaceId: string }>();
  return (
    <SettingsShell workspaceId={workspaceId}>
      <Outlet />
    </SettingsShell>
  );
}
