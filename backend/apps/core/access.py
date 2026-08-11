"""Workspace-scoped access helpers.

Contract rules (docs/API_CONTRACT.md section 1.7):
- out-of-workspace resources are NEVER disclosed -> 404, never 403;
- in-workspace but role-forbidden -> 403;
- guests cannot see private spaces at all -> 404.

docs/DESIGN_PERMISSIONS.md §C bu modulga granular ruxsat qatlamini qo'shadi:
`has_perm` / `require_perm` / `require_membership_perm` / `has_space_perm` /
`require_space_perm` / `effective_permissions` / `my_permissions`.

**404 vs 403 tartibi (C.4, qat'iy):**

1. Resurs mavjudmi?      yo'q → 404
2. require_membership    a'zo emas → 404
3. check_space_visible   ko'rinmaydi → 404   ← SpaceMember shu yerda
4. require_perm          ruxsat yo'q → 403
5. serializer.is_valid() → 400

Eski `require_role(...)` / `min_role=` chaqiruvlari **o'zgarishsiz** qoladi
(rollout §G.2 Faza 3). Bu modul faqat yangi qatlamni qo'shadi.
"""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.core.enums import AssignableRole, ROLE_RANK, SpaceAccess, WorkspaceRole

if TYPE_CHECKING:
    # Faqat tip uchun: ish vaqtida import qilinsa `apps.workspaces` <-> `apps.core`
    # halqasi paydo bo'lardi (shuning uchun funksiyalar ichida lokal import).
    from apps.workspaces.models import Space, Workspace, WorkspaceMember

MIN_RANK = {
    "owner": ROLE_RANK[WorkspaceRole.OWNER],
    "admin": ROLE_RANK[WorkspaceRole.ADMIN],
    "member": ROLE_RANK[WorkspaceRole.MEMBER],
    "guest": ROLE_RANK[WorkspaceRole.GUEST],
}

#: Django cache qavatining umri (C.3). Version kalitda bo'lgani uchun TTL
#: faqat "unutish" mexanizmi — invalidatsiya version bump orqali bo'ladi.
PERMISSION_CACHE_TTL = 300

#: Bitta HTTP request davomida ko'p membership obyekti uchun umumiy qavat.
#: Kalit `_cache_key(workspace)` bo'lgani uchun stale bo'lishi mumkin emas.
_REQUEST_LOCAL: contextvars.ContextVar[dict[str, dict[str, frozenset[str]]] | None] = (
    contextvars.ContextVar(
        "wsperm_request_local", default=None
    )
)

#: `access == viewer` bo'lgan bo'lim a'zosiga qoladigan **yagona** kodlar.
#: "Eng past huquq g'olib" (B.5): viewer uchun har qanday yozish 403.
SPACE_VIEWER_GRANTS = frozenset(
    {
        "workspace.read",
        "member.read",
        "space.read",
        "space.read_private",
        "task.read",
        "task.watch",
        "task.view_deleted",
        # O'qish kodi — viewer vazifani ko'ra olsa, uning fayllarini ham
        # ko'ra olishi kerak (yozish kodlari ataylab kirmaydi).
        "attachment.read",
    }
)

#: `access == manager` (PM) shu bo'lim ichida lokal oladigan kodlar (F-5).
#: `space.manage_statuses` / `list.manage_statuses` bu yerdan OLIB TASHLANDI:
#: ular katalogda `deprecated=True` (v6) va endi hech qanday endpointni
#: qo'riqlamaydi.
#: `space.delete`, `space.change_visibility`, `member.*`, `workspace.*`,
#: `tag.*` HECH QACHON kirmaydi.
SPACE_MANAGER_GRANTS = frozenset(
    {
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
        # `attachment.delete_any` ataylab YO'Q — `comment.delete_any` kabi
        # moderatsiya huquqi bo'lim menejeriga lokal berilmaydi.
        #
        # `space.change_visibility` ham ataylab YO'Q (`space.delete` bilan bir
        # xil mantiq): PM bo'lim ICHIDA to'liq hokim, lekin bo'limning ish
        # maydoniga nisbatan CHEGARASINI o'zgartira olmaydi. Aks holda u
        # `is_private=false` bilan yopiq loyihaning butun mazmunini bir
        # so'rovda barcha a'zolarga oshkor qilardi (yoki teskarisi — ochiq
        # bo'limni yopib, unga tayangan guest/kontraktorlarni chiqarib
        # yuborardi).
    }
)


