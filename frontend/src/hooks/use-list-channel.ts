"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { API_BASE_URL, WS_BASE_URL } from "@/lib/env";
import { getClientId } from "@/lib/client-id";
import { keys } from "@/lib/keys";
import { removeTaskFromGroups, writeTaskEverywhere } from "@/lib/task-cache";
import { refreshAccessToken } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type {
  Comment,
  GroupedTasksResponse,
  Paginated,
  Task,
  TaskAttachment,
  WsAttachmentRemovedData,
  WsCommentDeletedData,
  WsFrame,
  WsTaskDeletedData,
} from "@/types/api";

export type ConnectionStatus = "connecting" | "open" | "reconnecting" | "offline";

/** Server yopish kodlari (§15.1). 4403 = kirish huquqi bekor qilindi. */
export const WS_CLOSE_ACCESS_REVOKED = 4403;

/**
 * §15.1 — bir martalik WS handshake chiptasini oladi.
 *
 * Nega: access token'ni `?token=` da yuborish uni har bir proxy/APM access
 * log'iga yozib qo'yadi. Chipta 30 soniya yashaydi va bir marta ishlaydi,
 * shuning uchun log'dan olingan URL bilan soket ochib bo'lmaydi.
 *
 * `null` qaytsa chaqiruvchi eski `?token=` yo'liga tushadi — eskiroq backend
 * bilan ham ulanish uzilib qolmasligi uchun (deprecated fallback).
 *
 * `use-workspace-channel.ts` ham shu yordamchini import qiladi: mantiq bitta
 * joyda tursin.
 */
export async function fetchRealtimeTicket(accessToken: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/realtime/ticket/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { ticket?: unknown };
    return typeof body.ticket === "string" && body.ticket ? body.ticket : null;
  } catch {
    return null;
  }
}

/** Chipta bo'lsa u bilan, aks holda deprecated token bilan handshake qatori. */
export async function realtimeHandshakeQuery(accessToken: string): Promise<string> {
  const ticket = await fetchRealtimeTicket(accessToken);
  return ticket
    ? `ticket=${encodeURIComponent(ticket)}`
    : `token=${encodeURIComponent(accessToken)}`;
}

/**
 * §15 — native WebSocket to ws://<host>/ws/list/{list_id}/?ticket=<opaque>.
 * Applies task.* / comment.* events to the TanStack Query cache, suppresses
 * this tab's own echoes via actor.client_id, reconnects with exponential
 * backoff (1s → 30s + jitter) and refetches on resume (no server replay).
 * A 4403 close (access revoked) is terminal: no reconnect, cache invalidated.
 */
