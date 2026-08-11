import * as React from "react";
import { useLocation, useNavigate } from "react-router";
import { useAuthStore } from "@/stores/auth-store";
import { FullPageSpinner } from "@/components/shared/full-page-spinner";

/**
 * Client route protection for the app area. Tokens live client-side (access
 * in memory, refresh in localStorage), so the guard runs after the session
 * bootstrap in <Providers>: while restoring → spinner; unauthenticated →
 * redirect to /login?next=<current path>.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const status = useAuthStore((s) => s.status);
  const navigate = useNavigate();
  const { pathname } = useLocation();

  React.useEffect(() => {
    if (status === "unauthenticated") {
      const next = pathname && pathname !== "/" ? `?next=${encodeURIComponent(pathname)}` : "";
      navigate(`/login${next}`, { replace: true });
    }
  }, [status, navigate, pathname]);

  if (status !== "authenticated") return <FullPageSpinner />;
  return <>{children}</>;
}
