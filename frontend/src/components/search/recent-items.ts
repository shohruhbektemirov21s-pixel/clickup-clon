/**
 * "Yaqinda ochilganlar" — command palette bo'sh bo'lganda ko'rsatiladigan
 * oxirgi ochilgan vazifa/ro'yxatlar. Zustand emas: bu server holati ham,
 * UI holati ham emas — u brauzerda saqlanadigan, sahifa yangilangandan keyin
 * ham yashaydigan mayda ma'lumot. Shuning uchun oddiy `localStorage` helper.
 *
 * Kalit `clickish.recent` (docs/UI_SPEC.md §S12.6). Yozuvlar bitta massivda
 * saqlanadi va `workspaceId` bo'yicha filtrlanadi, chunki foydalanuvchi bir
 * nechta ish maydonida ishlashi mumkin va ro'yxatlar aralashib ketmasligi
 * kerak.
 */

import * as React from "react";

export type RecentKind = "task" | "list";

export interface RecentItem {
  kind: RecentKind;
  /** Vazifa yoki ro'yxat id'si. */
  id: string;
  workspaceId: string;
  title: string;
  /** Bosilganda o'tiladigan manzil. */
  href: string;
  /** Kontekst yo'li, masalan "Product › Q3 Roadmap › Sprint 24". */
  path: string;
  /** `Date.now()` — saralash uchun. */
  at: number;
}

const STORAGE_KEY = "clickish.recent";
/** Bitta ish maydoni uchun ko'rsatiladigan yozuvlar soni. */
export const RECENT_LIMIT = 5;
/** Umumiy saqlanadigan yozuvlar soni — localStorage'ni shishirmaslik uchun. */
const MAX_STORED = 50;

function isRecentItem(value: unknown): value is RecentItem {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    (v.kind === "task" || v.kind === "list") &&
    typeof v.id === "string" &&
    typeof v.workspaceId === "string" &&
    typeof v.title === "string" &&
    typeof v.href === "string" &&
    typeof v.path === "string" &&
    typeof v.at === "number"
  );
}

function readAll(): RecentItem[] {
  // SSR'da ham, private-mode'da localStorage o'chirilganda ham yiqilmasin.
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isRecentItem);
  } catch {
    return [];
  }
}

function writeAll(items: RecentItem[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_STORED)));
  } catch {
    // Kvota to'lgan yoki storage bloklangan — bu funksiya hech qachon
    // navigatsiyani to'xtatmasligi kerak.
  }
}

/** Ish maydoni uchun oxirgi {@link RECENT_LIMIT} ta yozuv, yangisi birinchi. */
export function readRecent(workspaceId: string): RecentItem[] {
  return readAll()
    .filter((item) => item.workspaceId === workspaceId)
    .sort((a, b) => b.at - a.at)
    .slice(0, RECENT_LIMIT);
}

/** Yozuvni ro'yxat boshiga qo'yadi; bir xil element ikki marta turmaydi. */
export function pushRecent(item: Omit<RecentItem, "at">): void {
  const rest = readAll().filter(
    (existing) => !(existing.id === item.id && existing.kind === item.kind),
  );
  writeAll([{ ...item, at: Date.now() }, ...rest]);
  invalidate();
}

/** Faqat berilgan ish maydonining yozuvlarini o'chiradi. */
export function clearRecent(workspaceId: string): void {
  writeAll(readAll().filter((item) => item.workspaceId !== workspaceId));
  invalidate();
}

/**
 * Hammasini o'chiradi — `useLogout` chaqiradi. Yozuvlar `localStorage` da
 * yashaydi, ya'ni sahifa yangilansa ham qoladi: tozalanmasa shu brauzerda
 * keyin kirgan foydalanuvchi oldingi odamning vazifa nomlarini "Yaqinda
 * ochilganlar" ro'yxatida ko'radi.
 */
export function clearAllRecent(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage bloklangan — chiqish jarayoni baribir to'xtamasligi kerak.
  }
  invalidate();
}

// ---------------------------------------------------------------------------
// React bilan bog'lash
// ---------------------------------------------------------------------------

/**
 * `localStorage` — tashqi store, shuning uchun uni `useEffect` + `setState`
 * bilan emas, `useSyncExternalStore` bilan o'qiymiz: SSR'da bo'sh ro'yxat,
 * gidratatsiyadan keyin haqiqiy qiymat, boshqa tabdagi o'zgarish esa `storage`
 * hodisasi orqali yetib keladi.
 *
 * Snapshot keshlanadi — `useSyncExternalStore` har renderda bir xil havolani
 * ko'rishi shart, aks holda cheksiz render halqasiga tushadi.
 */
const EMPTY_RECENT: RecentItem[] = [];
const snapshots = new Map<string, RecentItem[]>();
const listeners = new Set<() => void>();

function invalidate(): void {
  snapshots.clear();
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  if (listeners.size === 1 && typeof window !== "undefined") {
    window.addEventListener("storage", invalidate);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && typeof window !== "undefined") {
      window.removeEventListener("storage", invalidate);
    }
  };
}

function getSnapshot(workspaceId: string): RecentItem[] {
  let cached = snapshots.get(workspaceId);
  if (!cached) {
    cached = readRecent(workspaceId);
    snapshots.set(workspaceId, cached);
  }
  return cached;
}

export function useRecentItems(workspaceId: string): RecentItem[] {
  return React.useSyncExternalStore(
    subscribe,
    () => getSnapshot(workspaceId),
    () => EMPTY_RECENT,
  );
}
