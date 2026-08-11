import * as React from "react";
import { CornerDownRight, Pencil, Send, Trash2 } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useComments } from "@/hooks/queries";
import {
  useCreateComment,
  useDeleteComment,
  useUpdateComment,
} from "@/hooks/mutations";
import type { ListPermissions } from "@/components/list/use-list-permissions";
import { initials, richBodyToText, textToRichBody, timeAgo } from "@/lib/format";
import type { Comment } from "@/types/api";

/**
 * Vazifa kommentlari (§12).
 *
 * Ilgari bu yerda rol tekshiruvi turardi (`isAuthor || isAdmin`), kompozitor
 * esa umuman gate qilinmagan edi. Endi qaror to'liq kodlarga tayanadi:
 * `comment.create`, `comment.update_own`, `comment.delete_own`,
 * `comment.delete_any` — serverdagi `CommentDetailView` bilan bir xil mantiq
 * (muallif invarianti ruxsatdan USTUN: `comment.update_any` kodi yo'q).
 */
export function CommentsThread({
  taskId,
  perms,
}: {
  taskId: string;
  perms: ListPermissions;
}) {
  const { data, isPending } = useComments(taskId);
  const [replyTo, setReplyTo] = React.useState<Comment | null>(null);

  const comments = data?.results ?? [];
  const topLevel = comments.filter((c) => !c.parent_id);
  const repliesByParent = new Map<string, Comment[]>();
  for (const c of comments) {
    if (c.parent_id) {
      const arr = repliesByParent.get(c.parent_id) ?? [];
      arr.push(c);
      repliesByParent.set(c.parent_id, arr);
    }
  }

  // Javob ham yangi komment — `comment.create` bo'lmasa tugma ko'rsatilmaydi.
  const canReply = perms.canCreateComment;

  return (
    <div className="flex flex-col px-6 py-4">
      <h3 className="mb-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        Kommentlar {data ? `(${data.count})` : ""}
      </h3>

      {isPending ? (
        <div className="flex flex-col gap-3" aria-hidden>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex gap-2">
              <Skeleton className="size-7 rounded-full" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-3 w-32" />
                <Skeleton className="h-4 w-4/5" />
              </div>
            </div>
          ))}
        </div>
      ) : topLevel.length === 0 ? (
        <p className="mb-3 text-sm text-muted-foreground">
          {canReply
            ? "Hozircha kommentlar yo'q. Suhbatni boshlang."
            : "Hozircha kommentlar yo'q."}
        </p>
      ) : (
        <ul className="flex flex-col gap-4">
          {topLevel.map((comment) => (
            <li key={comment.id}>
              <CommentItem
                taskId={taskId}
                comment={comment}
                perms={perms}
                onReply={canReply ? () => setReplyTo(comment) : undefined}
              />
              {(repliesByParent.get(comment.id) ?? []).map((reply) => (
                <div key={reply.id} className="mt-3 ml-9">
                  <CommentItem taskId={taskId} comment={reply} perms={perms} />
                </div>
              ))}
            </li>
          ))}
        </ul>
      )}

      {canReply ? (
        <Composer taskId={taskId} replyTo={replyTo} onClearReply={() => setReplyTo(null)} />
      ) : (
        <p className="mt-4 text-xs text-muted-foreground">
          {perms.isLoading
            ? "Ruxsatlar tekshirilmoqda…"
            : "Bu vazifaga komment yozish uchun ruxsatingiz yo'q."}
        </p>
      )}
    </div>
  );
}

