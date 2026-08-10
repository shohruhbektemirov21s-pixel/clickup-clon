"""Katalog invariantlari — docs/DESIGN_PERMISSIONS.md §A, §I (merge gate)."""

import re
from pathlib import Path

import pytest

from apps.core.access import has_perm, my_permissions
from apps.core.enums import AssignableRole
from apps.core.permissions import (
    ALL_CODES,
    ASSIGNABLE_ROLES,
    CATALOG_VERSION,
    CODE_RE,
    DEFAULT_MATRIX,
    MAX_CODE_LENGTH,
    OWNER_ONLY_CODES,
    PERMISSION_BY_CODE,
    PERMISSION_GROUPS,
    PERMISSIONS,
    grouped_catalog,
)

# §A — "Jami: 49 kod, 9 guruh."
# v2: `attachment` guruhi + 4 kod → 48.
# v5: `space.change_visibility` (AppSec) → 49.
EXPECTED_CODE_COUNT = 49
EXPECTED_GROUP_COUNT = 9

#: AD-9 — kutilgan defaultlar (§A jadvali + `API_CONTRACT.md` §1.7).
#:
#: **2026-08 siyosati.** Bu jadval endi "eski `min_role=` xatti-harakati" ni
#: emas, **yangi siyosatni** kodifikatsiya qiladi: `member` — "ko'radi va
#: o'ziga biriktirilganini bajaradi". Struktura (bo'lim/jild/ro'yxat), begona
#: vazifani tahrirlash/o'chirish/ko'chirish va teg tahriri admin+ ga o'tdi.
POLICY_EXPECTATIONS = {
    # (kod → kutilgan default rollar)
    "owner-only (defaults bo'sh)": {
        "workspace.update": set(),
        "workspace.delete": set(),
    },
    "admin+ — boshqaruv va struktura": {
        "member.invite": {"admin"},
        "member.remove": {"admin"},
        "member.role_change": {"admin"},
        "invitation.read": {"admin"},
        "invitation.manage": {"admin"},
        "space.read_private": {"admin"},
        "space.create": {"admin"},
        "space.update": {"admin"},
        # v5 — `space.update` dan ajratilgan: PM (`SPACE_MANAGER_GRANTS`)
        # `space.update` ni oladi, ko'rinuvchanlikni esa OLMAYDI.
        "space.change_visibility": {"admin"},
        "space.delete": {"admin"},
        "space.manage_members": {"admin"},
        "space.manage_statuses": {"admin"},
        # ↓ 2026-08 da member'dan olib tashlandi
        "folder.create": {"admin"},
        "folder.update": {"admin"},
        "folder.delete": {"admin"},
        "folder.delete_cascade": {"admin"},
        "list.create": {"admin"},
        "list.update": {"admin"},
        "list.delete": {"admin"},
        "list.move": {"admin"},
        "list.manage_statuses": {"admin"},
        "task.update": {"admin"},
        "task.delete": {"admin"},
        "task.move": {"admin"},
        "task.assign": {"admin"},
        "task.restore": {"admin"},
        "task.view_deleted": {"admin"},
        "comment.delete_any": {"admin"},
        "attachment.delete_any": {"admin"},
        "tag.update": {"admin"},
        "tag.delete": {"admin"},
    },
    "member+ — o'z ishini bajarish": {
        "task.create": {"admin", "member"},
        "attachment.create": {"admin", "member"},
        "attachment.delete_own": {"admin", "member"},
        "tag.create": {"admin", "member"},
    },
    "guest+ — ko'rish va o'ziga biriktirilgani": {
        "workspace.read": {"admin", "member", "guest"},
        # 2026-08 (v4): jamoa ro'yxati mehmonga ham ochiq. Emailni
        # `UserSummarySerializer` maskalaydi (AppSec O-1).
        "member.read": {"admin", "member", "guest"},
        "space.read": {"admin", "member", "guest"},
        "task.read": {"admin", "member", "guest"},
        "task.update_assigned": {"admin", "member", "guest"},
        "task.watch": {"admin", "member", "guest"},
        "comment.create": {"admin", "member", "guest"},
        "comment.update_own": {"admin", "member", "guest"},
        "comment.delete_own": {"admin", "member", "guest"},
        "attachment.read": {"admin", "member", "guest"},
    },
}