# ---------------------------------------------------------------- membership


def get_membership(user: Any, workspace_id: Any) -> "WorkspaceMember | None":
    from apps.workspaces.models import WorkspaceMember

    return (
        WorkspaceMember.objects.select_related("workspace", "user")
        .filter(workspace_id=workspace_id, user=user)
        .first()
    )


def remember_membership(user: Any, membership: "WorkspaceMember") -> "WorkspaceMember":
    """Chaqiruvchining shu request'dagi a'zoligini `request.user` da saqlaydi.

    Nega atribut, nega serializer `context` emas: `UserSummarySerializer`
    o'nlab joyda (assignee, watcher, izoh muallifi, `created_by`, faoliyat
    aktori, biriktirma yuklovchisi) ichma-ich ishlatiladi. Har bir view'ga
    `context={"membership": ...}` qo'shish — **bitta joyni unutsang email
    sizib chiqadigan** dizayn. `request.user` obyekti har HTTP request'da
    autentifikatsiya qatlamida qaytadan yaratiladi, shuning uchun bu atribut
    request'lar orasida oqib ketmaydi (contextvar/thread-local dan farqli).

    `membership.user` — DB'dan kelgan **boshqa** instans, shuning uchun bayroq
    ataylab `require_membership()` ga uzatilgan `user` obyektiga qo'yiladi.
    """
    try:
        # So'rov davomidagi memo — modelda maydon emas, shuning uchun
        # statik tekshiruvchi uni ko'rmaydi (docstring'da sababi bor).
        user._current_membership = membership
    except AttributeError:  # AnonymousUser va sinovdagi soxta obyektlar
        pass
    return membership


def current_membership_of(user: Any) -> "WorkspaceMember | None":
    """`remember_membership()` saqlagan a'zolik yoki None."""
    return getattr(user, "_current_membership", None)


def require_membership(
    user: Any, workspace_id: Any, min_role: str = "guest"
) -> "WorkspaceMember":
    """Return the caller's membership or raise 404 (outside) / 403 (role)."""
    membership = get_membership(user, workspace_id)
    if membership is None:
        raise NotFound()
    remember_membership(user, membership)
    if ROLE_RANK[membership.role] < MIN_RANK[min_role]:
        raise PermissionDenied()
    return membership


def require_role(membership: "WorkspaceMember", min_role: str) -> "WorkspaceMember":
    """Legacy rol tekshiruvi — §B.7 shim.

    View qatlami to'liq `require_perm` ga ko'chirildi; bu funksiya faqat
    tashqi/eski chaqiruvlar uchun qoldi va yangi kodda ishlatilmasligi kerak
    (§C.5 drift-guard testi `apps/*/views.py` da uni taqiqlaydi).
    """
    import warnings

    warnings.warn(
        "require_role() eskirgan — apps.core.access.require_perm() dan foydalaning.",
        DeprecationWarning,
        stacklevel=2,
    )
    if ROLE_RANK[membership.role] < MIN_RANK[min_role]:
        raise PermissionDenied()
    return membership


# ------------------------------------------------------------ matrix / cache


def _cache_key(workspace: "Workspace") -> str:
    """AD-4: version kalit ichida → invalidatsiya bir zumda, cross-process."""
    return f"wsperm:{workspace.id}:{workspace.permissions_version}"


def _build_matrix(workspace: "Workspace") -> dict[str, frozenset[str]]:
    from apps.core.permissions import DEFAULT_MATRIX, PERMISSION_BY_CODE
    from apps.workspaces.models import RolePermission

    matrix = {r: set(DEFAULT_MATRIX[r]) for r in AssignableRole.values}
    rows = RolePermission.objects.filter(workspace_id=workspace.id).values_list(
        "role", "permission", "allowed"
    )
    for role, code, allowed in rows:
        if code not in PERMISSION_BY_CODE or role not in matrix:
            continue
        (matrix[role].add if allowed else matrix[role].discard)(code)
    return {r: frozenset(v) for r, v in matrix.items()}


