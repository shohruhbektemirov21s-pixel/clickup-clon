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

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.core.enums import AssignableRole, ROLE_RANK, SpaceAccess, WorkspaceRole

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
_REQUEST_LOCAL: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "wsperm_request_local", default=None
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
    }
)

#: `access == manager` (PM) shu bo'lim ichida lokal oladigan kodlar (F-5).
#: `space.delete`, `member.*`, `workspace.*`, `tag.*` HECH QACHON kirmaydi.
SPACE_MANAGER_GRANTS = frozenset(
    {
        "space.read",
        "space.update",
        "space.manage_members",
        "space.manage_statuses",
        "folder.create",
        "folder.update",
        "folder.delete",
        "folder.delete_cascade",
        "list.create",
        "list.update",
        "list.delete",
        "list.move",
        "list.manage_statuses",
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
    }
)


# ---------------------------------------------------------------- membership


def get_membership(user, workspace_id):
    from apps.workspaces.models import WorkspaceMember

    return (
        WorkspaceMember.objects.select_related("workspace", "user")
        .filter(workspace_id=workspace_id, user=user)
        .first()
    )


def require_membership(user, workspace_id, min_role="guest"):
    """Return the caller's membership or raise 404 (outside) / 403 (role)."""
    membership = get_membership(user, workspace_id)
    if membership is None:
        raise NotFound()
    if ROLE_RANK[membership.role] < MIN_RANK[min_role]:
        raise PermissionDenied()
    return membership


def require_role(membership, min_role):
    """Legacy rol tekshiruvi — §B.7 ko'chirishi tugagach olib tashlanadi."""
    if ROLE_RANK[membership.role] < MIN_RANK[min_role]:
        raise PermissionDenied()
    return membership


# ------------------------------------------------------------ matrix / cache


def _cache_key(workspace) -> str:
    """AD-4: version kalit ichida → invalidatsiya bir zumda, cross-process."""
    return f"wsperm:{workspace.id}:{workspace.permissions_version}"


def _build_matrix(workspace) -> dict[str, frozenset[str]]:
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


def effective_permissions(workspace) -> dict[str, frozenset[str]]:
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

    cached = cache.get(key)
    if cached is None:
        cached = _build_matrix(workspace)
        cache.set(key, cached, PERMISSION_CACHE_TTL)
    else:
        cached = {r: frozenset(v) for r, v in cached.items()}

    local[key] = cached
    return cached


@transaction.atomic
def bump_permissions_version(workspace, *, actor=None):
    """Matritsa har o'zgarganda chaqiriladi — R3: yozishning YAGONA yo'li."""
    from apps.realtime import events
    from apps.workspaces.models import Workspace

    Workspace.objects.filter(pk=workspace.pk).update(
        permissions_version=F("permissions_version") + 1, updated_at=timezone.now()
    )
    workspace.refresh_from_db(fields=["permissions_version"])
    _REQUEST_LOCAL.set({})
    transaction.on_commit(lambda: events.emit_permissions_updated(workspace, actor=actor))
    return workspace.permissions_version


def clear_permission_cache():
    """Testlar / management buyruqlari uchun: request-local qavatni tozalaydi."""
    _REQUEST_LOCAL.set({})


# --------------------------------------------------------------- has / require


def has_perm(membership, code: str) -> bool:
    from apps.core.permissions import PERMISSION_BY_CODE

    if settings.DEBUG and code not in PERMISSION_BY_CODE:
        raise ImproperlyConfigured(f"Noma'lum ruxsat kodi: {code}")
    if membership.role == WorkspaceRole.OWNER:
        return True  # AD-3 — owner lock, DB'ga qaralmaydi
    cached = getattr(membership, "_perm_set", None)
    if cached is None:
        cached = effective_permissions(membership.workspace).get(membership.role, frozenset())
        membership._perm_set = cached
    return code in cached


def require_perm(membership, code: str):
    if not has_perm(membership, code):
        raise PermissionDenied()
    return membership


def require_membership_perm(user, workspace_id, code: str):
    """C.4: avval 404 (a'zo emas), keyin 403 (ruxsat yo'q)."""
    membership = require_membership(user, workspace_id)
    return require_perm(membership, code)


def my_permissions(membership) -> frozenset[str]:
    from apps.core.permissions import ALL_CODES

    if membership.role == WorkspaceRole.OWNER:
        return ALL_CODES
    return effective_permissions(membership.workspace).get(membership.role, frozenset())


# ------------------------------------------------------------- space scoping


def space_access_of(membership, space):
    """Bu bo'limdagi lokal daraja yoki None."""
    from apps.workspaces.models import SpaceMember

    cache_attr = f"_space_access_{space.pk}"
    if hasattr(membership, cache_attr):
        return getattr(membership, cache_attr)
    value = (
        SpaceMember.objects.filter(space_id=space.pk, user_id=membership.user_id)
        .values_list("access", flat=True)
        .first()
    )
    setattr(membership, cache_attr, value)
    return value


def has_space_perm(membership, space, code: str) -> bool:
    """Workspace ruxsati + bo'lim ichidagi lokal daraja (B.5).

    - `viewer`   → faqat `SPACE_VIEWER_GRANTS` (eng past huquq g'olib)
    - `contributor` → workspace roli bo'yicha odatiy `has_perm`
    - `manager`  → contributor + `SPACE_MANAGER_GRANTS` lokal yoqiladi
    """
    if membership.role == WorkspaceRole.OWNER:
        return True
    access = space_access_of(membership, space)
    if access == SpaceAccess.VIEWER:
        return code in SPACE_VIEWER_GRANTS and has_perm(membership, code)
    if access == SpaceAccess.MANAGER and code in SPACE_MANAGER_GRANTS:
        return True
    return has_perm(membership, code)


def require_space_perm(membership, space, code: str):
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


def space_is_visible(membership, space) -> bool:
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


def check_space_visible(membership, space):
    """Ko'rinmasa 404 — mavjudlik oshkor qilinmaydi."""
    if not space_is_visible(membership, space):
        raise NotFound()


def visible_spaces_q(membership):
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
