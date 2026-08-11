import * as React from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { keys } from "@/lib/keys";
import { useAuthStore } from "@/stores/auth-store";
import type {
  AppNotification,
  ChatMessage,
  Comment,
  Conversation,
  GroupedTasksResponse,
  Invitation,
  InvitationLookup,
  List,
  Member,
  MemberProfile,
  MyPermissions,
  Paginated,
  PermissionCatalog,
  RolePermissionMatrix,
  SearchResponse,
  SpaceMember,
  Tag,
  Task,
  TaskAttachment,
  User,
  UserSearchResponse,
  Workspace,
  WorkspaceActivity,
  WorkspaceTree,
} from "@/types/api";

/**
 * Serverning `max_page_size` (§1.5). Bundan kattasini so'rash `400
 * validation_error` beradi, shuning uchun "hammasini bitta so'rovda" degan
 * joylar shu chegara bilan cheklanadi.
 */
const MAX_PAGE_SIZE = 100;

function useAuthed() {
  return useAuthStore((s) => s.status === "authenticated");
}

export function useMe() {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.me,
    queryFn: () => api.get<User>("me/"),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useWorkspaces() {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.workspaces,
    queryFn: () => api.get<Paginated<Workspace>>("workspaces/"),
    enabled,
    staleTime: 60_000,
  });
}

export function useWorkspace(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.workspace(workspaceId),
    queryFn: () => api.get<Workspace>(`workspaces/${workspaceId}/`),
    enabled: enabled && !!workspaceId,
    staleTime: 60_000,
  });
}

export function useWorkspaceTree(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.tree(workspaceId),
    queryFn: () => api.get<WorkspaceTree>(`workspaces/${workspaceId}/tree/`),
    enabled: enabled && !!workspaceId,
    staleTime: 30_000,
  });
}

export function useMembers(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.members(workspaceId),
    queryFn: () =>
      api.get<Paginated<Member>>(`workspaces/${workspaceId}/members/`, {
        page_size: MAX_PAGE_SIZE,
      }),
    enabled: enabled && !!workspaceId,
    staleTime: 60_000,
  });
}

/**
 * `GET workspaces/{id}/members/{userId}/profile/` (§4.1) — the header, the
 * counters and the space breakdown of the member profile page in one request.
 * Every number is already scoped to the caller's visibility server-side, so
 * the client never re-filters. Requires `member.read`; pass `canRead: false`
 * to skip a request that would 403.
 */
export function useMemberProfile(workspaceId: string, userId: string, canRead = true) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.memberProfile(workspaceId, userId),
    queryFn: () =>
      api.get<MemberProfile>(
        `workspaces/${workspaceId}/members/${userId}/profile/`,
      ),
    enabled: enabled && !!workspaceId && !!userId && canRead,
    retry: false,
    staleTime: 30_000,
  });
}

/**
 * `GET workspaces/{id}/activity/` (§10.8) — the workspace history feed,
 * newest first. `actorId` maps to `?actor=`; pass `null` for everybody.
 * Requires `task.read`.
 */
export function useWorkspaceActivity(
  workspaceId: string,
  actorId: string | null,
  canRead = true,
) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.activity(workspaceId, actorId),
    queryFn: () =>
      api.get<Paginated<WorkspaceActivity>>(`workspaces/${workspaceId}/activity/`, {
        actor: actorId ?? undefined,
        page_size: 50,
      }),
    enabled: enabled && !!workspaceId && canRead,
    staleTime: 30_000,
  });
}

/**
 * Tasks assigned to ONE member across the workspace (§10.5 `assignee=<uuid>`).
 * Same shape and ordering as `useMyTasks`, so the profile page can reuse the
 * dashboard's due-date bucketing verbatim.
 */
export function useMemberTasks(workspaceId: string, userId: string, canRead = true) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.workspaceTasks(workspaceId, `user:${userId}`),
    queryFn: () =>
      api.get<Paginated<Task>>(`workspaces/${workspaceId}/tasks/`, {
        assignee: userId,
        ordering: "due_date",
        page_size: MAX_PAGE_SIZE,
      }),
    enabled: enabled && !!workspaceId && !!userId && canRead,
    staleTime: 30_000,
  });
}

export function useInvitations(workspaceId: string, canRead: boolean) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.invitations(workspaceId),
    queryFn: () =>
      api.get<Paginated<Invitation>>(`workspaces/${workspaceId}/invitations/`),
    enabled: enabled && !!workspaceId && canRead,
  });
}

