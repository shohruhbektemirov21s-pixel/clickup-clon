import { API_BASE_URL } from "@/lib/env";
import { getClientId } from "@/lib/client-id";
import { MUTATIONS } from "@/i18n/uz";
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
  // multipart/form-data (me/avatar/) — the browser sets the boundary itself,
  // so Content-Type must NOT be set and the body must not be serialised.
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

  const exec = async (accessToken: string | null): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (body !== undefined && !isFormData) headers["Content-Type"] = "application/json";
    if (auth && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
    if (MUTATING.has(method)) headers["X-Client-Id"] = getClientId();
    return fetch(buildUrl(path, query), {
      method,
      headers,
      body:
        body === undefined ? undefined : isFormData ? (body as FormData) : JSON.stringify(body),
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

// ---------------------------------------------------------------------------
// Binary reads / uploads (§10.7 attachments)
// ---------------------------------------------------------------------------

/**
 * Fetches a protected binary resource (attachment download) as a Blob.
 * `<img src>` / `<a href>` cannot carry the Authorization header, so every
 * preview and download goes through here and then an object URL.
 */
async function requestBlob(path: string): Promise<Blob> {
  const exec = (accessToken: string | null) =>
    fetch(buildUrl(path), {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });

  let res = await exec(useAuthStore.getState().accessToken);
  if (res.status === 401) {
    const newAccess = await refreshAccessToken();
    if (!newAccess) throw await toApiError(res);
    res = await exec(newAccess);
  }
  if (!res.ok) throw await toApiError(res);
  return res.blob();
}

/**
 * multipart/form-data upload with progress. `fetch` exposes no upload
 * progress, so this one call uses XMLHttpRequest; the 401 → refresh → retry
 * rule from `request()` is preserved.
 */
function requestUpload<T>(
  path: string,
  form: FormData,
  onProgress?: (percent: number) => void,
  signal?: AbortSignal,
): Promise<T> {
  const exec = (accessToken: string | null, allowRetry: boolean): Promise<T> =>
    new Promise<T>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", buildUrl(path));
      if (accessToken) xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
      xhr.setRequestHeader("X-Client-Id", getClientId());
      // Content-Type is left unset on purpose: the browser adds the boundary.
      xhr.responseType = "text";

      if (onProgress && xhr.upload) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            onProgress(Math.round((event.loaded / event.total) * 100));
          }
        };
      }

      const fail = (status: number, body: string) => {
        let envelope: ApiErrorEnvelope | null = null;
        try {
          envelope = JSON.parse(body) as ApiErrorEnvelope;
        } catch {
          // non-JSON body
        }
        if (envelope?.error) {
          reject(
            new ApiError(
              status,
              envelope.error.code,
              envelope.error.message,
              envelope.error.details ?? {},
              envelope.error.request_id,
            ),
          );
          return;
        }
        reject(
          new ApiError(
            status,
            status >= 500 ? "server_error" : "bad_request",
            `Faylni yuklab bo'lmadi (status ${status}).`,
          ),
        );
      };

      xhr.onload = async () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(xhr.responseText ? (JSON.parse(xhr.responseText) as T) : (undefined as T));
          return;
        }
        if (xhr.status === 401 && allowRetry) {
          const newAccess = await refreshAccessToken();
          if (newAccess) {
            exec(newAccess, false).then(resolve, reject);
            return;
          }
        }
        fail(xhr.status, xhr.responseText);
      };
      xhr.onerror = () =>
        reject(
          new ApiError(
            0,
            "bad_request",
            MUTATIONS.errUploadNetwork,
          ),
        );
      xhr.onabort = () => reject(new DOMException("Bekor qilindi", "AbortError"));
      if (signal) signal.addEventListener("abort", () => xhr.abort(), { once: true });

      xhr.send(form);
    });

  return exec(useAuthStore.getState().accessToken, true);
}

export const api = {
  /** Authenticated binary GET — attachment download / image preview. */
  blob: requestBlob,
  /** multipart POST with upload progress (attachments). */
  upload: requestUpload,
  /**
   * `options.auth: false` — public endpointlar uchun (masalan
   * `invitations/lookup/`): Authorization header ilinmaydi va 401 bo'lsa
   * token yangilash urinishi bo'lmaydi.
   */
  get<T>(
    path: string,
    query?: Query,
    options?: Omit<RequestOptions, "method" | "body" | "query">,
  ) {
    return request<T>(path, { ...options, query });
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
  delete<T = void>(
    path: string,
    body?: unknown,
    options?: Omit<RequestOptions, "method" | "body">,
  ) {
    return request<T>(path, { ...options, method: "DELETE", body });
  },
};