#: `member` ning to'liq va **yakuniy** default to'plami (14 kod). Ro'yxatga
#: yangi kod qo'shilsa bu test ataylab yiqiladi — siyosat o'zgarishi ko'rinsin.
MEMBER_DEFAULTS = {
    "workspace.read",
    "member.read",
    "space.read",
    "task.read",
    "task.create",
    "task.update_assigned",
    "task.watch",
    "comment.create",
    "comment.update_own",
    "comment.delete_own",
    "attachment.read",
    "attachment.create",
    "attachment.delete_own",
    "tag.create",
}

#: `member` dan 2026-08 da OLIB TASHLANGAN kodlar.
MEMBER_REVOKED = {
    "task.update",
    "task.delete",
    "task.move",
    "task.assign",
    "folder.create",
    "folder.update",
    "folder.delete",
    "folder.delete_cascade",
    "list.create",
    "list.update",
    "list.delete",
    "list.move",
    "tag.update",
    "tag.delete",
    "space.create",
    "space.update",
    "space.delete",
}


def test_catalog_size_and_groups():
    assert len(PERMISSIONS) == EXPECTED_CODE_COUNT
    assert len(PERMISSION_BY_CODE) == EXPECTED_CODE_COUNT  # kodlar takrorlanmaydi
    assert len(PERMISSION_GROUPS) == EXPECTED_GROUP_COUNT
    assert {p.group for p in PERMISSIONS} == set(PERMISSION_GROUPS)


def test_permission_code_format():
    for permission in PERMISSIONS:
        assert CODE_RE.match(permission.code), permission.code
        assert len(permission.code) <= MAX_CODE_LENGTH
        assert re.match(r"^[a-z_]+$", permission.group)


def test_labels_and_descriptions_are_present():
    for permission in PERMISSIONS:
        assert permission.label.strip()
        assert permission.description.strip()


def test_default_matrix_is_monotonic():
    """AD-5: guest ⊆ member ⊆ admin (owner har doim to'liq to'plam)."""
    guest, member, admin = (
        DEFAULT_MATRIX["guest"],
        DEFAULT_MATRIX["member"],
        DEFAULT_MATRIX["admin"],
    )
    assert guest <= member, sorted(guest - member)
    assert member <= admin, sorted(member - admin)
    assert admin <= ALL_CODES


def test_owner_is_never_a_default_role():
    """AD-3: owner hech qachon `defaults` ichida bo'lmaydi."""
    for permission in PERMISSIONS:
        assert "owner" not in permission.defaults, permission.code
    assert "owner" not in DEFAULT_MATRIX
    assert set(DEFAULT_MATRIX) == set(ASSIGNABLE_ROLES) == set(AssignableRole.values)


def test_owner_only_codes_have_no_defaults():
    assert OWNER_ONLY_CODES == {
        "workspace.manage_permissions",
        "workspace.transfer_ownership",
    }
    for code in OWNER_ONLY_CODES:
        assert PERMISSION_BY_CODE[code].defaults == frozenset()


@pytest.mark.parametrize("group_name", sorted(POLICY_EXPECTATIONS))
def test_default_matrix_matches_the_documented_policy(group_name):
    """AD-9 — defaultlar §A jadvali / §1.7 bilan bit-ma-bit mos."""
    for code, expected in POLICY_EXPECTATIONS[group_name].items():
        assert set(PERMISSION_BY_CODE[code].defaults) == expected, code


def test_policy_expectations_cover_every_code():
    covered = {
        code for table in POLICY_EXPECTATIONS.values() for code in table
    } | OWNER_ONLY_CODES
    assert covered == ALL_CODES, sorted(ALL_CODES - covered)