export function useTags(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.tags(workspaceId),
    queryFn: () =>
      api.get<Paginated<Tag>>(`workspaces/${workspaceId}/tags/`, { page_size: MAX_PAGE_SIZE }),
    enabled: enabled && !!workspaceId,
    staleTime: 60_000,
  });
}

export function useList(listId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.list(listId),
    queryFn: () => api.get<List>(`lists/${listId}/`),
    enabled: enabled && !!listId,
    staleTime: 30_000,
  });
}

/**
 * Doska/ro'yxat uchun guruhlangan javob (§10.4).
 *
 * Javob DOIM to'rtta guruhni `STATUS_ORDER` tartibida qaytaradi — ustunlar
 * shu yerdan chiziladi, klient ularni o'zi yasamaydi va endi hech qanday
 * "status set" so'rovi yo'q.
 */
export function useGroupedTasks(listId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.tasksGrouped(listId),
    queryFn: () =>
      api.get<GroupedTasksResponse>(`lists/${listId}/tasks/`, {
        group_by: "status",
      }),
    enabled: enabled && !!listId,
  });
}

/**
 * Tasks assigned to the caller across the whole workspace (contract §10.5:
 * `assignee=me`). Due-date buckets are derived on the client from this single
 * response — the server `due=` filters overlap (an overdue task is also inside
 * `this_week`), which would duplicate rows across sections.
 */
export function useMyTasks(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.workspaceTasks(workspaceId, "mine"),
    queryFn: () =>
      api.get<Paginated<Task>>(`workspaces/${workspaceId}/tasks/`, {
        assignee: "me",
        ordering: "due_date",
        page_size: MAX_PAGE_SIZE,
      }),
    enabled: enabled && !!workspaceId,
    staleTime: 30_000,
  });
}

/**
 * One workspace-wide task page. It backs BOTH dashboard consumers — the
 * per-member open-task counters and the "Jamoa vazifalari" view grouped by
 * assignee — from a single cache entry, so neither adds a request per member.
 * `canRead` mirrors `task.read`; pass `false` to skip a guaranteed-empty read.
 * The server already drops tasks in spaces the caller cannot see, so the
 * client never re-filters for visibility.
 */
export function useWorkspaceTasks(workspaceId: string, canRead = true) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.workspaceTasks(workspaceId, "all"),
    queryFn: () =>
      api.get<Paginated<Task>>(`workspaces/${workspaceId}/tasks/`, {
        page_size: MAX_PAGE_SIZE,
      }),
    enabled: enabled && !!workspaceId && canRead,
    staleTime: 60_000,
  });
}

export function useTask(taskId: string | null) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.task(taskId ?? ""),
    queryFn: () => api.get<Task>(`tasks/${taskId}/`),
    enabled: enabled && !!taskId,
  });
}

export function useComments(taskId: string | null) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.comments(taskId ?? ""),
    queryFn: () =>
      api.get<Paginated<Comment>>(`tasks/${taskId}/comments/`, { page_size: 100 }),
    enabled: enabled && !!taskId,
  });
}

/**
 * Attachments of a task (§10.7). `canRead` mirrors `attachment.read`, which
 * every role holds by default — pass `false` only when the matrix revoked it,
 * so the panel does not fire a request that is guaranteed to 403.
 */
export function useAttachments(taskId: string | null, canRead = true) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.attachments(taskId ?? ""),
    queryFn: () =>
      api.get<Paginated<TaskAttachment>>(`tasks/${taskId}/attachments/`, {
        page_size: 100,
      }),
    enabled: enabled && !!taskId && canRead,
  });
}

// ---------------------------------------------------------------------------
// §18 Permissions (docs/DESIGN_PERMISSIONS.md §D.1–D.5)
// ---------------------------------------------------------------------------

/**
 * Watches a freshly-observed `catalog_version` and unfreezes the cached
 * catalog when the server has moved on.
 *
 * Why this is needed: `usePermissionCatalog` caches with `staleTime` **and**
 * `gcTime: Infinity`, which is not a cache but a value pinned for the life of
 * the tab. Deploy a catalog change and an open session keeps rendering the old
 * labels, groups and code set — including the set of codes the settings matrix
 * is able to display at all — with no way back short of a hard reload.
 * `catalog_version` is the server's counter for exactly that event; this is
 * what makes it bind.
 *
 * Fails safe on absence. A missing version on either side — an older server
 * that omits the field, or no catalog fetched yet — does nothing, so a server
 * without the field can never push the client into a refetch loop. It
 * invalidates rather than refetching imperatively, so TanStack refetches the
 * catalog only where it is actually mounted; and because the effect is keyed on
 * the observed version, a failed refetch cannot re-trigger it either.
 */
