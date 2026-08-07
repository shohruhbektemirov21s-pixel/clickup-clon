"use client";

import { api } from "@/lib/api";
import { getRefreshToken, useAuthStore } from "@/stores/auth-store";
import type { AuthResponse, LoginRequest, RegisterRequest } from "@/types/api";

export async function login(body: LoginRequest): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>("auth/login/", body, { auth: false });
  useAuthStore.getState().setSession(res);
  return res;
}

export async function register(body: RegisterRequest): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>("auth/register/", body, { auth: false });
  useAuthStore.getState().setSession(res);
  return res;
}

/** Blacklists this device's refresh token, then clears local session state. */
export async function logout(): Promise<void> {
  const refresh = getRefreshToken();
  try {
    if (refresh) await api.post("auth/logout/", { refresh });
  } catch {
    // Best effort — clear locally regardless.
  } finally {
    useAuthStore.getState().clearSession();
  }
}
