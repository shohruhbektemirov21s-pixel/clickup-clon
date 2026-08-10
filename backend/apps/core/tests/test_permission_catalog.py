"""Katalog invariantlari — docs/DESIGN_PERMISSIONS.md §A, §I (merge gate)."""

import re

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

# §A — "Jami: 44 kod, 8 guruh."
EXPECTED_CODE_COUNT = 44
EXPECTED_GROUP_COUNT = 8

#: AD-9 — §B.7 ko'chirish jadvalidan olingan kutilmalar. Bu jadval bugungi
#: `min_role=` xatti-harakatini bit-ma-bit takrorlaydi; buzilsa mavjud
#: testlar ham yiqilishi kerak edi.
LEGACY_EXPECTATIONS = {
    # (kod, rol) -> kutilgan default
    "owner-only (min_role='owner')": {
        "workspace.update": set(),
        "workspace.delete": set(),
    },
    "admin+ (min_role='admin')": {
        "member.invite": {"admin"},
        "member.remove": {"admin"},
        "member.role_change": {"admin"},
        "invitation.read": {"admin"},
        "invitation.manage": {"admin"},
        "space.create": {"admin"},
        "space.update": {"admin"},
        "space.delete": {"admin"},
        "space.manage_statuses": {"admin"},
        "list.manage_statuses": {"admin"},
        "folder.delete_cascade": {"admin"},
        "task.restore": {"admin"},
        "task.view_deleted": {"admin"},
        "comment.delete_any": {"admin"},
        "space.read_private": {"admin"},
        "space.manage_members": {"admin"},
    },
    "member+ (min_role='member')": {
        "member.read": {"admin", "member"},
        "folder.create": {"admin", "member"},
        "folder.update": {"admin", "member"},
        "folder.delete": {"admin", "member"},
        "list.create": {"admin", "member"},
        "list.update": {"admin", "member"},
        "list.delete": {"admin", "member"},
        "list.move": {"admin", "member"},
        "task.create": {"admin", "member"},
        "task.update": {"admin", "member"},
        "task.delete": {"admin", "member"},
        "task.move": {"admin", "member"},
        "task.assign": {"admin", "member"},
        "tag.create": {"admin", "member"},
        "tag.update": {"admin", "member"},
        "tag.delete": {"admin", "member"},
    },
    "guest+ (min_role='guest')": {
        "workspace.read": {"admin", "member", "guest"},
        "space.read": {"admin", "member", "guest"},
        "task.read": {"admin", "member", "guest"},
        "task.update_assigned": {"admin", "member", "guest"},
        "task.watch": {"admin", "member", "guest"},
        "comment.create": {"admin", "member", "guest"},
        "comment.update_own": {"admin", "member", "guest"},
        "comment.delete_own": {"admin", "member", "guest"},
    },
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


@pytest.mark.parametrize("group_name", sorted(LEGACY_EXPECTATIONS))
def test_default_matrix_matches_legacy_roles(group_name):
    """AD-9 — regressiya detektori: defaultlar §1.7 ni bit-ma-bit takrorlaydi."""
    for code, expected in LEGACY_EXPECTATIONS[group_name].items():
        assert set(PERMISSION_BY_CODE[code].defaults) == expected, code


def test_legacy_expectations_cover_every_code():
    covered = {
        code for table in LEGACY_EXPECTATIONS.values() for code in table
    } | OWNER_ONLY_CODES
    assert covered == ALL_CODES, sorted(ALL_CODES - covered)


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