function useCatalogVersionGuard(observed: number | undefined): void {
  const queryClient = useQueryClient();
  React.useEffect(() => {
    if (typeof observed !== "number") return;
    const cached = queryClient.getQueryData<PermissionCatalog>(keys.permissionCatalog);
    if (typeof cached?.catalog_version !== "number") return;
    if (cached.catalog_version === observed) return;
    // `isInvalidated` overrides `staleTime: Infinity` on the next fetch
    // opportunity, so this reaches unmounted consumers on their next mount too.
    void queryClient.invalidateQueries({ queryKey: keys.permissionCatalog });
  }, [observed, queryClient]);
}

/**
 * The permission catalog is derived from server *code*, not from the database:
 * it only ever changes on deploy. `staleTime: Infinity` keeps it to one fetch
 * per session (risk R4 — never add a round trip per screen); a catalog bump is
 * picked up by {@link useCatalogVersionGuard} instead of by polling.
 */
export function usePermissionCatalog() {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.permissionCatalog,
    queryFn: () => api.get<PermissionCatalog>("permissions/"),
    enabled,
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

/**
 * The caller's own effective permissions — every UI affordance in the
 * workspace is gated off this single request. Available to any member,
 * guests included. Invalidated by the `permission.updated` WS frame.
 */
export function useMyPermissions(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.myPermissions(workspaceId),
    queryFn: () => api.get<MyPermissions>(`workspaces/${workspaceId}/my-permissions/`),
    enabled: enabled && !!workspaceId,
    staleTime: 5 * 60_000,
  });
}

/**
 * The full role × permission matrix. Requires `workspace.manage_permissions`
 * (owner-only by default), so the caller passes `canRead` to avoid a
 * guaranteed 403. `version` is the optimistic-concurrency token.
 */
export function useRolePermissions(workspaceId: string, canRead: boolean) {
  const enabled = useAuthed();
  const query = useQuery({
    queryKey: keys.rolePermissions(workspaceId),
    queryFn: () =>
      api.get<RolePermissionMatrix>(`workspaces/${workspaceId}/role-permissions/`),
    enabled: enabled && !!workspaceId && canRead,
    staleTime: 30_000,
  });
  // The matrix is the only payload that carries a *fresh* `catalog_version` to
  // the client: `GET my-permissions/` answers with the workspace's
  // `permissions_version` (a different counter entirely) and does not send the
  // catalog one at all. This screen is also where a frozen catalog does the
  // most damage — it renders every label and group straight out of it.
  useCatalogVersionGuard(query.data?.catalog_version);
  return query;
}

/**
 * `GET spaces/{id}/members/` (§D.6) — bo'lim jamoasi.
 *
 * O'qish uchun alohida ruxsat kodi yo'q: bo'limni ko'ra olgan har qanday a'zo
 * jamoani ham ko'radi (yozish esa `space.manage_members` yoki lokal `manager`
 * talab qiladi). Ko'rinmaydigan bo'lim 404 beradi — shuning uchun retry yo'q.
 */
export function useSpaceMembers(spaceId: string | null) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.spaceMembers(spaceId ?? ""),
    queryFn: () =>
      api.get<Paginated<SpaceMember>>(`spaces/${spaceId}/members/`, { page_size: MAX_PAGE_SIZE }),
    enabled: enabled && !!spaceId,
    retry: false,
    staleTime: 30_000,
  });
}

/**
 * `GET invitations/lookup/?token=` — PUBLIC endpoint, shuning uchun
 * `auth: false` bilan chaqiriladi (chaqiruvchi tizimga kirmagan bo'lishi
 * mumkin). Noma'lum/eskirgan token → 404; retry qilinmaydi.
 */
