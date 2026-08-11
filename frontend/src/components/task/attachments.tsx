import * as React from "react";
import {
  Download,
  File as FileIcon,
  FileArchive,
  FileImage,
  FileSpreadsheet,
  FileText,
  Loader2,
  Paperclip,
  Presentation,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useAttachments } from "@/hooks/queries";
import { useDeleteAttachment, useUploadAttachment } from "@/hooks/mutations";
import type { ListPermissions } from "@/components/list/use-list-permissions";
import { api, isApiError } from "@/lib/api";
import { formatFileSize, timeAgo } from "@/lib/format";
import {
  ATTACHMENT_ALLOWED_EXTENSIONS,
  ATTACHMENT_MAX_BYTES,
  type TaskAttachment,
} from "@/types/api";

const ALLOWED = new Set<string>(ATTACHMENT_ALLOWED_EXTENSIONS);
const MAX_MB = Math.round(ATTACHMENT_MAX_BYTES / (1024 * 1024));

function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot + 1).toLowerCase();
}

function isImage(attachment: TaskAttachment): boolean {
  return attachment.content_type.startsWith("image/");
}

function IconFor({ attachment }: { attachment: TaskAttachment }) {
  const ext = extensionOf(attachment.original_name);
  const className = "size-5 shrink-0";
  if (isImage(attachment)) return <FileImage className={`${className} text-sky-500`} />;
  if (ext === "pdf") return <FileText className={`${className} text-red-500`} />;
  if (ext === "xls" || ext === "xlsx" || ext === "csv")
    return <FileSpreadsheet className={`${className} text-emerald-600`} />;
  if (ext === "ppt" || ext === "pptx")
    return <Presentation className={`${className} text-orange-500`} />;
  if (ext === "zip") return <FileArchive className={`${className} text-amber-600`} />;
  if (ext === "doc" || ext === "docx")
    return <FileText className={`${className} text-blue-600`} />;
  if (ext === "txt" || ext === "md")
    return <FileText className={`${className} text-muted-foreground`} />;
  return <FileIcon className={`${className} text-muted-foreground`} />;
}

/**
 * Image preview. The download endpoint requires the Authorization header, so
 * `<img src={download_url}>` would 401 — the bytes are fetched once and served
 * from an object URL that is revoked on unmount.
 */
function Thumbnail({ attachment }: { attachment: TaskAttachment }) {
  const [url, setUrl] = React.useState<string | null>(null);

  React.useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    api
      .blob(`attachments/${attachment.id}/download/`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        /* fall back to the icon */
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [attachment.id]);

  if (!url) return <IconFor attachment={attachment} />;
  return (
    // Oddiy `<img>` — manba `blob:` URL, tashqi rasm emas (ilgari bu yerda
    // `next/image` qoidasini o'chiruvchi izoh turardi).
    <img
      src={url}
      alt={attachment.original_name}
      className="size-9 shrink-0 rounded border object-cover"
    />
  );
}