def test_member_defaults_are_exactly_the_policy_set():
    """2026-08: member = ko'rish + o'ziga biriktirilgani + fayl/izoh."""
    assert DEFAULT_MATRIX["member"] == MEMBER_DEFAULTS
    assert len(DEFAULT_MATRIX["member"]) == 14


def test_revoked_codes_left_member_but_stayed_with_admin():
    for code in sorted(MEMBER_REVOKED):
        assert code not in DEFAULT_MATRIX["member"], code
        assert code in DEFAULT_MATRIX["admin"], code


def test_admin_and_guest_defaults_are_unchanged():
    """Talab: admin va guest ustunlariga tegilmadi."""
    assert len(DEFAULT_MATRIX["admin"]) == len(ALL_CODES) - 4  # 4 kod owner-only/owner
    assert DEFAULT_MATRIX["guest"] == {
        "workspace.read",
        "member.read",
        "space.read",
        "task.read",
        "task.update_assigned",
        "task.watch",
        "comment.create",
        "comment.update_own",
        "comment.delete_own",
        "attachment.read",
    }


def test_grouped_catalog_shape():
    """D.1 — `default_roles` owner ni o'z ichiga olmaydi."""
    groups = grouped_catalog()
    assert [g["key"] for g in groups] == list(PERMISSION_GROUPS)
    seen = set()
    for group in groups:
        assert group["label"] == PERMISSION_GROUPS[group["key"]]
        for entry in group["permissions"]:
            assert set(entry) == {
                "code",
                "label",
                "description",
                "default_roles",
                "owner_only",
                "sensitive",
            }
            assert "owner" not in entry["default_roles"]
            assert entry["default_roles"] == [
                r for r in ASSIGNABLE_ROLES if r in PERMISSION_BY_CODE[entry["code"]].defaults
            ]
            seen.add(entry["code"])
    assert seen == ALL_CODES
    assert CATALOG_VERSION >= 1


def test_owner_always_has_every_permission(env):
    """AD-3 merge gate: owner short-circuit — DB'da qator bo'lmasa ham."""
    from apps.workspaces.models import RolePermission, WorkspaceMember

    owner = WorkspaceMember.objects.get(workspace=env.workspace, user=env.owner)
    # Har qanday grantni o'chirib tashlaymiz — owner baribir hamma narsaga ega.
    RolePermission.objects.filter(workspace=env.workspace).update(allowed=False)
    for code in sorted(ALL_CODES):
        assert has_perm(owner, code) is True, code
    assert my_permissions(owner) == ALL_CODES


def test_owner_rows_are_never_stored(env):
    """AD-3: `role='owner'` DB constraint bilan taqiqlangan."""
    from django.db import IntegrityError, transaction

    from apps.workspaces.models import RolePermission

    assert not RolePermission.objects.filter(role="owner").exists()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RolePermission.objects.create(
                workspace=env.workspace, role="owner", permission="task.read", allowed=True
            )


# ---------------------------------------------------------------------------
# Katalog ↔ frontend TypeScript union drift-guard
# ---------------------------------------------------------------------------
#
# `apps/core/permissions.py` — YAGONA manba (AD-1). Undan ikkita nusxa
# yashaydi: `docs/API_CONTRACT.md` §1.7.1 (generatsiya qilinadigan blok, Docs
# tomonidan byte-ma-byte tekshiriladi) va `frontend/src/types/api.ts` dagi
# `PermissionCode` union'i. Uchinchisi shu paytgacha faqat "ko'z bilan"
# solishtirilardi va aynan shu tufayli `space.change_visibility` (katalog v5)
# frontend'ga tushmay qoldi: `can(my, "space.change_visibility")` yozgan har
# qanday komponent TS xatosiga urilardi, muammo esa qo'lda diff qilinmaguncha
# ko'rinmadi.
#
# Bu test ikki ro'yxatni to'plam sifatida tenglashtiradi. U SKIP QILMAYDI:
# fayl topilmasa yoki union parse bo'lmasa — yiqiladi. Jimgina o'tkazib
# yuboriladigan drift-guard umuman yo'q guard'dan yomonroq (enforcement
# skaneri aynan shunday qilib faqat `views.py` ni ko'radigan bo'lib qolgan
# edi).

