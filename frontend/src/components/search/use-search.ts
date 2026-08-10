"use client";

/**
 * Qidiruv so'rovi uchun umumiy klient mantiq: 250 ms debounce, "kamida 2 belgi"
 * qoidasi va miltillashga qarshi "oldingi natijani saqlab turish".
 *
 * Tarmoq qatlami — `useWorkspaceSearch`. Eskirgan so'rovni TanStack Query o'zi
 * bekor qiladi, ya'ni kech kelgan javob hech qachon yangisini bosib ketmaydi.
 * Miltillashni esa o'sha hook'dagi `placeholderData: keepPreviousData` to'xtatib
 * turadi: so'rov kaliti o'zgarganda `data: undefined` bo'lib qolmaydi, oldingi
 * javob yangisi kelguncha ekranda qoladi.
 *
 * Muhimi — javob **qaysi so'rovga tegishli ekani** (`SearchResult.query`)
 * javobning o'zi bilan birga keladi va bu yerdan {@link SearchState.resultQuery}
 * bo'lib chiqadi. Sarlavha, `Highlight` va a'zolar filtri o'sha matnni ishlatadi,
 * `debouncedQuery` ni emas — aks holda ekranda `abc` ning natijalari turib,
 * sarlavha «abcd» bo'yicha 12 ta natija deb yozib qo'yardi.
 *
 * Bu yerda modul darajasidagi kesh yo'q: hamma narsa TanStack Query ichida
 * yashaydi, ya'ni `useLogout` dagi `queryClient.clear()` bitta brauzerda ketma-ket
 * kirgan ikki foydalanuvchi orasida hech narsa qoldirmasligiga kafolat beradi.
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

export interface SearchState {
  /** Ko'rsatiladigan javob — doim {@link SearchState.resultQuery} ga tegishli. */
  data: SearchResponse | undefined;
  /**
   * `data` aynan qaysi so'rovga tegishli. Ekranga chiqadigan hamma narsa —
   * sarlavha, `Highlight`, a'zolar filtri — shu matnni ishlatishi kerak.
   */
  resultQuery: string;
  /**
   * Debounce'dan o'tgan, haqiqatda so'ralgan matn. Foydalanuvchi nimani
   * so'raganini bildiradi (URL sinxroni, "barcha natijalar" havolasi), ekranda
   * nima turganini emas — buning uchun {@link SearchState.resultQuery} bor.
   */
  debouncedQuery: string;
  /** So'rov 2 belgidan qisqa (bo'sh so'rov ham shu holatda). */
  isTooShort: boolean;
  /** Hali ko'rsatadigan hech narsa yo'q — skeleton chiqadi. */
  isInitialLoading: boolean;
  /** Yozilyapti yoki so'rov uchmoqda — kichik spinner chiqadi. */
  isSyncing: boolean;
  /** Ekranda oldingi so'rov natijalari turibdi (xiralashtirib ko'rsatiladi). */
  isStale: boolean;
  isError: boolean;
  refetch: () => void;
}

export function useSearch(workspaceId: string, rawQuery: string): SearchState {
  const trimmed = rawQuery.trim();
  const debouncedQuery = useDebouncedValue(trimmed);
  const isTooShort = trimmed.length < MIN_QUERY_LENGTH;

  const query = useWorkspaceSearch(workspaceId, debouncedQuery);

  // `keepPreviousData` kalit o'zgarganda oldingi javobni qaytaradi — shu
  // jumladan ish maydoni almashganda ham. Boshqa ish maydonining natijasini
  // ko'rsatmaymiz.
  const result =
    query.data && query.data.workspaceId === workspaceId ? query.data : undefined;

  const isSettling = debouncedQuery !== trimmed;
  const data = isTooShort ? undefined : result?.response;

  return {
    data,
    resultQuery: data ? (result?.query ?? "") : "",
    debouncedQuery,
    isTooShort,
    isInitialLoading: !isTooShort && !data && !query.isError,
    isSyncing: !isTooShort && (isSettling || query.isFetching),
    isStale: !!data && result?.query !== debouncedQuery,
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