export function useListChannel(listId: string | null) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((s) => s.accessToken);
  const authenticated = useAuthStore((s) => s.status === "authenticated");
  const [status, setStatus] = React.useState<ConnectionStatus>("connecting");
  const seenEvents = React.useRef<Set<string>>(new Set());

  React.useEffect(() => {
    if (!listId || !authenticated || !accessToken) return;

    let socket: WebSocket | null = null;
    let closed = false;
    let attempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let hadConnection = false;
    const clientId = getClientId();
    const seen = seenEvents.current;

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
      // Echo suppression: drop frames caused by this tab's own mutations.
      if (payload.actor?.client_id && payload.actor.client_id === clientId) return;

      switch (type) {
        case "connection.ack": {
          setStatus("open");
          if (hadConnection) {
            // Refetch is authoritative after a reconnect.
            queryClient.invalidateQueries({ queryKey: keys.tasksRoot(listId) });
          }
          hadConnection = true;
          break;
        }
        case "task.created":
        case "task.updated": {
          writeTaskEverywhere(queryClient, payload.data as Task);
          break;
        }
        case "task.moved": {
          if (payload.rebalanced) {
            queryClient.invalidateQueries({ queryKey: keys.tasksRoot(listId) });
          } else {
            writeTaskEverywhere(queryClient, payload.data as Task);
          }
          break;
        }
        case "task.deleted": {
          const data = payload.data as WsTaskDeletedData;
          queryClient.setQueryData<GroupedTasksResponse>(
            keys.tasksGrouped(listId),
            (old) => removeTaskFromGroups(old, data.id) ?? old,
          );
          queryClient.removeQueries({ queryKey: keys.task(data.id) });
          break;
        }
        case "comment.created": {
          const comment = payload.data as Comment;
          queryClient.setQueryData<Paginated<Comment>>(
            keys.comments(comment.task_id),
            (old) =>
              old && !old.results.some((c) => c.id === comment.id)
                ? { ...old, count: old.count + 1, results: [...old.results, comment] }
                : old,
          );
          queryClient.invalidateQueries({ queryKey: keys.task(comment.task_id) });
          break;
        }
        case "comment.updated": {
          const comment = payload.data as Comment;
          queryClient.setQueryData<Paginated<Comment>>(
            keys.comments(comment.task_id),
            (old) =>
              old
                ? {
                    ...old,
                    results: old.results.map((c) =>
                      c.id === comment.id ? comment : c,
                    ),
                  }
                : old,
          );
          break;
        }
        case "comment.deleted": {
          const data = payload.data as WsCommentDeletedData;
          queryClient.setQueryData<Paginated<Comment>>(
            keys.comments(data.task_id),
            (old) =>
              old
                ? {
                    ...old,
                    count: Math.max(0, old.count - 1),
                    results: old.results.filter((c) => c.id !== data.id),
                  }
                : old,
          );
          break;
        }
        case "attachment.added": {
          const attachment = payload.data as TaskAttachment;
          queryClient.setQueryData<Paginated<TaskAttachment>>(
            keys.attachments(attachment.task_id),
            (old) =>
              old && !old.results.some((a) => a.id === attachment.id)
                ? {
                    ...old,
                    count: old.count + 1,
                    results: [attachment, ...old.results],
                  }
                : old,
          );
          // `attachment_count` lives on the task.
          queryClient.invalidateQueries({ queryKey: keys.task(attachment.task_id) });
          break;
        }
        case "attachment.removed": {
          const data = payload.data as WsAttachmentRemovedData;
          queryClient.setQueryData<Paginated<TaskAttachment>>(
            keys.attachments(data.task_id),
            (old) =>
              old
                ? {
                    ...old,
                    count: Math.max(0, old.count - 1),
                    results: old.results.filter((a) => a.id !== data.id),
                  }
                : old,
          );
          queryClient.invalidateQueries({ queryKey: keys.task(data.task_id) });
          break;
        }
        default:
          // presence.* and error frames are ignored in this hook.
          break;
      }
    };

    const connect = async () => {
      if (closed) return;
      setStatus(attempt === 0 ? "connecting" : "reconnecting");
      let token = useAuthStore.getState().accessToken;
      if (!token) token = await refreshAccessToken();
      if (!token || closed) {
        setStatus("offline");
        return;
      }
      const query = await realtimeHandshakeQuery(token);
      if (closed) return;
      socket = new WebSocket(`${WS_BASE_URL}/ws/list/${listId}/?${query}`);
      socket.onmessage = (event) => {
        try {
          applyFrame(JSON.parse(event.data as string) as WsFrame);
        } catch {
          // Malformed frame — ignore.
        }
      };
      socket.onopen = () => {
        attempt = 0;
      };
      socket.onclose = (event) => {
        if (closed) return;
        if (event.code === WS_CLOSE_ACCESS_REVOKED) {
          // Server a'zolikni bekor qildi (§15.1). Qayta ulanish faqat 403
          // sikliga aylanadi — soketni butunlay tark etamiz va cache'ni
          // yangilaymiz, shunda UI yo'qolgan huquqni darhol aks ettiradi.
          closed = true;
          setStatus("offline");
          void queryClient.invalidateQueries({ queryKey: keys.tasksRoot(listId) });
          return;
        }
        setStatus("reconnecting");
        const backoff = Math.min(1000 * 2 ** attempt, 30_000);
        const jitter = backoff * (0.5 + Math.random() * 0.5);
        attempt += 1;
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
      socket?.close();
    };
    // accessToken deliberately excluded: token rotation must not tear the
    // socket down — a fresh token is read from the store on each (re)connect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listId, authenticated, queryClient]);

  return status;
}
