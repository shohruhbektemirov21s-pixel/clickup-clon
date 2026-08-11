import * as React from "react";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { logout, markIntentionalLogout } from "@/lib/auth";
import { clearAllRecent } from "@/components/search/recent-items";

/**
 * Single logout path for the whole app: blacklist the refresh token, drop the
 * in-memory access token + stored refresh token, then **clear every client-side
 * cache** so the next user never sees the previous user's workspaces, tasks or
 * members, and finally land on /login.
 *
 * `queryClient.clear()` covers every server read, search results included — the
 * command palette keeps nothing outside the query cache. One store still lives
 * outside it: `clearAllRecent()` drops "Yaqinda ochilganlar", which is held in
 * `localStorage` and would otherwise survive not just the logout but the
 * browser restart.
 *
 * `markIntentionalLogout()` tells `AuthGate` this is a deliberate sign-out, so
 * it must NOT append `?next=<previous path>` to the redirect — that parameter
 * would send whoever logs in next straight into the previous user's workspace.
 */
export function useLogout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return React.useCallback(async () => {
    markIntentionalLogout();
    await logout();
    queryClient.clear();
    clearAllRecent();
    navigate("/login", { replace: true });
  }, [queryClient, navigate]);
}
