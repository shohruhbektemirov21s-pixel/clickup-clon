import { format, formatDistanceToNow, isPast, isToday } from "date-fns";
import { uz } from "date-fns/locale";
import type { Priority, StatusType } from "@/types/api";

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

export function isOverdue(iso: string | null, statusType?: StatusType): boolean {
  if (!iso) return false;
  if (statusType === "closed") return false;
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

export const PRIORITIES: Priority[] = ["urgent", "high", "normal", "low", "none"];

export const PRIORITY_META: Record<Priority, { label: string; className: string }> = {
  urgent: { label: "Juda muhim", className: "text-priority-urgent" },
  high: { label: "Yuqori", className: "text-priority-high" },
  normal: { label: "O'rtacha", className: "text-priority-normal" },
  low: { label: "Past", className: "text-priority-low" },
  none: { label: "Muhimlik yo'q", className: "text-priority-none" },
};

export const STATUS_TYPE_COLOR: Record<StatusType, string> = {
  open: "#87909E",
  active: "#4194F6",
  closed: "#6BC950",
};

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