export function useInvitationLookup(token: string) {
  return useQuery({
    queryKey: keys.invitationLookup(token),
    queryFn: () =>
      api.get<InvitationLookup>("invitations/lookup/", { token }, { auth: false }),
    enabled: !!token,
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

/**
 * Bitta qidiruv javobi va u **aynan qaysi so'rovga** tegishli ekani.
 *
 * `placeholderData: keepPreviousData` yozayotgan paytda oldingi javobni ekranda
 * ushlab turadi, ya'ni ro'yxat har bir yangi so'rovda skeletonga tushib
 * miltillamaydi. Lekin TanStack Query o'sha javob qaysi kalitdan qolganini
 * aytmaydi — shuning uchun so'rov matnini (va ish maydonini) javobning o'ziga
 * bog'lab qo'yamiz. Shunda sarlavha, `Highlight` va a'zolar filtri doim
 * ekrandagi natijalarga mos matnni ishlatadi va «xyz» bo'yicha 12 ta natija deb
 * turib `abc` ning natijalari chizilib qolmaydi.
 */
export interface SearchResult {
  workspaceId: string;
  /** `?q=` — javob aynan shu matn uchun olingan. */
  query: string;
  response: SearchResponse;
}

export function useWorkspaceSearch(workspaceId: string, q: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.search(workspaceId, q),
    queryFn: async (): Promise<SearchResult> => ({
      workspaceId,
      query: q,
      response: await api.get<SearchResponse>(`workspaces/${workspaceId}/search/`, { q }),
    }),
    enabled: enabled && !!workspaceId && q.trim().length >= 2,
    placeholderData: keepPreviousData,
  });
}

// ---------------------------------------------------------------------------
// §19 Bildirishnomalar
// ---------------------------------------------------------------------------

/**
 * `GET notifications/?workspace=` — qo'ng'iroqcha menyusi va
 * `/w/{id}/notifications` sahifasi shu bitta kesh yozuvidan o'qiydi.
 *
 * Ish maydoni bo'yicha filtrlanadi: qo'ng'iroqcha ish maydoni layout'ida
 * turadi, ya'ni «boshqa ish maydonidagi voqea» bu yerda shovqin bo'lardi.
 * Barcha ish maydonlari kerak bo'lsa `workspaceId` ga `null` beriladi.
 *
 * Sahifa hajmi QAT'IY: menyu ham, sahifa ham AYNAN bir kesh yozuvidan
 * o'qiydi, menyu esa birinchi bir nechtasini o'zi kesib oladi. Har biri
 * o'z `page_size` i bilan so'raganda kalit bir xil, javob esa har xil
 * bo'lardi — ikkisi bir-birining ma'lumotini almashtirib turardi.
 *
 * `enabled` — qo'ng'iroqcha ro'yxatni faqat menyu ochilganda so'raydi;
 * nishon uchun arzon `unread-count/` yetarli.
 */
const NOTIFICATIONS_PAGE_SIZE = 50;

export function useNotifications(workspaceId: string | null, enabled = true) {
  const authed = useAuthed();
  return useQuery({
    queryKey: keys.notifications(workspaceId),
    queryFn: () =>
      api.get<Paginated<AppNotification>>("notifications/", {
        workspace: workspaceId ?? undefined,
        page_size: NOTIFICATIONS_PAGE_SIZE,
      }),
    enabled: authed && enabled,
    staleTime: 30_000,
  });
}

/**
 * O'qilmaganlar soni — nishon uchun alohida, ARZON so'rov. Ro'yxatning
 * o'zi faqat menyu ochilganda kerak, nishon esa doim ekranda turadi.
 * `notification.created` freymi ikkalasini ham bekor qiladi.
 */
export function useUnreadNotificationCount(workspaceId: string | null) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.notificationsUnread(workspaceId),
    queryFn: () =>
      api.get<{ count: number }>("notifications/unread-count/", {
        workspace: workspaceId ?? undefined,
      }),
    enabled,
    staleTime: 30_000,
  });
}

/**
 * `GET workspaces/{id}/user-search/?q=` — ro'yxatdan o'tgan foydalanuvchilar.
 * Server 2 belgidan qisqa so'rovga bo'sh javob beradi; shu shart bu yerda ham
 * takrorlanadi, ya'ni bir harf yozilganda so'rov umuman ketmaydi.
 * `canSearch` — `member.invite`; usiz so'rov 403 bo'lardi.
 */
export function useUserSearch(workspaceId: string, q: string, canSearch: boolean) {
  const enabled = useAuthed();
  const query = q.trim();
  return useQuery({
    queryKey: keys.userSearch(workspaceId, query),
    queryFn: () =>
      api.get<UserSearchResponse>(`workspaces/${workspaceId}/user-search/`, {
        q: query,
      }),
    enabled: enabled && !!workspaceId && canSearch && query.length >= 2,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

/** Ish maydonidagi ko'rinadigan suhbatlar (kanallar + o'z DM'laringiz). */
export function useConversations(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.conversations(workspaceId),
    queryFn: () =>
      api.get<Paginated<Conversation>>(`workspaces/${workspaceId}/chat/channels/`),
    enabled: enabled && !!workspaceId,
  });
}

export function useChatMessages(conversationId: string | null) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.chatMessages(conversationId ?? "none"),
    queryFn: () =>
      api.get<Paginated<ChatMessage>>(`chat/conversations/${conversationId}/messages/`, {
        page_size: 100,
      }),
    enabled: enabled && !!conversationId,
  });
}
