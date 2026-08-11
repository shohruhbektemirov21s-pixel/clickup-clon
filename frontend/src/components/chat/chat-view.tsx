"use client";

import * as React from "react";
import { Hash, Loader2, Lock, MessageSquarePlus, Plus, Send, Users } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useChatMessages, useConversations, useMe, useMembers } from "@/hooks/queries";
import {
  useCreateChannel,
  useJoinConversation,
  useOpenDirect,
  useSendMessage,
} from "@/hooks/mutations";
import { useChatChannel } from "@/hooks/use-chat-channel";
import { displayName, initials } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ChatMessage, Conversation } from "@/types/api";

function Bubble({ message, mine }: { message: ChatMessage; mine: boolean }) {
  const author = message.author;
  return (
    <li className={cn("flex gap-2.5", mine && "flex-row-reverse")}>
      <Avatar className="size-7 shrink-0">
        {author?.avatar ? <AvatarImage src={author.avatar} alt="" /> : null}
        <AvatarFallback
          className="text-[10px] font-semibold text-primary-foreground"
          style={{ backgroundColor: author?.avatar_color || "#7B68EE" }}
        >
          {initials(author?.full_name ?? "", undefined)}
        </AvatarFallback>
      </Avatar>
      <div className={cn("min-w-0 max-w-[70%]", mine && "text-right")}>
        <p className="text-[11px] text-muted-foreground">
          {author ? displayName(author) : "O'chirilgan hisob"}{" "}
          <time dateTime={message.created_at}>
            {new Date(message.created_at).toLocaleTimeString("uz-UZ", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </time>
        </p>
        {/* Matn ATAYLAB matn sifatida chiziladi — server ham HTML qabul
            qilmaydi (`Message.body` oddiy matn). */}
        <p
          className={cn(
            "mt-0.5 inline-block rounded-xl px-3 py-1.5 text-sm break-words whitespace-pre-wrap",
            mine ? "bg-primary text-primary-foreground" : "bg-muted",
          )}
        >
          {message.body}
        </p>
      </div>
    </li>
  );
}

function NewChannelDialog({ workspaceId }: { workspaceId: string }) {
  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const create = useCreateChannel(workspaceId);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    await create.mutateAsync({ name: name.trim() });
    setName("");
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={<Button variant="ghost" size="icon-sm" aria-label="Kanal qo'shish" />}
      >
        <Plus />
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>Yangi kanal</DialogTitle>
            <DialogDescription>
              Kanal ish maydonining barcha a&apos;zolariga ko&apos;rinadi.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="masalan: umumiy"
            className="my-4"
            autoFocus
            maxLength={80}
          />
          <DialogFooter>
            <Button type="submit" disabled={!name.trim() || create.isPending}>
              {create.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
              Yaratish
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PeoplePicker({ workspaceId }: { workspaceId: string }) {
  const [open, setOpen] = React.useState(false);
  const { data: me } = useMe();
  const { data: members } = useMembers(workspaceId);
  const openDirect = useOpenDirect(workspaceId);

  const others = (members?.results ?? []).filter((m) => m.user.id !== me?.id);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={<Button variant="ghost" size="icon-sm" aria-label="Yozishma boshlash" />}
      >
        <MessageSquarePlus />
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Kimga yozasiz?</DialogTitle>
          <DialogDescription>Ish maydoni a&apos;zolaridan birini tanlang.</DialogDescription>
        </DialogHeader>
        <ul className="mt-2 max-h-80 overflow-y-auto">
          {others.length === 0 ? (
            <li className="py-6 text-center text-sm text-muted-foreground">
              Ish maydonida boshqa a&apos;zo yo&apos;q.
            </li>
          ) : (
            others.map((member) => (
              <li key={member.id}>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left hover:bg-muted"
                  onClick={async () => {
                    await openDirect.mutateAsync(member.user.id);
                    setOpen(false);
                  }}
                >
                  <Avatar className="size-7">
                    {member.user.avatar ? <AvatarImage src={member.user.avatar} alt="" /> : null}
                    <AvatarFallback
                      className="text-[10px] font-semibold text-primary-foreground"
                      style={{ backgroundColor: member.user.avatar_color || "#7B68EE" }}
                    >
                      {initials(member.user.full_name, member.user.email ?? undefined)}
                    </AvatarFallback>
                  </Avatar>
                  <span className="truncate text-sm">{displayName(member.user)}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      </DialogContent>
    </Dialog>
  );
}

function Composer({
  workspaceId,
  conversation,
}: {
  workspaceId: string;
  conversation: Conversation;
}) {
  const [text, setText] = React.useState("");
  const send = useSendMessage(workspaceId, conversation.id);
  const join = useJoinConversation(workspaceId);

  if (!conversation.is_member) {
    return (
      <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
        <p className="text-sm text-muted-foreground">
          Yozish uchun avval kanalga qo&apos;shiling.
        </p>
        <Button size="sm" onClick={() => join.mutate(conversation.id)} disabled={join.isPending}>
          Qo&apos;shilish
        </Button>
      </div>
    );
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const body = text.trim();
    if (!body) return;
    setText("");
    await send.mutateAsync(body);
  };

  return (
    <form onSubmit={submit} className="flex items-end gap-2 border-t px-4 py-3">
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          // Enter — yuborish, Shift+Enter — yangi qator. Chat uchun odatiy
          // kutilma; aks holda har xabar uchun sichqoncha kerak bo'lardi.
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void submit(e);
          }
        }}
        placeholder="Xabar yozing…"
        rows={1}
        maxLength={4000}
        className="max-h-32 min-h-9 resize-none"
      />
      <Button type="submit" size="icon" disabled={!text.trim() || send.isPending} aria-label="Yuborish">
        {send.isPending ? <Loader2 className="animate-spin" /> : <Send />}
      </Button>
    </form>
  );
}

export function ChatView({ workspaceId }: { workspaceId: string }) {
  const { data: conversations, isPending } = useConversations(workspaceId);
  const { data: me } = useMe();
  const [activeId, setActiveId] = React.useState<string | null>(null);

  const rows = conversations?.results ?? [];
  // Tanlanmagan bo'lsa birinchisini ko'rsatamiz — bo'sh o'ng panel
  // foydalanuvchini "nima bosishim kerak" holatida qoldirardi.
  const active = rows.find((c) => c.id === activeId) ?? rows[0] ?? null;

  const { data: messages } = useChatMessages(active?.id ?? null);
  const { connected } = useChatChannel(active?.id ?? null);

  // Tarix `-created_at` bilan keladi; ekranda eskisi tepada bo'lishi kerak.
  const ordered = React.useMemo(
    () => [...(messages?.results ?? [])].reverse(),
    [messages],
  );

  return (
    <div className="flex min-h-0 flex-1">
      <aside className="flex w-64 shrink-0 flex-col border-r">
        <header className="flex items-center gap-1 border-b px-3 py-2.5">
          <h2 className="flex-1 text-sm font-semibold">Suhbatlar</h2>
          <PeoplePicker workspaceId={workspaceId} />
          <NewChannelDialog workspaceId={workspaceId} />
        </header>
        <ul className="min-h-0 flex-1 overflow-y-auto p-1.5">
          {isPending ? (
            <li className="px-2 py-4 text-sm text-muted-foreground">Yuklanmoqda…</li>
          ) : rows.length === 0 ? (
            <li className="px-2 py-4 text-xs leading-relaxed text-muted-foreground">
              Hali suhbat yo&apos;q. Yuqoridagi tugmalar bilan kanal oching yoki
              hamkasbingizga yozing.
            </li>
          ) : (
            rows.map((conversation) => (
              <li key={conversation.id}>
                <button
                  type="button"
                  onClick={() => setActiveId(conversation.id)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm",
                    conversation.id === active?.id
                      ? "bg-primary/10 font-medium text-primary"
                      : "text-muted-foreground hover:bg-muted",
                  )}
                >
                  {conversation.kind === "channel" ? (
                    conversation.is_private ? (
                      <Lock className="size-3.5 shrink-0" />
                    ) : (
                      <Hash className="size-3.5 shrink-0" />
                    )
                  ) : (
                    <Users className="size-3.5 shrink-0" />
                  )}
                  <span className="min-w-0 flex-1 truncate">{conversation.title}</span>
                  {conversation.unread > 0 ? (
                    <span className="shrink-0 rounded-full bg-primary px-1.5 text-[10px] font-semibold text-primary-foreground">
                      {conversation.unread}
                    </span>
                  ) : null}
                </button>
              </li>
            ))
          )}
        </ul>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        {active ? (
          <>
            <header className="flex items-center gap-2 border-b px-4 py-2.5">
              <h1 className="truncate text-sm font-semibold">{active.title}</h1>
              {active.topic ? (
                <span className="truncate text-xs text-muted-foreground">{active.topic}</span>
              ) : null}
              <span className="ml-auto flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <span
                  className={cn(
                    "size-1.5 rounded-full",
                    connected ? "bg-status-closed" : "bg-muted-foreground/40",
                  )}
                />
                {connected ? "Jonli" : "Ulanmoqda…"}
              </span>
            </header>

            <ul className="flex min-h-0 flex-1 flex-col-reverse gap-3 overflow-y-auto px-4 py-4">
              {/* `flex-col-reverse` — yangi xabar kelganda ro'yxat o'zi
                  pastda qoladi, qo'lda scroll qilish shart emas. */}
              {[...ordered].reverse().map((message) => (
                <Bubble
                  key={message.id}
                  message={message}
                  mine={!!me && message.author?.id === me.id}
                />
              ))}
              {ordered.length === 0 ? (
                <li className="py-8 text-center text-sm text-muted-foreground">
                  Hali xabar yo&apos;q — birinchi bo&apos;lib yozing.
                </li>
              ) : null}
            </ul>

            <Composer workspaceId={workspaceId} conversation={active} />
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center p-12 text-center text-sm text-muted-foreground">
            Chapdan suhbat tanlang yoki yangisini oching.
          </div>
        )}
      </section>
    </div>
  );
}
