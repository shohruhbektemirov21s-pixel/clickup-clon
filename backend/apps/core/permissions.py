"""Ruxsat katalogi — docs/DESIGN_PERMISSIONS.md §A.

AD-1: katalog **kodda** yashaydi, grantlar esa DB'da (`workspaces.RolePermission`).
Yangi ruxsat qo'shish = shu fayldagi bitta qator; migratsiya talab qilinmaydi.

AD-3: `owner` hech qachon `defaults` ichida bo'lmaydi va hech qachon DB'da
saqlanmaydi — `has_perm()` owner uchun short-circuit qiladi.

AD-5: `DEFAULT_MATRIX` monoton: guest ⊆ member ⊆ admin ⊆ owner.

AD-9: defaultlar `docs/API_CONTRACT.md §1.7` ning bugungi xatti-harakatini
bit-ma-bit takrorlaydi — mavjud testlar regressiya detektori bo'lib qoladi.

Kod formati: ``<resource>.<action>``, ``[a-z_]+\\.[a-z_]+``, max 64 belgi.
Kodlar **hech qachon o'chirilmaydi**, faqat ``deprecated=True`` qilinadi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Katalog sxemasi o'zgarganda (yangi kod / guruh) oshiriladi; frontend
# `staleTime: Infinity` bilan keshlaydi va shu raqamga qarab yangilanadi.
CATALOG_VERSION = 1

CODE_RE = re.compile(r"^[a-z_]+\.[a-z_]+$")
MAX_CODE_LENGTH = 64

#: `RolePermission` jadvalida saqlanadigan rollar (owner YO'Q) — enums bilan
#: sinxron, lekin permissions.py Django modellariga bog'liq bo'lmasligi uchun
#: bu yerda literal.
ASSIGNABLE_ROLES = ("admin", "member", "guest")

ADMIN = "admin"
MEMBER = "member"
GUEST = "guest"

A = frozenset({ADMIN})
AM = frozenset({ADMIN, MEMBER})
AMG = frozenset({ADMIN, MEMBER, GUEST})
NONE: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PermissionDef:
    """Katalogdagi bitta ruxsat kodi."""

    code: str
    group: str
    label: str  # o'zbekcha UI yorlig'i
    description: str  # o'zbekcha tavsif
    defaults: frozenset[str]  # {"admin","member"} — owner HECH QACHON bu yerda emas
    owner_only: bool = False  # hech qachon grant qilinmaydi (400)
    sensitive: bool = False  # UI ogohlantirish
    deprecated: bool = False


#: Guruh kaliti → o'zbekcha yorliq. Tartib UI'dagi tartibni belgilaydi.
PERMISSION_GROUPS: dict[str, str] = {
    "workspace": "Ish maydoni",
    "member": "A'zolar",
    "space": "Bo'limlar",
    "folder": "Jildlar",
    "list": "Ro'yxatlar",
    "task": "Vazifalar",
    "comment": "Izohlar",
    "tag": "Teglar",
}


PERMISSIONS: tuple[PermissionDef, ...] = (
    # ------------------------------------------------------------- workspace
    PermissionDef(
        code="workspace.read",
        group="workspace",
        label="Ish maydonini o'qish",
        description="Ish maydoni va uning daraxtini (bo'lim/jild/ro'yxat) ko'rish.",
        defaults=AMG,
    ),
    PermissionDef(
        code="workspace.update",
        group="workspace",
        label="Ish maydonini tahrirlash",
        description="Ish maydoni nomi, tavsifi va rangini o'zgartirish.",
        defaults=NONE,
    ),
    PermissionDef(
        code="workspace.delete",
        group="workspace",
        label="Ish maydonini o'chirish",
        description="Ish maydonini butunlay o'chirish — qaytarib bo'lmaydi.",
        defaults=NONE,
        sensitive=True,
    ),
    PermissionDef(
        code="workspace.manage_permissions",
        group="workspace",
        label="Ruxsatlar matritsasini boshqarish",
        description="Rollar ruxsat matritsasini o'qish va o'zgartirish.",
        defaults=NONE,
        owner_only=True,
        sensitive=True,
    ),
    PermissionDef(
        code="workspace.transfer_ownership",
        group="workspace",
        label="Egalikni o'tkazish",
        description="Ish maydoni egaligini boshqa a'zoga berish.",
        defaults=NONE,
        owner_only=True,
        sensitive=True,
    ),
    # ---------------------------------------------------------------- member
    PermissionDef(
        code="member.read",
        group="member",
        label="A'zolar ro'yxatini ko'rish",
        description="Ish maydoni a'zolari ro'yxatini va ularning rollarini ko'rish.",
        defaults=AM,
    ),
    PermissionDef(
        code="member.invite",
        group="member",
        label="Taklif yuborish",
        description="Yangi foydalanuvchini ish maydoniga taklif qilish.",
        defaults=A,
    ),
    PermissionDef(
        code="member.remove",
        group="member",
        label="A'zoni chiqarish",
        description="A'zoni ish maydonidan chiqarish.",
        defaults=A,
        sensitive=True,
    ),
    PermissionDef(
        code="member.role_change",
        group="member",
        label="Rolni o'zgartirish",
        description="A'zoning ish maydonidagi rolini o'zgartirish.",
        defaults=A,
        sensitive=True,
    ),
    PermissionDef(
        code="invitation.read",
        group="member",
        label="Takliflarni ko'rish",
        description="Yuborilgan takliflar ro'yxatini ko'rish.",
        defaults=A,
    ),
    PermissionDef(
        code="invitation.manage",
        group="member",
        label="Takliflarni boshqarish",
        description="Taklifni bekor qilish yoki qayta yuborish.",
        defaults=A,
    ),
    # ----------------------------------------------------------------- space
    PermissionDef(
        code="space.read",
        group="space",
        label="Bo'limlarni ko'rish",
        description="Ochiq bo'limlarni va ularning mazmunini ko'rish.",
        defaults=AMG,
    ),
    PermissionDef(
        code="space.read_private",
        group="space",
        label="Yopiq bo'limlarni ko'rish",
        description="Barcha yopiq bo'limlarni bo'lim a'zosi bo'lmasdan ko'rish.",
        defaults=A,
        sensitive=True,
    ),
    PermissionDef(
        code="space.create",
        group="space",
        label="Bo'lim yaratish",
        description="Ish maydonida yangi bo'lim yaratish.",
        defaults=A,
    ),
    PermissionDef(
        code="space.update",
        group="space",
        label="Bo'limni tahrirlash",
        description="Bo'lim nomi, rangi, ikonkasi va arxiv holatini o'zgartirish.",
        defaults=A,
    ),
    PermissionDef(
        code="space.delete",
        group="space",
        label="Bo'limni o'chirish",
        description="Bo'limni butun mazmuni bilan o'chirish — qaytarib bo'lmaydi.",
        defaults=A,
        sensitive=True,
    ),
    PermissionDef(
        code="space.manage_members",
        group="space",
        label="Bo'lim a'zolarini boshqarish",
        description="Loyiha menejeri huquqi: bo'limga odam biriktirish va olib tashlash.",
        defaults=A,
    ),
    PermissionDef(
        code="space.manage_statuses",
        group="space",
        label="Bo'lim statuslarini boshqarish",
        description="Bo'limning status to'plamini almashtirish.",
        defaults=A,
    ),
    # ---------------------------------------------------------------- folder
    PermissionDef(
        code="folder.create",
        group="folder",
        label="Jild yaratish",
        description="Bo'lim ichida yangi jild yaratish.",
        defaults=AM,
    ),
    PermissionDef(
        code="folder.update",
        group="folder",
        label="Jildni tahrirlash",
        description="Jild nomi, rangi va arxiv holatini o'zgartirish.",
        defaults=AM,
    ),
    PermissionDef(
        code="folder.delete",
        group="folder",
        label="Jildni o'chirish (ro'yxatlarni saqlab)",
        description="Jildni o'chirish, ro'yxatlar bo'lim ildiziga ko'chiriladi "
        "(`?strategy=detach`).",
        defaults=AM,
    ),
    PermissionDef(
        code="folder.delete_cascade",
        group="folder",
        label="Jildni mazmuni bilan o'chirish",
        description="Jildni ichidagi barcha ro'yxat va vazifalar bilan o'chirish "
        "(`?strategy=cascade`).",
        defaults=A,
        sensitive=True,
    ),
    # ------------------------------------------------------------------ list
    PermissionDef(
        code="list.create",
        group="list",
        label="Ro'yxat yaratish",
        description="Bo'lim yoki jild ichida yangi ro'yxat yaratish.",
        defaults=AM,
    ),
    PermissionDef(
        code="list.update",
        group="list",
        label="Ro'yxatni tahrirlash",
        description="Ro'yxat nomi, tavsifi, rangi va arxiv holatini o'zgartirish.",
        defaults=AM,
    ),
    PermissionDef(
        code="list.delete",
        group="list",
        label="Ro'yxatni o'chirish",
        description="Ro'yxatni vazifalari bilan o'chirish.",
        defaults=AM,
        sensitive=True,
    ),
    PermissionDef(
        code="list.move",
        group="list",
        label="Ro'yxatni ko'chirish",
        description="Ro'yxatni jildlar orasida ko'chirish va tartibini o'zgartirish.",
        defaults=AM,
    ),
    PermissionDef(
        code="list.manage_statuses",
        group="list",
        label="Ro'yxat statuslarini boshqarish",
        description="Ro'yxat uchun alohida status to'plami o'rnatish yoki olib tashlash.",
        defaults=A,
    ),
    # ------------------------------------------------------------------ task
    PermissionDef(
        code="task.read",
        group="task",
        label="Vazifalarni o'qish",
        description="Ko'rinadigan bo'limlardagi vazifalarni o'qish.",
        defaults=AMG,
    ),
    PermissionDef(
        code="task.create",
        group="task",
        label="Vazifa yaratish",
        description="Ro'yxatda yangi vazifa yaratish.",
        defaults=AM,
    ),
    PermissionDef(
        code="task.update",
        group="task",
        label="Har qanday vazifani tahrirlash",
        description="Ro'yxatdagi istalgan vazifani tahrirlash.",
        defaults=AM,
    ),
    PermissionDef(
        code="task.update_assigned",
        group="task",
        label="O'ziga biriktirilgan vazifani tahrirlash",
        description="Faqat o'ziga biriktirilgan vazifalarni tahrirlash va ko'chirish.",
        defaults=AMG,
    ),
    PermissionDef(
        code="task.delete",
        group="task",
        label="Vazifani o'chirish",
        description="Vazifani soft-delete qiladi; 30 kun ichida tiklash mumkin.",
        defaults=AM,
    ),
    PermissionDef(
        code="task.move",
        group="task",
        label="Vazifani ko'chirish",
        description="Har qanday vazifani ro'yxat/status orasida ko'chirish.",
        defaults=AM,
    ),
    PermissionDef(
        code="task.assign",
        group="task",
        label="Vazifani biriktirish",
        description="Vazifaning `assignee_ids` ro'yxatini o'zgartirish.",
        defaults=AM,
    ),
    PermissionDef(
        code="task.watch",
        group="task",
        label="Vazifani kuzatish",
        description="Vazifaga kuzatuvchi bo'lish yoki kuzatishni to'xtatish.",
        defaults=AMG,
    ),
    PermissionDef(
        code="task.restore",
        group="task",
        label="Vazifani tiklash",
        description="O'chirilgan vazifani tiklash.",
        defaults=A,
    ),
    PermissionDef(
        code="task.view_deleted",
        group="task",
        label="O'chirilgan vazifalarni ko'rish",
        description="`?include_deleted=true` bilan o'chirilgan vazifalarni ko'rish.",
        defaults=A,
    ),
    # --------------------------------------------------------------- comment
    PermissionDef(
        code="comment.create",
        group="comment",
        label="Izoh yozish",
        description="Vazifaga izoh yoki javob yozish.",
        defaults=AMG,
    ),
    PermissionDef(
        code="comment.update_own",
        group="comment",
        label="O'z izohini tahrirlash",
        description="Faqat o'zi yozgan izohni tahrirlash. Boshqaning izohini "
        "hech kim, hatto owner ham tahrirlay olmaydi.",
        defaults=AMG,
    ),
    PermissionDef(
        code="comment.delete_own",
        group="comment",
        label="O'z izohini o'chirish",
        description="Faqat o'zi yozgan izohni o'chirish.",
        defaults=AMG,
    ),
    PermissionDef(
        code="comment.delete_any",
        group="comment",
        label="Har qanday izohni o'chirish",
        description="Boshqa foydalanuvchining izohini o'chirish (moderatsiya).",
        defaults=A,
        sensitive=True,
    ),
    # ------------------------------------------------------------------- tag
    PermissionDef(
        code="tag.create",
        group="tag",
        label="Teg yaratish",
        description="Ish maydonida yangi teg yaratish.",
        defaults=AM,
    ),
    PermissionDef(
        code="tag.update",
        group="tag",
        label="Tegni tahrirlash",
        description="Teg nomi yoki rangini o'zgartirish.",
        defaults=AM,
    ),
    PermissionDef(
        code="tag.delete",
        group="tag",
        label="Tegni o'chirish",
        description="Tegni o'chirish; barcha vazifalardan olib tashlanadi.",
        defaults=AM,
    ),
)


#: Kod → ta'rif. Noma'lum kod bilan chaqiruv `has_perm()` da (DEBUG'da) yiqiladi.
PERMISSION_BY_CODE: dict[str, PermissionDef] = {p.code: p for p in PERMISSIONS}

#: Rol → shu rol **default**da egalik qiladigan kodlar. `owner` bu yerda YO'Q
#: (AD-3): owner har doim hamma narsaga ega va DB'da saqlanmaydi.
DEFAULT_MATRIX: dict[str, frozenset[str]] = {
    role: frozenset(p.code for p in PERMISSIONS if not p.deprecated and role in p.defaults)
    for role in ASSIGNABLE_ROLES
}

#: Katalogdagi barcha faol kodlar (owner shu to'plamga ega deb hisoblanadi).
ALL_CODES: frozenset[str] = frozenset(p.code for p in PERMISSIONS if not p.deprecated)

#: Grant qilib bo'lmaydigan kodlar — `PUT role-permissions/` bularni 400 qiladi.
OWNER_ONLY_CODES: frozenset[str] = frozenset(p.code for p in PERMISSIONS if p.owner_only)


def grouped_catalog() -> list[dict]:
    """`GET permissions/` uchun guruhlangan katalog (D.1)."""
    groups = []
    for key, label in PERMISSION_GROUPS.items():
        entries = [p for p in PERMISSIONS if p.group == key and not p.deprecated]
        if not entries:
            continue
        groups.append(
            {
                "key": key,
                "label": label,
                "permissions": [
                    {
                        "code": p.code,
                        "label": p.label,
                        "description": p.description,
                        # owner HECH QACHON default_roles ichida emas
                        "default_roles": [r for r in ASSIGNABLE_ROLES if r in p.defaults],
                        "owner_only": p.owner_only,
                        "sensitive": p.sensitive,
                    }
                    for p in entries
                ],
            }
        )
    return groups
