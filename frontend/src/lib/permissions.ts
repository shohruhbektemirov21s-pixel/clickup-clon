import { COMMON } from "@/i18n/uz";
import type { MyPermissions, PermissionCode, SpaceAccess } from "@/types/api";

/**
 * Permission helpers for UI affordances.
 *
 * ⚠️ SECURITY: `can()` / `canInSpace()` decide only what the UI *shows*.
 * They are a convenience layer over `GET workspaces/{id}/my-permissions/`
 * and can be trivially bypassed from the browser. The server re-checks every
 * permission independently on every request (DESIGN_PERMISSIONS §C.4:
 * 404 → 403 → 400). Never treat a `true` here as authorisation.
 */

/**
 * Local grants a space `manager` (PM) gains inside their own space.
 * Mirrors `SPACE_MANAGER_GRANTS` on the server (DESIGN_PERMISSIONS §B.5,
 * `apps/core/access.py`). `space.delete`, `member.*`, `workspace.*` and
 * `tag.*` are never included. `*.manage_statuses` was dropped in catalog v6
 * — status is a fixed code set now, so there is nothing left to manage.
 */
const SPACE_MANAGER_GRANTS: ReadonlySet<PermissionCode> = new Set<PermissionCode>([
  "space.read",
  "space.update",
  "space.manage_members",
  "folder.create",
  "folder.update",
  "folder.delete",
  "folder.delete_cascade",
  "list.create",
  "list.update",
  "list.delete",
  "list.move",
  "task.read",
  "task.create",
  "task.update",
  "task.update_assigned",
  "task.delete",
  "task.move",
  "task.assign",
  "task.watch",
  "task.restore",
  "task.view_deleted",
  "attachment.read",
  "attachment.create",
  "attachment.delete_own",
  // `attachment.delete_any` is deliberately absent — moderation stays global.
]);

/**
 * Codes a space `viewer` keeps; everything else is cut (§B.5).
 * Kept byte-for-byte in step with `SPACE_VIEWER_GRANTS` in
 * `backend/apps/core/access.py` — a code missing here hides a control the
 * server would have allowed, which is just as wrong as showing one it refuses.
 */
const SPACE_VIEWER_GRANTS: ReadonlySet<PermissionCode> = new Set<PermissionCode>([
  "workspace.read",
  "member.read",
  "space.read",
  "space.read_private",
  "task.read",
  "task.watch",
  "task.view_deleted",
  "attachment.read",
]);

/**
 * Workspace-level check.
 *
 * There is deliberately **no** `role === "owner" → true` short-circuit: the
 * server already expands an owner to the whole catalog when it builds
 * `permissions` (`my_permissions()`, AD-3), and it intersects that list with
 * `READONLY_ALLOWED_CODES` for a read-only account *before* the owner lock.
 * Short-circuiting here would resurrect every write button for a read-only
 * owner and every one of them would 403.
 */
export function can(my: MyPermissions | undefined, code: PermissionCode): boolean {
  if (!my) return false;
  return my.permissions.includes(code);
}

/** Access level the caller holds in a given space, or `undefined` if none. */
export function spaceAccess(
  my: MyPermissions | undefined,
  spaceId: string,
): SpaceAccess | undefined {
  return my?.spaces.find((s) => s.space_id === spaceId)?.access;
}

/**
 * Space-scoped check: the lowest privilege wins (§B.5).
 * - `viewer` → every write is cut, regardless of the workspace role.
 * - `manager` → workspace grants plus the fixed local PM grant set.
 * - otherwise → the plain workspace check.
 *
 * This is the check the server runs (`has_space_perm`) for every task,
 * comment and attachment write, so it — not `can()` — is what content
 * affordances must be drawn from.
 */
export function canInSpace(
  my: MyPermissions | undefined,
  spaceId: string,
  code: PermissionCode,
): boolean {
  if (!my) return false;
  const access = spaceAccess(my, spaceId);
  if (access === "viewer") {
    // Read-only membership: only the read codes survive.
    return SPACE_VIEWER_GRANTS.has(code) && can(my, code);
  }
  // NOTE: the server gates its read-only flag *before* this local grant, and
  // `MyPermissions` carries no `is_readonly` field, so a hypothetical
  // read-only space manager would be over-served here. Unreachable today: a
  // `manager` row only exists for the space creator, and a read-only account
  // cannot create a space.
  if (access === "manager" && SPACE_MANAGER_GRANTS.has(code)) return true;
  return can(my, code);
}