#: Yo'l TEST FAYLIGA nisbatan hisoblanadi, `cwd` ga emas: CI pytest'ni
#: `backend/` dan, odam esa ko'pincha repo ildizidan ishga tushiradi.
REPO_ROOT = Path(__file__).resolve().parents[4]
FRONTEND_TYPES = REPO_ROOT / "frontend" / "src" / "types" / "api.ts"

TS_MEMBER_RE = re.compile(r'"([a-z_]+(?:\.[a-z_]+)?)"')


def _read_ts_union(name: str) -> set[str]:
    """`export type <name> = | "a" | "b";` union a'zolarini qaytaradi."""
    assert FRONTEND_TYPES.is_file(), (
        f"Frontend tiplari topilmadi: {FRONTEND_TYPES}. Drift-guard skip "
        f"qilmaydi — yo'lni tuzating yoki testni ataylab o'chiring."
    )
    source = FRONTEND_TYPES.read_text(encoding="utf-8")

    marker = f"export type {name} ="
    start = source.find(marker)
    assert start != -1, (
        f"`{marker}` {FRONTEND_TYPES} da topilmadi — union nomi o'zgargan "
        f"bo'lsa, bu testni ham yangilang."
    )
    end = source.find(";", start)
    assert end != -1, f"`{marker}` bloki `;` bilan tugamagan ({FRONTEND_TYPES})."

    block = source[start + len(marker) : end]
    members = TS_MEMBER_RE.findall(block)
    assert members, (
        f"`{marker}` bloki parse qilinmadi ({FRONTEND_TYPES}). Union formati "
        f"o'zgargan bo'lsa (masalan bitta qatorga yig'ilgan), regex'ni "
        f"yangilang — bo'sh natija bilan test yashil bo'lib qolmasin."
    )
    # `|` ajratgichlari soni a'zolar soniga mos kelsin: shakl buzilib, bir
    # nechta a'zo e'tibordan chetda qolsa ham sezamiz.
    assert block.count("|") == len(members), (
        f"`{marker}` blokidagi `|` soni ({block.count('|')}) a'zolar soniga "
        f"({len(members)}) teng emas — union qo'lda buzilgan bo'lishi mumkin."
    )
    assert len(set(members)) == len(members), (
        f"`{marker}` union'ida takrorlangan a'zo bor: "
        f"{sorted({m for m in members if members.count(m) > 1})}"
    )
    return set(members)


def _drift_message(kind: str, catalog: set[str], typescript: set[str]) -> str:
    missing_in_ts = sorted(catalog - typescript)
    missing_in_catalog = sorted(typescript - catalog)
    return (
        f"{kind} katalog bilan frontend union'i mos emas.\n"
        f"  apps/core/permissions.py da bor, {FRONTEND_TYPES} da YO'Q "
        f"(TS union'iga qo'shing): {missing_in_ts}\n"
        f"  {FRONTEND_TYPES} da bor, katalogda YO'Q "
        f"(TS union'idan olib tashlang): {missing_in_catalog}"
    )


def test_typescript_permission_union_matches_the_catalog():
    """`PermissionCode` union'i katalog bilan bit-ma-bit bir xil bo'lsin."""
    catalog = {permission.code for permission in PERMISSIONS}
    typescript = _read_ts_union("PermissionCode")
    assert catalog == typescript, _drift_message("Ruxsat kodlari", catalog, typescript)
    # Sanoq ham qulflansin: §A "Jami: 49 kod".
    assert len(typescript) == EXPECTED_CODE_COUNT


def test_typescript_group_union_matches_the_catalog():
    """`PermissionGroupKey` — guruh kalitlari ham o'sha manbadan."""
    catalog = set(PERMISSION_GROUPS)
    typescript = _read_ts_union("PermissionGroupKey")
    assert catalog == typescript, _drift_message("Guruh kalitlari", catalog, typescript)
    assert len(typescript) == EXPECTED_GROUP_COUNT