def effective_permissions(workspace: "Workspace") -> dict[str, frozenset[str]]:
    """Rol → yakuniy ruxsat to'plami (owner bu yerda YO'Q, AD-3).

    Uch qavatli kesh: request-local dict → Django cache → DB.
    Cache hit → +0 query.
    """
    key = _cache_key(workspace)

    local = _REQUEST_LOCAL.get()
    if local is None:
        local = {}
        _REQUEST_LOCAL.set(local)
    if key in local:
        return local[key]

    cached: dict[str, frozenset[str]] | None = cache.get(key)
    if cached is None:
        cached = _build_matrix(workspace)
        cache.set(key, cached, PERMISSION_CACHE_TTL)
    else:
        cached = {r: frozenset(v) for r, v in cached.items()}

    local[key] = cached
    return cached


@transaction.atomic
def bump_permissions_version(workspace: "Workspace", *, actor: Any = None) -> int:
    """Matritsa har o'zgarganda chaqiriladi — R3: yozishning YAGONA yo'li."""
    from apps.realtime import events
    from apps.workspaces.models import Workspace

    Workspace.objects.filter(pk=workspace.pk).update(
        permissions_version=F("permissions_version") + 1, updated_at=timezone.now()
    )
    workspace.refresh_from_db(fields=["permissions_version"])
    _REQUEST_LOCAL.set({})
    transaction.on_commit(lambda: events.emit_permissions_updated(workspace, actor=actor))
    version: int = workspace.permissions_version
    return version


def clear_permission_cache() -> None:
    """Testlar / management buyruqlari uchun: request-local qavatni tozalaydi."""
    _REQUEST_LOCAL.set({})


# --------------------------------------------------------------- has / require


#: Faqat o'qish hisobiga (`User.is_readonly`, ya'ni demo) ruxsat etilgan kodlar.
#: Bu ro'yxatga kirmagan HAR QANDAY kod rad etiladi — yangi yozish kodi
#: qo'shilganda u avtomatik taqiqlanadi, ya'ni ro'yxat "fail-closed".
READONLY_ALLOWED_CODES = frozenset(
    {
        "workspace.read",
        "member.read",
        "invitation.read",
        "space.read",
        "space.read_private",
        "task.read",
        "task.view_deleted",
        "attachment.read",
    }
)


def has_perm(membership: "WorkspaceMember", code: str) -> bool:
    from apps.core.permissions import PERMISSION_BY_CODE

    if settings.DEBUG and code not in PERMISSION_BY_CODE:
        raise ImproperlyConfigured(f"Noma'lum ruxsat kodi: {code}")
    # Demo hisobi rolidan qat'i nazar hech narsani o'zgartira olmaydi. Bayroq
    # faqat CHEKLAYDI: rol bermagan o'qish huquqini qo'shib qo'ymaslik uchun
    # tekshiruv davom etadi va natija kesishma bo'ladi.
    if getattr(membership.user, "is_readonly", False) and code not in READONLY_ALLOWED_CODES:
        return False
    if membership.role == WorkspaceRole.OWNER:
        return True  # AD-3 — owner lock, DB'ga qaralmaydi
    cached = getattr(membership, "_perm_set", None)
    if cached is None:
        cached = effective_permissions(membership.workspace).get(membership.role, frozenset())
        # Instans darajasidagi memo (modelda maydon emas) — bitta so'rovda
        # o'nlab `has_perm` chaqiruvi bitta matritsani qayta hisoblamasin.
        membership._perm_set = cached  # type: ignore[attr-defined]
    return code in cached


def require_perm(membership: "WorkspaceMember", code: str) -> "WorkspaceMember":
    if not has_perm(membership, code):
        raise PermissionDenied()
    return membership


def require_membership_perm(user: Any, workspace_id: Any, code: str) -> "WorkspaceMember":
    """C.4: avval 404 (a'zo emas), keyin 403 (ruxsat yo'q)."""
    membership = require_membership(user, workspace_id)
    return require_perm(membership, code)


def my_permissions(membership: "WorkspaceMember") -> frozenset[str]:
    from apps.core.permissions import ALL_CODES

    granted = (
        ALL_CODES
        if membership.role == WorkspaceRole.OWNER
        else effective_permissions(membership.workspace).get(membership.role, frozenset())
    )
    # `has_perm` bilan bir xil kesishma: aks holda UI yozish tugmalarini
    # ko'rsatib, bosilganda 403 olardi.
    if getattr(membership.user, "is_readonly", False):
        return granted & READONLY_ALLOWED_CODES
    return granted


