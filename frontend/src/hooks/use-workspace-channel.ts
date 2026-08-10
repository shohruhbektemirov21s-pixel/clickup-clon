"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { WS_BASE_URL } from "@/lib/env";
import { getClientId } from "@/lib/client-id";
import { keys } from "@/lib/keys";
import { refreshAccessToken } from "@/lib/api";
import {
  realtimeHandshakeQuery,
  WS_CLOSE_ACCESS_REVOKED,
} from "@/hooks/use-list-channel";
import { useAuthStore } from "@/stores/auth-store";
import type { WsAccessRevokedData, WsFrame } from "@/types/api";

/** Three-state badge vocabulary for workspace-wide views. */
export type WorkspaceConnectionStatus = "connecting" | "live" | "offline";

/** Consecutive failed connects before the badge admits we are offline. */
const OFFLINE_AFTER_ATTEMPTS = 3;

/** Coalescing window — a burst of frames costs one refetch, not one each. */
const FLUSH_MS = 120;

/**
 * §15 — native WebSocket to ws://<host>/ws/workspaces/{workspace_id}/?ticket=…
 *
 * The workspace channel carries the frames that no single list channel can
 * cover: `task.*` for every list the caller can read, `list.updated` for the
 * sidebar/tree, and `permission.updated`. Unlike `useListChannel` this hook
 * never patches task rows in place — a workspace-wide view is assembled from
 * server-side filters (`assignee=me`, visible spaces, pagination) that the
 * client cannot re-evaluate, so the frames are used purely as invalidation
 * signals and the refetch stays authoritative.
 *
 * Same wire discipline as the list channel: a fresh single-use handshake
 * ticket (§15.1) on every (re)connect, exponential backoff 1s → 30s with
 * jitter, a terminal 4403 close when access is revoked, `connection.ack`
 * gates the "live" state, `event_id` makes application idempotent, and frames
 * carrying this tab's own `client_id` are dropped (its mutations already
 * updated the cache).
 */
export function useWorkspaceChannel(
  workspaceId: string | null,
): WorkspaceConnectionStatus {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((s) => s.accessToken);
  const authenticated = useAuthStore((s) => s.status === "authenticated");
  const [status, setStatus] = React.useState<WorkspaceConnectionStatus>("connecting");
  const seenEvents = React.useRef<Set<string>>(new Set());

  React.useEffect(() => {
    if (!workspaceId || !authenticated || !accessToken) return;

    let socket: WebSocket | null = null;
    let closed = false;
    let attempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let flushTimer: ReturnType<typeof setTimeout> | null = null;
    let hadConnection = false;
    const clientId = getClientId();
    const seen = seenEvents.current;
    const pending = { tasks: false, tree: false, permissions: false };

    const flush = () => {
      flushTimer = null;
      if (pending.tasks) {
        // Prefix key — both dashboard scopes ("mine" and "all") at once.
        void queryClient.invalidateQueries({
          queryKey: keys.workspaceTasksRoot(workspaceId),
        });
      }
      if (pending.tree) {
        void queryClient.invalidateQueries({ queryKey: keys.tree(workspaceId) });
      }
      if (pending.permissions) {
        void queryClient.invalidateQueries({
          queryKey: keys.myPermissions(workspaceId),
        });
        void queryClient.invalidateQueries({
          queryKey: keys.rolePermissions(workspaceId),
        });
      }
      pending.tasks = false;
      pending.tree = false;
      pending.permissions = false;
    };

    const schedule = (what: Partial<typeof pending>) => {
      Object.assign(pending, what);
      if (flushTimer === null) flushTimer = setTimeout(flush, FLUSH_MS);
    };

    const applyFrame = (frame: WsFrame) => {
      const { type, payload } = frame;
      if (!payload) return;
      // Idempotency: same event_id twice = no-op.
      if (payload.event_id) {
        if (seen.has(payload.event_id)) return;
        seen.add(payload.event_id);
        if (seen.size > 500) {
          const first = seen.values().next().value;
          if (first) seen.delete(first);
        }
      }
      // Echo suppression: this tab's own mutations already wrote the cache.
      if (payload.actor?.client_id && payload.actor.client_id === clientId) return;

      switch (type) {
        case "connection.ack": {
          attempt = 0;
          setStatus("live");
          // No server-side replay: after a gap the refetch is authoritative.
          if (hadConnection) schedule({ tasks: true, tree: true });
          hadConnection = true;
          break;
        }
        case "task.created":
        case "task.updated":
        case "task.moved":
        case "task.deleted": {
          // `tree` carries every list's open_task_count → the stat cards.
          schedule({ tasks: true, tree: true });
          break;
        }
        case "list.updated": {
          schedule({ tree: true });
          break;
        }
        case "permission.updated": {
          schedule({ permissions: true });
          break;
        }
        case "access.revoked": {
          // §D.10 — arrives on the private `user.<id>` group, which this
          // socket also joins. The caller just lost a space (or the whole
          // workspace), so everything scoped by visibility is now stale:
          // the tree, the task lists and the caller's own permission set.
          schedule({ permissions: true, tasks: true, tree: true });
          const spaceId = (payload.data as WsAccessRevokedData | undefined)?.space_id;
          if (spaceId) {
            void queryClient.invalidateQueries({ queryKey: keys.spaceMembers(spaceId) });
          }
          break;
        }
        default:
          // comment.*/attachment.*/presence.* belong to the list channel.
          break;
      }
    };

    const connect = async () => {
      if (closed) return;
      setStatus(attempt >= OFFLINE_AFTER_ATTEMPTS ? "offline" : "connecting");
      let token = useAuthStore.getState().accessToken;
      if (!token) token = await refreshAccessToken();
      if (!token || closed) {
        setStatus("offline");
        return;
      }
      // §15.1 — bir martalik chipta; chipta olinmasa deprecated `?token=`.
      const query = await realtimeHandshakeQuery(token);
      if (closed) return;
      socket = new WebSocket(`${WS_BASE_URL}/ws/workspaces/${workspaceId}/?${query}`);
      socket.onmessage = (event) => {
        try {
          applyFrame(JSON.parse(event.data as string) as WsFrame);
        } catch {
          // Malformed frame — ignore.
        }
      };
      socket.onclose = (event) => {
        if (closed) return;
        if (event.code === WS_CLOSE_ACCESS_REVOKED) {
          // Workspace a'zoligi bekor qilindi — qayta ulanishning ma'nosi yo'q.
          closed = true;
          setStatus("offline");
          schedule({ tasks: true, tree: true, permissions: true });
          return;
        }
        attempt += 1;
        setStatus(attempt >= OFFLINE_AFTER_ATTEMPTS ? "offline" : "connecting");
        const backoff = Math.min(1000 * 2 ** (attempt - 1), 30_000);
        const jitter = backoff * (0.5 + Math.random() * 0.5);
        reconnectTimer = setTimeout(connect, jitter);
      };
      socket.onerror = () => {
        socket?.close();
      };
    };

    void connect();

    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (flushTimer) clearTimeout(flushTimer);
      socket?.close();
    };
    // accessToken deliberately excluded: token rotation must not tear the
    // socket down — a fresh token is read from the store on each (re)connect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, authenticated, queryClient]);

  return status;
}
