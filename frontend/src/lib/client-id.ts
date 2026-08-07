/**
 * Per-tab client id (§1.4 of the contract). Sent as X-Client-Id on every
 * mutating request; the server echoes it as `actor.client_id` in WebSocket
 * frames so this tab can suppress its own echoes.
 */
let cached: string | null = null;

export function getClientId(): string {
  if (typeof window === "undefined") return "server";
  if (cached) return cached;
  const key = "clickish.client-id";
  let id = window.sessionStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    window.sessionStorage.setItem(key, id);
  }
  cached = id;
  return id;
}
