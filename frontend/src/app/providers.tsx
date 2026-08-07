"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Toaster } from "@/components/ui/sonner";
import { api, isApiError, refreshAccessToken } from "@/lib/api";
import { getRefreshToken, useAuthStore } from "@/stores/auth-store";
import type { User } from "@/types/api";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        retry: (failureCount, error) => {
          // Never retry 4xx errors; retry network/5xx twice.
          if (isApiError(error) && error.status < 500) return false;
          return failureCount < 2;
        },
        refetchOnWindowFocus: false,
      },
    },
  });
}

/** Restore the session from the persisted refresh token on first load. */
function SessionBootstrap({ children }: { children: React.ReactNode }) {
  const setStatus = useAuthStore((s) => s.setStatus);
  const setUser = useAuthStore((s) => s.setUser);
  const clearSession = useAuthStore((s) => s.clearSession);
  const started = React.useRef(false);

  React.useEffect(() => {
    if (started.current) return;
    started.current = true;
    const run = async () => {
      if (useAuthStore.getState().status === "authenticated") return;
      if (!getRefreshToken()) {
        setStatus("unauthenticated");
        return;
      }
      const access = await refreshAccessToken();
      if (!access) {
        clearSession();
        return;
      }
      try {
        const me = await api.get<User>("me/");
        setUser(me);
        setStatus("authenticated");
      } catch {
        clearSession();
      }
    };
    void run();
  }, [setStatus, setUser, clearSession]);

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(makeQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        <SessionBootstrap>{children}</SessionBootstrap>
        <Toaster position="bottom-right" />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
