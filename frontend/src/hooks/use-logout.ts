"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { logout } from "@/lib/auth";

/**
 * Single logout path for the whole app: blacklist the refresh token, drop the
 * in-memory access token + stored refresh token, then **clear the TanStack
 * Query cache** so the next user never sees the previous user's workspaces,
 * tasks or members, and finally land on /login.
 */
export function useLogout() {
  const router = useRouter();
  const queryClient = useQueryClient();

  return React.useCallback(async () => {
    await logout();
    queryClient.clear();
    router.replace("/login");
  }, [queryClient, router]);
}
