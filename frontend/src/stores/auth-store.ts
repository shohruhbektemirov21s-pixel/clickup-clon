import { create } from "zustand";
import type { User } from "@/types/api";

const REFRESH_KEY = "clickish.refresh";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  /** JWT access token — memory only, never persisted. */
  accessToken: string | null;
  user: User | null;
  status: AuthStatus;
  setSession: (session: { access: string; refresh: string; user?: User }) => void;
  setAccess: (access: string) => void;
  setUser: (user: User) => void;
  setStatus: (status: AuthStatus) => void;
  clearSession: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  status: "loading",
  setSession: ({ access, refresh, user }) => {
    persistRefreshToken(refresh);
    set((s) => ({
      accessToken: access,
      user: user ?? s.user,
      status: "authenticated",
    }));
  },
  setAccess: (access) => set({ accessToken: access }),
  setUser: (user) => set({ user }),
  setStatus: (status) => set({ status }),
  clearSession: () => {
    clearRefreshToken();
    set({ accessToken: null, user: null, status: "unauthenticated" });
  },
}));

/** Refresh token lives in localStorage (per project decision OQ-1). */
export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

export function persistRefreshToken(refresh: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearRefreshToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(REFRESH_KEY);
}
