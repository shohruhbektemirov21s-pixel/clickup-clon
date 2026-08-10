"use client";

/**
 * Qidiruv so'rovi uchun umumiy klient mantiq: 250 ms debounce, "kamida 2 belgi"
 * qoidasi va miltillashga qarshi "oldingi natijani saqlab turish".
 *
 * Tarmoq qatlami — mavjud `useWorkspaceSearch` (`hooks/` fayllariga tegilmaydi).
 * Eskirgan so'rovni TanStack Query o'zi bekor qiladi, ya'ni kech kelgan javob
 * hech qachon yangisini bosib ketmaydi. Lekin so'rov kaliti o'zgarganda hook
 * bir lahzaga `data: undefined` qaytaradi va ro'yxat miltillaydi — `hooks/`
 * ichida `placeholderData: keepPreviousData` qo'sha olmaganimiz uchun oxirgi
 * muvaffaqiyatli javob shu modulning kichik tashqi store'ida saqlanadi va
 * `useSyncExternalStore` orqali o'qiladi.
 */

import * as React from "react";
import { useWorkspaceSearch } from "@/hooks/queries";
import type {
  Folder,
  List,
  Member,
  SearchResponse,
  SearchResultItem,
  Space,
  Task,
} from "@/types/api";

/** Serverdagi qoida bilan bir xil: 1 belgi doim bo'sh natija qaytaradi. */
export const MIN_QUERY_LENGTH = 2;
export const SEARCH_DEBOUNCE_MS = 250;

export function useDebouncedValue<T>(value: T, delay: number = SEARCH_DEBOUNCE_MS): T {
  const [debounced, setDebounced] = React.useState(value);

  React.useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

// ---------------------------------------------------------------------------
// `keepPreviousData` o'rnini bosuvchi mayda tashqi store
// ---------------------------------------------------------------------------

const lastResponse = new Map<string, SearchResponse>();
const responseListeners = new Set<() => void>();

function rememberResponse(workspaceId: string, data: SearchResponse): void {
  if (lastResponse.get(workspaceId) === data) return;
  lastResponse.set(workspaceId, data);
  for (const listener of responseListeners) listener();
}

function subscribeResponse(listener: () => void): () => void {
  responseListeners.add(listener);
  return () => {
    responseListeners.delete(listener);
  };
}

export interface SearchState {
  /** Ko'rsatiladigan javob — yangisi hali kelmagan bo'lsa, oldingisi. */
  data: SearchResponse | undefined;
  /** Debounce'dan o'tgan, haqiqatda so'ralgan matn. */
  debouncedQuery: string;
  /** So'rov 2 belgidan qisqa (bo'sh so'rov ham shu holatda). */
  isTooShort: boolean;
  /** Hali ko'rsatadigan hech narsa yo'q — skeleton chiqadi. */
  isInitialLoading: boolean;
  /** Yozilyapti yoki so'rov uchmoqda — kichik spinner chiqadi. */
  isSyncing: boolean;
  /** Ekrandagi natijalar eskirgan (yangi so'rov javobini kutmoqda). */
  isStale: boolean;
  isError: boolean;
  refetch: () => void;
}

export function useSearch(workspaceId: string, rawQuery: string): SearchState {
  const trimmed = rawQuery.trim();
  const debouncedQuery = useDebouncedValue(trimmed);
  const isTooShort = trimmed.length < MIN_QUERY_LENGTH;

  const query = useWorkspaceSearch(workspaceId, debouncedQuery);

  const cached = React.useSyncExternalStore(
    subscribeResponse,
    () => lastResponse.get(workspaceId),
    () => undefined,
  );

  React.useEffect(() => {
    if (query.data) rememberResponse(workspaceId, query.data);
  }, [query.data, workspaceId]);

  const isSettling = debouncedQuery !== trimmed;
  const data = isTooShort ? undefined : (query.data ?? cached);

  return {
    data,
    debouncedQuery,
    isTooShort,
    isInitialLoading: !isTooShort && !data && !query.isError,
    isSyncing: !isTooShort && (isSettling || query.isFetching),
    isStale: !isTooShort && !query.data && !!cached,
    isError: query.isError,
    refetch: () => void query.refetch(),
  };
}

// ---------------------------------------------------------------------------
// Natijalarni turlarga ajratish
// ---------------------------------------------------------------------------

export interface GroupedResults {
  tasks: Task[];
  lists: List[];
  folders: Folder[];
  spaces: Space[];
  total: number;
}

export const EMPTY_GROUPS: GroupedResults = {
  tasks: [],
  lists: [],
  folders: [],
  spaces: [],
  total: 0,
};

export function groupResults(results: SearchResultItem[] | undefined): GroupedResults {
  if (!results || results.length === 0) return EMPTY_GROUPS;
  const groups: GroupedResults = {
    tasks: [],
    lists: [],
    folders: [],
    spaces: [],
    total: results.length,
  };
  for (const result of results) {
    switch (result.type) {
      case "task":
        groups.tasks.push(result.item);
        break;
      case "list":
        groups.lists.push(result.item);
        break;
      case "folder":
        groups.folders.push(result.item);
        break;
      case "space":
        groups.spaces.push(result.item);
        break;
    }
  }
  return groups;
}

/**
 * A'zolar qidiruvi serverda yo'q (§13 faqat task/list/folder/space qaytaradi),
 * shuning uchun keshlangan a'zolar ro'yxati klientda filtrlanadi.
 */
export function filterMembers(members: Member[], query: string, limit = 5): Member[] {
  const needle = query.trim().toLowerCase();
  if (needle.length < MIN_QUERY_LENGTH) return [];
  return members
    .filter(
      (member) =>
        member.user.full_name.toLowerCase().includes(needle) ||
        (member.user.email?.toLowerCase().includes(needle) ?? false),
    )
    .slice(0, limit);
}
