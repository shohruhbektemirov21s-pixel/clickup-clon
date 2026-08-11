import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { WS_BASE_URL } from "@/lib/env";
import { keys } from "@/lib/keys";
import { useAuthStore } from "@/stores/auth-store";
import { fetchRealtimeTicket } from "@/hooks/use-list-channel";
import type { ChatMessage, Paginated } from "@/types/api";

/**
 * `ws/chat/{id}/` — bitta suhbatning real vaqtli kanali.
 *
 * `use-list-channel.ts` dagi chipta olish mantiqi QAYTA ISHLATILADI
 * (`fetchRealtimeTicket`): access token URL'ga chiqmasligi qoidasi ikkala
 * kanal uchun bir xil bo'lishi kerak, va uni ikkinchi marta yozish
 * ertami-kechmi ajralib ketardi.
 *
 * Soket faqat O'QIYDI: yuborish REST orqali. Kelgan xabar keshning boshiga
 * qo'shiladi; o'z xabaringiz mutatsiya javobidan allaqachon keshda
 * bo'lgani uchun `id` bo'yicha takrorlanish tekshiriladi.
 */
export function useChatChannel(conversationId: string | null) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((s) => s.accessToken);
  const authenticated = useAuthStore((s) => s.status === "authenticated");
  const [connected, setConnected] = React.useState(false);

  React.useEffect(() => {
    if (!conversationId || !authenticated || !accessToken) return;

    let socket: WebSocket | null = null;
    let closed = false;
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const append = (message: ChatMessage) => {
      queryClient.setQueryData<Paginated<ChatMessage>>(
        keys.chatMessages(conversationId),
        (old) => {
          if (!old) return old;
          if (old.results.some((m) => m.id === message.id)) return old;
          // Tarix `-created_at` bo'yicha keladi, ya'ni eng yangisi boshida.
          return { ...old, count: old.count + 1, results: [message, ...old.results] };
        },
      );
    };

    const connect = async () => {
      if (closed) return;
      let ticket: string | null = null;
      try {
        ticket = await fetchRealtimeTicket(accessToken);
      } catch {
        // Vaqtinchalik nosozlik — backoff bilan qayta urinamiz.
      }
      if (closed) return;
      if (!ticket) {
        schedule();
        return;
      }

      const url = `${WS_BASE_URL}/ws/chat/${conversationId}/?ticket=${encodeURIComponent(ticket)}`;
      socket = new WebSocket(url);

      socket.onmessage = (event) => {
        let frame: { type?: string; payload?: { data?: unknown } };
        try {
          frame = JSON.parse(event.data as string);
        } catch {
          return;
        }
        if (frame.type === "connection.ack") {
          attempt = 0;
          setConnected(true);
          return;
        }
        if (frame.type === "chat.message.created" && frame.payload?.data) {
          append(frame.payload.data as ChatMessage);
          // Ro'yxatdagi "oxirgi xabar" va o'qilmaganlar soni ham yangilansin.
          queryClient.invalidateQueries({ queryKey: ["workspace"], exact: false });
        }
      };
      socket.onclose = () => {
        setConnected(false);
        if (!closed) schedule();
      };
      socket.onerror = () => socket?.close();
    };

    const schedule = () => {
      if (closed) return;
      // 1s → 2s → 4s … 30s gacha.
      const delay = Math.min(1000 * 2 ** attempt, 30_000);
      attempt += 1;
      timer = setTimeout(connect, delay);
    };

    void connect();

    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, [conversationId, authenticated, accessToken, queryClient]);

  return { connected };
}