# ------------------------------------------------------------- space scoping


def space_access_of(membership: "WorkspaceMember", space: "Space") -> str | None:
    """Bu bo'limdagi lokal daraja yoki None."""
    from apps.workspaces.models import SpaceMember

    cache_attr = f"_space_access_{space.pk}"
    if hasattr(membership, cache_attr):
        # Nomi dinamik bo'lgani uchun `getattr` `Any` beradi — turini ochiq aytamiz.
        memoized: str | None = getattr(membership, cache_attr)
        return memoized
    value: str | None = (
        SpaceMember.objects.filter(space_id=space.pk, user_id=membership.user_id)
        .values_list("access", flat=True)
        .first()
    )
    setattr(membership, cache_attr, value)
    return value


def has_space_perm(membership: "WorkspaceMember", space: "Space", code: str) -> bool:
    """Workspace ruxsati + bo'lim ichidagi lokal daraja (B.5).

    - `viewer`   → faqat `SPACE_VIEWER_GRANTS` (eng past huquq g'olib)
    - `contributor` → workspace roli bo'yicha odatiy `has_perm`
    - `manager`  → contributor + `SPACE_MANAGER_GRANTS` lokal yoqiladi
    """
    # Faqat o'qish bayrog'i owner va manager short-circuit'laridan ham ustun —
    # aks holda demo hisob bo'lim ichida yozib yuborardi.
    if getattr(membership.user, "is_readonly", False) and code not in READONLY_ALLOWED_CODES:
        return False
    if membership.role == WorkspaceRole.OWNER:
        return True
    access = space_access_of(membership, space)
    if access == SpaceAccess.VIEWER:
        return code in SPACE_VIEWER_GRANTS and has_perm(membership, code)
    if access == SpaceAccess.MANAGER and code in SPACE_MANAGER_GRANTS:
        return True
    return has_perm(membership, code)


def require_space_perm(
    membership: "WorkspaceMember", space: "Space", code: str
) -> "WorkspaceMember":
    if not has_space_perm(membership, space, code):
        raise PermissionDenied()
    return membership


# ------------------------------------------------------------- visibility


def _acl_enabled() -> bool:
    """§G.2 Faza 4 bayrog'i.

    `SpaceMember` ACL visibility qoidasi (R20) mavjud xatti-harakatni
    o'zgartiradi, shuning uchun u alohida fazada `SPACE_ACL_ENABLED=True`
    bilan yoqiladi. Bayroq o'chiq bo'lsa legacy qoida (guest × private) amal
    qiladi va `SpaceMember` qatorlari faqat qo'shimcha ruxsat beradi.
    """
    return bool(getattr(settings, "SPACE_ACL_ENABLED", False))


def space_is_visible(membership: "WorkspaceMember", space: "Space") -> bool:
    """B.5 visibility predikati (bayroq yoqilganda)."""
    if membership.role == WorkspaceRole.OWNER:
        return True
    if _acl_enabled():
        if has_perm(membership, "space.read_private"):
            return True
        if not space.is_private and has_perm(membership, "space.read"):
            return True
        return space_access_of(membership, space) is not None
    # legacy (API_CONTRACT §1.7): guest yopiq bo'limni ko'rmaydi
    if membership.role == WorkspaceRole.GUEST and space.is_private:
        return space_access_of(membership, space) is not None
    return True


def check_space_visible(membership: "WorkspaceMember", space: "Space") -> None:
    """Ko'rinmasa 404 — mavjudlik oshkor qilinmaydi."""
    if not space_is_visible(membership, space):
        raise NotFound()


def visible_spaces_q(membership: "WorkspaceMember") -> Q:
    """C.5 — bo'lim ro'yxatlari uchun yagona filtr."""
    if membership.role == WorkspaceRole.OWNER:
        return Q()
    if _acl_enabled():
        if has_perm(membership, "space.read_private"):
            return Q()
        explicit = Q(space_members__user_id=membership.user_id)
        if has_perm(membership, "space.read"):
            return Q(is_private=False) | explicit
        return explicit
    if membership.role == WorkspaceRole.GUEST:
        return Q(is_private=False) | Q(space_members__user_id=membership.user_id)
    return Q()