// ---------------------------------------------------------------------------
// Umumiy konvensiya — "javob hali noma'lum" holati
// ---------------------------------------------------------------------------

/** Ruxsat hali yuklanmagan boshqaruv uchun sabab. */
export const PERMISSION_LOADING_HINT = "Ruxsatlar tekshirilmoqda…";
/** Ruxsat yo'qligi aniq bo'lgan boshqaruv uchun sabab. */
export const PERMISSION_DENIED_HINT = COMMON.errPermissionDenied;

/**
 * Bitta kod bo'yicha uch holatli javob: **ha / yo'q / hali bilmayman**.
 *
 * Ikki holatli `boolean` ning kamchiligi shu: `my-permissions` yo'lda
 * bo'lganda u `false` bo'ladi va UI "ruxsat yo'q" deb chizadi, so'ng ruxsat
 * kelgach boshqaruv **birdan paydo bo'ladi**. Bu — 403 beradigan tugmaning
 * ko'zgudagi aksi: kechikib chiqqan tugma. `isLoading` shu farqni ochiq
 * qiladi, chaqiruvchi esa skeleton yoki `disabled` ko'rsatadi.
 */
export interface PermissionGate {
  /** Ruxsat aniq berilgan. Yuklanayotganda HAR DOIM `false`. */
  allowed: boolean;
  /** Javob hali noma'lum — hech narsani yoqmang, joyini band qilib turing. */
  isLoading: boolean;
  /** `title=` uchun o'zbekcha sabab; ruxsat bor bo'lsa `undefined`. */
  hint: string | undefined;
}

/**
 * Bo'lim doirasidagi bitta kod uchun `PermissionGate`.
 *
 * `contentPermissions()` dan ataylab ALOHIDA: u faqat vazifa / komment /
 * biriktirma kodlarini qamraydi va a'zolarni boshqarish uning ishi emas.
 * Umumiy bo'lgani — konvensiya, ya'ni shu `isLoading` + `hint` juftligi.
 *
 * @param isPending `useMyPermissions(...).isPending`. Xatoda `false` bo'ladi,
 *   ya'ni gate "yopiq" holatga tushadi (fail-closed), abadiy skeletonga emas.
 */
export function spacePermissionGate(
  my: MyPermissions | undefined,
  isPending: boolean,
  spaceId: string | null | undefined,
  code: PermissionCode,
): PermissionGate {
  const isLoading = isPending || !spaceId;
  const allowed = !isLoading && !!spaceId && canInSpace(my, spaceId, code);
  return {
    allowed,
    isLoading,
    hint: allowed
      ? undefined
      : isLoading
        ? PERMISSION_LOADING_HINT
        : PERMISSION_DENIED_HINT,
  };
}

// ---------------------------------------------------------------------------
// §18 Content facade — vazifa / komment / biriktirma affordance'lari
// ---------------------------------------------------------------------------

/** Predikatlarga kerak bo'lgan minimal vazifa shakli. */
type AssignedTask = { assignees: { id: string }[] };

/**
 * Bitta bo'lim ichidagi mazmun ruxsatlari — ro'yxat, doska, vazifa paneli,
 * kommentlar va biriktirmalar shu bitta obyektdan chiziladi.
 *
 * Har bir maydon `backend` dagi aniq bir tekshiruvga mos keladi, shuning
 * uchun "server ruxsat bermaydigan tugma" ham, "foydalanuvchi haqli bo'lgan
 * yo'q tugma" ham qolmaydi.
 */
export interface ContentPermissions {
  /** `my-permissions` (yoki bo'lim id'si) hali kelmadi — yoqmang, o'chiring. */
  isLoading: boolean;
  /** `title=` uchun o'zbekcha sabab; ruxsat bor bo'lsa `undefined`. */
  hint: (allowed: boolean) => string | undefined;