function CommentItem({
  taskId,
  comment,
  perms,
  onReply,
}: {
  taskId: string;
  comment: Comment;
  perms: ListPermissions;
  onReply?: () => void;
}) {
  const updateComment = useUpdateComment(taskId);
  const deleteComment = useDeleteComment(taskId);
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState("");

  const authorId = comment.author?.id;
  const canEdit = perms.canEditComment(authorId);
  const canDelete = perms.canDeleteComment(authorId);
  const text = richBodyToText(comment.body_html);

  const commitEdit = () => {
    setEditing(false);
    const trimmed = draft.trim();
    if (!trimmed || trimmed === text) return;
    updateComment.mutate({
      commentId: comment.id,
      body: textToRichBody(trimmed),
    });
  };

  return (
    <div className="group flex gap-2.5">
      <Avatar className="mt-0.5 size-7">
        {comment.author?.avatar ? <AvatarImage src={comment.author.avatar} alt="" /> : null}
        <AvatarFallback
          className="text-[10px] font-semibold text-primary-foreground"
          style={{ backgroundColor: comment.author?.avatar_color || "#87909E" }}
        >
          {comment.author ? initials(comment.author.full_name, comment.author.email ?? undefined) : "?"}
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {comment.author
              ? comment.author.full_name || comment.author.email
              : "O'chirilgan foydalanuvchi"}
          </span>
          <span className="text-xs text-muted-foreground">
            {timeAgo(comment.created_at)}
            {comment.is_edited ? " · tahrirlangan" : ""}
          </span>
          <span className="ml-auto flex opacity-0 transition-opacity group-hover:opacity-100">
            {onReply ? (
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label="Javob yozish"
                onClick={onReply}
              >
                <CornerDownRight />
              </Button>
            ) : null}
            {canEdit ? (
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label="Kommentni tahrirlash"
                onClick={() => {
                  setDraft(text);
                  setEditing(true);
                }}
              >
                <Pencil />
              </Button>
            ) : null}
            {canDelete ? (
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label="Kommentni o'chirish"
                className="text-danger"
                disabled={deleteComment.isPending}
                onClick={() => deleteComment.mutate(comment.id)}
              >
                <Trash2 />
              </Button>
            ) : null}
          </span>
        </div>
        {editing ? (
          <Textarea
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") commitEdit();
              if (e.key === "Escape") setEditing(false);
            }}
            rows={2}
            className="mt-1"
          />
        ) : (
          <p className="text-sm whitespace-pre-wrap">{text}</p>
        )}
      </div>
    </div>
  );
}

function Composer({
  taskId,
  replyTo,
  onClearReply,
}: {
  taskId: string;
  replyTo: Comment | null;
  onClearReply: () => void;
}) {
  const createComment = useCreateComment(taskId);
  const [draft, setDraft] = React.useState("");

  /**
   * Qoralamani FAQAT muvaffaqiyatdan keyin tozalaymiz. Ilgari `mutate` dan
   * so'ng darhol `setDraft("")` chaqirilardi — 403 / 429 / oflaynda
   * yozilgan matn qaytarib bo'lmaydigan darajada yo'qolardi.
   */
  const send = async () => {
    const trimmed = draft.trim();
    if (!trimmed) return;
    try {
      await createComment.mutateAsync({
        ...textToRichBody(trimmed),
        parent_id: replyTo?.id ?? null,
      });
      setDraft("");
      onClearReply();
    } catch {
      // Xato toast'i mutatsiyaning `onError` idan chiqadi; qoralama joyida
      // qoladi, foydalanuvchi qayta yuborishi mumkin.
    }
  };

  return (
    <div className="mt-4">
      {replyTo ? (
        <div className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground">
          <CornerDownRight className="size-3" />
          Javob:{" "}
          {replyTo.author
            ? replyTo.author.full_name || replyTo.author.email
            : "O'chirilgan foydalanuvchi"}
          <button className="text-primary hover:underline" onClick={onClearReply}>
            Bekor qilish
          </button>
        </div>
      ) : null}
      <div className="flex items-end gap-2">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Komment yozing..."
          rows={2}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              void send();
            }
          }}
        />
        <Button
          size="icon-sm"
          aria-label="Yuborish"
          disabled={!draft.trim() || createComment.isPending}
          onClick={() => void send()}
        >
          <Send />
        </Button>
      </div>
    </div>
  );
}