async function downloadAttachment(attachment: TaskAttachment) {
  try {
    const blob = await api.blob(`attachments/${attachment.id}/download/`);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = attachment.original_name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    // Revoking immediately can race the download in some browsers.
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (err) {
    toast.error(
      isApiError(err) && err.status !== 0
        ? err.message
        : "Faylni yuklab bo'lmadi. Tarmoq aloqasini tekshiring.",
    );
  }
}

/**
 * "Fayllar" section of the task panel (§10.7).
 *
 * Deliberately stays enabled for completed (closed) tasks — attaching the
 * final report *after* the work is done is the whole point of the feature.
 *
 * `attachment.*` kodlari bo'lim doirasida hal qilinadi (`perms`), chunki
 * server ham `has_space_perm` ni chaqiradi: bo'lim `viewer` i fayl ko'radi,
 * lekin yuklay ham, o'chira ham olmaydi.
 */
export function TaskAttachments({
  taskId,
  perms,
}: {
  taskId: string;
  perms: ListPermissions;
}) {
  const canRead = perms.canReadAttachments;
  const canUpload = perms.canUploadAttachment;
  const { data, isPending } = useAttachments(taskId, canRead);
  const upload = useUploadAttachment(taskId);
  const remove = useDeleteAttachment(taskId);

  const inputRef = React.useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = React.useState(false);
  const [progress, setProgress] = React.useState<{ name: string; percent: number } | null>(
    null,
  );

  const attachments = data?.results ?? [];

  const rejectReason = (file: File): string | null => {
    const ext = extensionOf(file.name);
    if (!ext || !ALLOWED.has(ext)) {
      return `«${file.name}» turi qo'llab-quvvatlanmaydi. Ruxsat etilgan turlar: ${ATTACHMENT_ALLOWED_EXTENSIONS.join(", ")}.`;
    }
    if (file.size === 0) return `«${file.name}» bo'sh fayl.`;
    if (file.size > ATTACHMENT_MAX_BYTES) {
      return `«${file.name}» juda katta (${formatFileSize(file.size)}). Chegara — ${MAX_MB} MB.`;
    }
    return null;
  };

  const send = async (files: FileList | File[]) => {
    for (const file of Array.from(files)) {
      // Client-side gate is a courtesy only — the server re-validates size,
      // extension and MIME type on every request.
      const reason = rejectReason(file);
      if (reason) {
        toast.error(reason);
        continue;
      }
      setProgress({ name: file.name, percent: 0 });
      try {
        await upload.mutateAsync({
          file,
          onProgress: (percent) => setProgress({ name: file.name, percent }),
        });
      } catch {
        // toast already raised by the mutation
      } finally {
        setProgress(null);
      }
    }
  };

  if (!canRead) return null;

  return (
    <div
      className="px-6 py-4"
      onDragOver={(e) => {
        if (!canUpload) return;
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        if (!canUpload) return;
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files.length) void send(e.dataTransfer.files);
      }}
    >
      <h3 className="mb-3 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        <Paperclip className="size-3.5" />
        Fayllar {data ? `(${data.count})` : ""}
      </h3>

      {isPending ? (
        <div className="flex flex-col gap-2" aria-hidden>
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : attachments.length === 0 ? (
        <p className="mb-3 text-sm text-muted-foreground">
          Hozircha fayl biriktirilmagan.
        </p>
      ) : (
        <ul className="mb-3 flex flex-col gap-1.5">
          {attachments.map((attachment) => (
            <AttachmentRow
              key={attachment.id}
              attachment={attachment}
              canDelete={perms.canDeleteAttachment(attachment.uploaded_by?.id)}
              onDelete={() => remove.mutate(attachment.id)}
            />
          ))}
        </ul>
      )}

      {progress ? (
        <div className="mb-3">
          <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
            <span className="truncate">{progress.name}</span>
            <span>{progress.percent}%</span>
          </div>
          <Progress value={progress.percent} className="h-1.5" />
        </div>
      ) : null}

      {canUpload ? (
        <div
          className={`flex flex-col items-center gap-1.5 rounded-lg border border-dashed px-4 py-5 text-center transition-colors ${
            dragging ? "border-primary bg-primary/5" : "border-border"
          }`}
        >
          <Upload className="size-5 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Fayllarni shu yerga tashlang yoki
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => inputRef.current?.click()}
            disabled={upload.isPending}
          >
            {upload.isPending ? (
              <>
                <Loader2 className="size-3.5 animate-spin" /> Yuklanmoqda…
              </>
            ) : (
              "Fayl tanlash"
            )}
          </Button>
          <p className="text-xs text-muted-foreground">
            {MAX_MB} MB gacha · {ATTACHMENT_ALLOWED_EXTENSIONS.join(", ")}
          </p>
          <input
            ref={inputRef}
            type="file"
            multiple
            hidden
            aria-label="Fayl tanlash"
            accept={ATTACHMENT_ALLOWED_EXTENSIONS.map((e) => `.${e}`).join(",")}
            onChange={(e) => {
              if (e.target.files?.length) void send(e.target.files);
              e.target.value = ""; // allow re-picking the same file
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

function AttachmentRow({
  attachment,
  canDelete,
  onDelete,
}: {
  attachment: TaskAttachment;
  /** `attachment.delete_own` o'ziniki uchun, `attachment.delete_any` boshqasi. */
  canDelete: boolean;
  onDelete: () => void;
}) {
  const uploader =
    attachment.uploaded_by?.full_name ||
    attachment.uploaded_by?.email ||
    "O'chirilgan foydalanuvchi";

  return (
    <li className="group flex items-center gap-2.5 rounded-md border px-2.5 py-2">
      {isImage(attachment) ? (
        <Thumbnail attachment={attachment} />
      ) : (
        <IconFor attachment={attachment} />
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium" title={attachment.original_name}>
          {attachment.original_name}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {formatFileSize(attachment.size_bytes)} · {uploader} ·{" "}
          {timeAgo(attachment.created_at)}
        </p>
      </div>
      <span className="flex shrink-0 opacity-60 transition-opacity group-hover:opacity-100">
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={`${attachment.original_name} — yuklab olish`}
          onClick={() => void downloadAttachment(attachment)}
        >
          <Download />
        </Button>
        {canDelete ? (
          <Button
            variant="ghost"
            size="icon-xs"
            className="text-danger"
            aria-label={`${attachment.original_name} — o'chirish`}
            onClick={onDelete}
          >
            <Trash2 />
          </Button>
        ) : null}
      </span>
    </li>
  );
}