  // ---- vazifalar ----
  /** `task.create` — kompozitor va bo'sh holat CTA'si. */
  canCreateTask: boolean;
  /** `task.delete` — "o'ziniki" istisnosi YO'Q (server ham bermaydi). */
  canDeleteTask: boolean;
  /** Hech bo'lmasa bitta sudrash yo'li bormi — `DndContext` sensorlari uchun. */
  canDragSome: boolean;
  /** `task.update`, yoki o'ziga biriktirilganda `task.update_assigned`. */
  canEditTask: (task: AssignedTask) => boolean;
  /** `task.move`, yoki o'ziga biriktirilganda `task.update_assigned`. */
  canMoveTask: (task: AssignedTask) => boolean;
  /** Tahrir huquqi **va** alohida `task.assign` kodi (§10.2 AppSec). */
  canAssignTask: (task: AssignedTask) => boolean;
  /** `task.watch` — kuzatuv tugmasi. */
  canWatchTask: boolean;

  // ---- kommentlar ----
  /** `comment.create` — kompozitor va "javob yozish". */
  canCreateComment: boolean;
  /** Muallif invarianti + `comment.update_own` (`update_any` mavjud emas). */
  canEditComment: (authorId: string | null | undefined) => boolean;
  /** O'ziniki → `comment.delete_own`, boshqaniki → `comment.delete_any`. */
  canDeleteComment: (authorId: string | null | undefined) => boolean;

  // ---- biriktirmalar ----
  /** `attachment.read` — bo'lim umuman ko'rinadimi. */
  canReadAttachments: boolean;
  /** `attachment.create` — tashlash zonasi va "Fayl tanlash". */
  canUploadAttachment: boolean;
  /** O'ziniki → `attachment.delete_own`, boshqaniki → `attachment.delete_any`. */
  canDeleteAttachment: (uploaderId: string | null | undefined) => boolean;
}

/**
 * Sof funksiya — React'ga bog'liq emas, shuning uchun ham `useListPermissions`,
 * ham `useBoardPermissions` uni bir xil `useMemo` ichida chaqira oladi.
 *
 * `spaceId` yoki `meId` yetishmasa hamma narsa `false` bo'ladi va
 * `isLoading` yoqiladi: ruxsat aniqlanmaguncha yoniq tugma ko'rsatilmaydi.
 */
export function contentPermissions(
  my: MyPermissions | undefined,
  spaceId: string | undefined,
  meId: string | undefined,
): ContentPermissions {
  const scope = my && spaceId && meId ? { my, spaceId, meId } : null;
  const isLoading = scope === null;

  const allow = (code: PermissionCode): boolean =>
    scope !== null && canInSpace(scope.my, scope.spaceId, code);
  const isMine = (userId: string | null | undefined): boolean =>
    scope !== null && !!userId && userId === scope.meId;

  const updateAny = allow("task.update");
  const updateAssigned = allow("task.update_assigned");
  const moveAny = allow("task.move");
  const assign = allow("task.assign");

  const commentUpdateOwn = allow("comment.update_own");
  const commentDeleteOwn = allow("comment.delete_own");
  const commentDeleteAny = allow("comment.delete_any");

  const attachmentDeleteOwn = allow("attachment.delete_own");
  const attachmentDeleteAny = allow("attachment.delete_any");

  const assignedToMe = (task: AssignedTask) =>
    scope !== null && task.assignees.some((a) => a.id === scope.meId);
  const canEditTask = (task: AssignedTask) =>
    updateAny || (updateAssigned && assignedToMe(task));

  return {
    isLoading,
    hint: (allowed) =>
      allowed ? undefined : isLoading ? PERMISSION_LOADING_HINT : PERMISSION_DENIED_HINT,

    canCreateTask: allow("task.create"),
    canDeleteTask: allow("task.delete"),
    canDragSome: moveAny || updateAssigned,
    canEditTask,
    canMoveTask: (task) => moveAny || (updateAssigned && assignedToMe(task)),
    canAssignTask: (task) => assign && canEditTask(task),
    canWatchTask: allow("task.watch"),

    canCreateComment: allow("comment.create"),
    canEditComment: (authorId) => isMine(authorId) && commentUpdateOwn,
    canDeleteComment: (authorId) =>
      isMine(authorId) ? commentDeleteOwn : commentDeleteAny,

    canReadAttachments: allow("attachment.read"),
    canUploadAttachment: allow("attachment.create"),
    canDeleteAttachment: (uploaderId) =>
      isMine(uploaderId) ? attachmentDeleteOwn : attachmentDeleteAny,
  };
}
