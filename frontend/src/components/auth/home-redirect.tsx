"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { getRefreshToken, useAuthStore } from "@/stores/auth-store";
import { useWorkspaces } from "@/hooks/queries";
import { FullPageSpinner } from "@/components/shared/full-page-spinner";
import { CreateWorkspaceCard } from "@/components/shared/create-workspace-card";
import { Landing } from "@/components/marketing/landing";

const subscribeToStorage = (onChange: () => void) => {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
};
const getHasStoredSession = () => !!getRefreshToken();
// SSR snapshot: assume signed-out so the server always renders the landing.
const getServerHasStoredSession = () => false;

/**
 * `/` — the server (and any signed-out visitor) renders the public marketing
 * landing immediately, so first paint / no-JS / SEO all carry the login and
 * register links. The authenticated redirect is layered on after hydration;
 * a stored refresh token switches to the spinner during session bootstrap so
 * returning signed-in users don't flash the landing.
 */
export function HomeRedirect() {
  const router = useRouter();
  const status = useAuthStore((s) => s.status);
  const workspaces = useWorkspaces();
  const hasStoredSession = React.useSyncExternalStore(
    subscribeToStorage,
    getHasStoredSession,
    getServerHasStoredSession,
  );

  React.useEffect(() => {
    if (status === "authenticated" && workspaces.data) {
      const first = workspaces.data.results[0];
      if (first) router.replace(`/w/${first.id}`);
    }
  }, [status, workspaces.data, router]);

  if (status === "authenticated") {
    if (workspaces.data && workspaces.data.results.length === 0) {
      return <CreateWorkspaceCard />;
    }
    return <FullPageSpinner />;
  }

  // Session restore in flight for a returning user — avoid a landing flash.
  if (status === "loading" && hasStoredSession) return <FullPageSpinner />;

  return <Landing />;
}
