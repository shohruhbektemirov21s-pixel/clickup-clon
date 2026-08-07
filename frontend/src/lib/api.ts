"use client";

import { API_BASE_URL } from "@/lib/env";
import { getClientId } from "@/lib/client-id";
import {
  clearRefreshToken,
  getRefreshToken,
  persistRefreshToken,
  useAuthStore,
} from "@/stores/auth-store";
import type { ApiErrorCode, ApiErrorEnvelope, TokenPair } from "@/types/api";

// ---------------------------------------------------------------------------
// Typed error
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode;
  readonly details: Record<string, unknown>;
  readonly requestId?: string;

  constructor(
    status: number,
    code: ApiErrorCode,
    message: string,
    details: Record<string, unknown> = {},
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  /** First message for a field from `error.details.<field>: string[]`. */
  fieldError(field: string): string | undefined {
    const value = this.details[field];
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
    if (typeof value === "string") return value;
    return undefined;
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}

async function toApiError(res: Response): Promise<ApiError> {
  let envelope: ApiErrorEnvelope | null = null;
  try {
    envelope = (await res.json()) as ApiErrorEnvelope;
  } catch {
    // Non-JSON error body (proxy, network middlebox…)
  }
  if (envelope?.error) {
    return new ApiError(
      res.status,
      envelope.error.code,
      envelope.error.message,
      envelope.error.details ?? {},
      envelope.error.request_id,
    );
  }
  return new ApiError(
    res.status,
    res.status >= 500 ? "server_error" : "bad_request",
    `So'rov bajarilmadi (status ${res.status}).`,
  );
}

// ---------------------------------------------------------------------------
// URL / query helpers
// ---------------------------------------------------------------------------

export type QueryValue = string | number | boolean | undefined | null;
export type Query = Record<string, QueryValue | QueryValue[]>;

function buildUrl(path: string, query?: Query): string {
  // Every contract path ends with a trailing slash — enforce it here.
  let p = path.startsWith("/") ? path.slice(1) : path;
  if (!p.endsWith("/")) p += "/";
  const url = `${API_BASE_URL}/${p}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const v of value) {
        if (v !== undefined && v !== null) params.append(key, String(v));
      }
    } else {
      params.append(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

// ---------------------------------------------------------------------------
// Refresh flow (single flight)
// ---------------------------------------------------------------------------

let refreshPromise: Promise<string | null> | null = null;

/**
 * Rotates the refresh token (§1.3): POST auth/refresh/ returns a NEW access
 * and a NEW refresh; the old refresh is blacklisted server-side.
 * Returns the new access token, or null when the session is unrecoverable.
 */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

async function doRefresh(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  try {
    const res = await fetch(buildUrl("auth/refresh/"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) {
      if (res.status === 401) {
        clearRefreshToken();
        useAuthStore.getState().clearSession();
      }
      return null;
    }
    const pair = (await res.json()) as TokenPair;
    persistRefreshToken(pair.refresh);
    useAuthStore.getState().setAccess(pair.access);
    return pair.access;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Core request
// ---------------------------------------------------------------------------

const MUTATING = new Set(["POST", "PATCH", "PUT", "DELETE"]);

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Query;
  /** Attach the Authorization header (default true). */
  auth?: boolean;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, auth = true, signal } = options;

  const exec = async (accessToken: string | null): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
    if (MUTATING.has(method)) headers["X-Client-Id"] = getClientId();
    return fetch(buildUrl(path, query), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  };

  let res = await exec(useAuthStore.getState().accessToken);

  // §1.3 / R15 — 401 token_not_valid triggers a silent refresh + one retry.
  if (res.status === 401 && auth) {
    const err = await toApiError(res.clone());
    if (err.code === "token_not_valid" || err.code === "authentication_failed") {
      const newAccess = await refreshAccessToken();
      if (newAccess) {
        res = await exec(newAccess);
      } else {
        throw err;
      }
    }
  }

  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get<T>(path: string, query?: Query, signal?: AbortSignal) {
    return request<T>(path, { query, signal });
  },
  post<T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) {
    return request<T>(path, { ...options, method: "POST", body });
  },
  patch<T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) {
    return request<T>(path, { ...options, method: "PATCH", body });
  },
  put<T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) {
    return request<T>(path, { ...options, method: "PUT", body });
  },
  delete<T = void>(path: string, body?: unknown) {
    return request<T>(path, { method: "DELETE", body });
  },
};
