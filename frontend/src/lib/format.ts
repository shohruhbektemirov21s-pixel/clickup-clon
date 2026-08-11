import { format, formatDistanceToNow, isPast, isToday } from "date-fns";
import { uz } from "date-fns/locale";
import { isClosedStatus, PRIORITY_CLASS, PRIORITY_LABEL, PRIORITY_ORDER } from "@/i18n/uz";
import type { Priority, TaskStatus } from "@/types/api";

/**
 * Ekranda ko'rsatiladigan ism.
 *
 * `UserSummary.email` mehmon rolidagi *ko'ruvchi* uchun `null` bo'ladi (§4),
 * shuning uchun `full_name || email` shakli `null` ni matnga aylantirib
 * "null a'zoni chiqarish" kabi e'lonlar hosil qilardi.
 */
export function displayName(
  user: { full_name?: string | null; email?: string | null } | null | undefined,
): string {
  if (!user) return "Foydalanuvchi";
  return user.full_name?.trim() || user.email || "Foydalanuvchi";
}

export function initials(name: string | null | undefined, email?: string): string {
  const source = (name && name.trim()) || email || "?";
  const parts = source.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

export function formatDueDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isToday(d)) return "Bugun";
  return format(d, d.getFullYear() === new Date().getFullYear() ? "d MMM" : "d MMM, yyyy", {
    locale: uz,
  });
}

/**
 * Muddat o'tganmi. Yopilgan vazifa hech qachon "kechikkan" emas — v1.4.0 dan
 * buni `status === "done"` hal qiladi; holat turi degan alohida maydon yo'q.
 */
export function isOverdue(iso: string | null, status?: TaskStatus): boolean {
  if (!iso) return false;
  if (status && isClosedStatus(status)) return false;
  const d = new Date(iso);
  return isPast(d) && !isToday(d);
}

export function timeAgo(iso: string): string {
  return formatDistanceToNow(new Date(iso), { addSuffix: true, locale: uz });
}

/**
 * Human file size in Uzbek notation — decimal comma, e.g. `2,4 MB`.
 * Binary units (1 KB = 1024 B) to match what the server counts.
 */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  // One decimal below 100, none above — "980 KB", not "980,4 KB".
  const rounded = value >= 100 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${String(rounded).replace(".", ",")} ${units[unit]}`;
}

/**
 * Muhimlik yorliqlari YAGONA manbadan — `src/i18n/uz.ts`. Bu yerda faqat
 * qayta eksport turadi, chunki chaqiruvchilar tarixan `@/lib/format` dan
 * o'qiydi; ikkinchi ta'rif YOZILMASIN.
 */
export const PRIORITIES: readonly Priority[] = PRIORITY_ORDER;

export const PRIORITY_META: Record<Priority, { label: string; className: string }> =
  Object.fromEntries(
    PRIORITY_ORDER.map((p) => [p, { label: PRIORITY_LABEL[p], className: PRIORITY_CLASS[p] }]),
  ) as Record<Priority, { label: string; className: string }>;

/** Plain text → minimal rich-text pair (both fields must travel together). */
export function textToRichBody(text: string): {
  body_html: string;
  body_json: unknown;
} {
  const escaped = escapeHtml(text.trim());
  const html = escaped
    .split(/\n+/)
    .map((line) => `<p>${line}</p>`)
    .join("");
  return {
    body_html: html,
    body_json: {
      type: "doc",
      content: text
        .trim()
        .split(/\n+/)
        .map((line) => ({
          type: "paragraph",
          content: line ? [{ type: "text", text: line }] : [],
        })),
    },
  };
}

export function richBodyToText(html: string | null): string {
  if (!html) return "";
  return html
    .replace(/<\/p>\s*<p>/g, "\n")
    .replace(/<br\s*\/?>/g, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .trim();
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
