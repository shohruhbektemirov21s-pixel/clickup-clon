"""Yangi ruxsat endpoint'lari — docs/DESIGN_PERMISSIONS.md §D.1–D.5."""

import pytest

from conftest import assert_error

from apps.core.access import bump_permissions_version, has_perm
from apps.core.permissions import ALL_CODES, CATALOG_VERSION, DEFAULT_MATRIX
from apps.workspaces.models import RolePermission, WorkspaceMember

pytestmark = pytest.mark.django_db


def matrix_url(env):
    return f"/api/v1/workspaces/{env.workspace.id}/role-permissions/"


def reset_url(env):
    return f"{matrix_url(env)}reset/"


def mine_url(env):
    return f"/api/v1/workspaces/{env.workspace.id}/my-permissions/"


def version(env):
    env.workspace.refresh_from_db(fields=["permissions_version"])
    return env.workspace.permissions_version


# ------------------------------------------------------------------- D.1


def test_catalog_endpoint(env):
    response = env.guest_client.get("/api/v1/permissions/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["catalog_version"] == CATALOG_VERSION
    assert set(body) == {"catalog_version", "groups"}  # pagination yo'q
    codes = {p["code"] for g in body["groups"] for p in g["permissions"]}
    assert codes == ALL_CODES
    for group in body["groups"]:
        for entry in group["permissions"]:
            assert "owner" not in entry["default_roles"]


def test_catalog_requires_auth(api):
    assert api.get("/api/v1/permissions/").status_code == 401


# ------------------------------------------------------------------- D.2


def test_get_matrix_shape(env):
    response = env.owner_client.get(matrix_url(env))
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["workspace_id"] == str(env.workspace.id)
    assert body["version"] == version(env)
    assert body["catalog_version"] == CATALOG_VERSION
    assert set(body["roles"]) == {"owner", "admin", "member", "guest"}
    assert body["roles"]["owner"] == {"locked": True, "permissions": sorted(ALL_CODES)}
    for role in ("admin", "member", "guest"):
        assert body["roles"][role]["locked"] is False
        assert body["roles"][role]["permissions"] == sorted(DEFAULT_MATRIX[role])
    assert body["overrides"] == []  # hech narsa o'zgartirilmagan


@pytest.mark.parametrize("client_attr", ["admin_client", "member_client", "guest_client"])
def test_matrix_is_owner_only(env, client_attr):
    """`workspace.manage_permissions` default'da faqat owner'da (F-1, 1-qavat)."""
    response = getattr(env, client_attr).get(matrix_url(env))
    assert_error(response, 403, "permission_denied")


def test_matrix_hides_existence_from_outsiders(env):
    assert_error(env.outsider_client.get(matrix_url(env)), 404, "not_found")


# ------------------------------------------------------------------- D.3


def test_put_updates_matrix_and_bumps_version(env):
    before = version(env)
    response = env.owner_client.put(
        matrix_url(env),
        {
            "expected_version": before,
            "roles": {"member": {"space.create": True, "task.delete": False}},
        },
        format="json",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["version"] == before + 1 == version(env)
    assert "space.create" in body["roles"]["member"]["permissions"]
    assert "task.delete" not in body["roles"]["member"]["permissions"]

    overrides = {(o["role"], o["permission"]): o["allowed"] for o in body["overrides"]}
    assert overrides == {("member", "space.create"): True, ("member", "task.delete"): False}
    assert overrides and all(o["updated_by_id"] == str(env.owner.id) for o in body["overrides"])

    member = WorkspaceMember.objects.select_related("workspace").get(
        workspace=env.workspace, user=env.member
    )
    assert has_perm(member, "space.create") is True
    assert has_perm(member, "task.delete") is False


def test_matrix_version_conflict_returns_409(env):
    current = version(env)
    payload = {
        "expected_version": current - 1,
        "roles": {"member": {"space.create": True}},
    }
    response = env.owner_client.put(matrix_url(env), payload, format="json")
    error = assert_error(response, 409, "conflict")
    assert error["details"] == {
        "expected_version": current - 1,
        "current_version": current,
    }
    assert version(env) == current  # yon ta'sir yo'q


def test_expected_version_is_mandatory(env):
    response = env.owner_client.put(
        matrix_url(env), {"roles": {"member": {"space.create": True}}}, format="json"
    )
    error = assert_error(response, 400, "validation_error")
    assert "expected_version" in error["details"]


def test_put_unknown_code_returns_400(env):
    response = env.owner_client.put(
        matrix_url(env),
        {"expected_version": version(env), "roles": {"member": {"foo_bar": True}}},
        format="json",
    )
    error = assert_error(response, 400, "validation_error")
    assert error["details"] == {"roles.member.foo_bar": ["Noma'lum ruxsat kodi."]}


def test_put_owner_role_is_rejected(env):
    response = env.owner_client.put(
        matrix_url(env),
        {"expected_version": version(env), "roles": {"owner": {"task.read": False}}},
        format="json",
    )
    error = assert_error(response, 400, "validation_error")
    assert error["details"] == {
        "roles.owner": ["Owner ruxsatlarini o'zgartirib bo'lmaydi."]
    }


def test_owner_only_codes_not_grantable(env):
    """F-1 (3-qavat) merge gate."""
    for code in ("workspace.manage_permissions", "workspace.transfer_ownership"):
        response = env.owner_client.put(
            matrix_url(env),
            {"expected_version": version(env), "roles": {"admin": {code: True}}},
            format="json",
        )
        error = assert_error(response, 400, "validation_error")
        assert error["details"] == {
            f"roles.admin.{code}": ["Bu ruxsat faqat owner uchun."]
        }
    # allowed=False esa no-op sifatida qabul qilinadi
    response = env.owner_client.put(
        matrix_url(env),
        {
            "expected_version": version(env),
            "roles": {"admin": {"workspace.manage_permissions": False}},
        },
        format="json",
    )
    assert response.status_code == 200, response.content


def test_put_monotonic_violation_returns_400(env):
    """AD-5 / F-9 — D.3 jadvalidagi aynan misol."""
    env.owner_client.put(
        matrix_url(env),
        {"expected_version": version(env), "roles": {"member": {"space.create": True}}},
        format="json",
    )
    before = version(env)
    response = env.owner_client.put(
        matrix_url(env),
        {"expected_version": before, "roles": {"admin": {"space.create": False}}},
        format="json",
    )
    error = assert_error(response, 400, "validation_error")
    assert error["details"] == {
        "monotonic": ["'space.create' member'da yoqilgan, admin'da o'chirilgan."]
    }
    assert version(env) == before  # yon ta'sir yo'q


def test_monotonic_allows_a_consistent_downgrade(env):
    response = env.owner_client.put(
        matrix_url(env),
        {
            "expected_version": version(env),
            "roles": {"admin": {"tag.delete": False}, "member": {"tag.delete": False}},
        },
        format="json",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert "tag.delete" not in body["roles"]["admin"]["permissions"]
    assert "tag.delete" not in body["roles"]["member"]["permissions"]


def test_admin_cannot_edit_own_role_row(env):
    """F-1 (2-qavat) merge gate: rank guard.

    1-qavat (`workspace.manage_permissions` owner'da) chetlab o'tilgan holatni
    modellashtiramiz — DB'ga to'g'ridan-to'g'ri grant yozamiz.
    """
    RolePermission.objects.update_or_create(
        workspace=env.workspace,
        role="admin",
        permission="workspace.manage_permissions",
        defaults={"allowed": True},
    )
    bump_permissions_version(env.workspace)

    # Endi admin endpoint'ga kira oladi, lekin o'z qatorini tahrirlay olmaydi.
    assert env.admin_client.get(matrix_url(env)).status_code == 200
    response = env.admin_client.put(
        matrix_url(env),
        {"expected_version": version(env), "roles": {"admin": {"space.delete": False}}},
        format="json",
    )
    error = assert_error(response, 403, "permission_denied")
    assert error["details"] == {"reason": "self_escalation", "role": "admin"}

    # Pastroq rollarni esa o'zgartira oladi.
    ok = env.admin_client.put(
        matrix_url(env),
        {"expected_version": version(env), "roles": {"member": {"task.delete": False}}},
        format="json",
    )
    assert ok.status_code == 200, ok.content


# ------------------------------------------------------------------- D.4


def test_reset_single_role(env):
    env.owner_client.put(
        matrix_url(env),
        {"expected_version": version(env), "roles": {"member": {"space.create": True}}},
        format="json",
    )
    before = version(env)
    response = env.owner_client.post(reset_url(env), {"role": "member"}, format="json")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["version"] == before + 1
    assert body["overrides"] == []
    assert body["roles"]["member"]["permissions"] == sorted(DEFAULT_MATRIX["member"])


def test_reset_all_roles(env):
    env.owner_client.put(
        matrix_url(env),
        {
            "expected_version": version(env),
            "roles": {"guest": {"task.watch": False}, "member": {"task.watch": False}},
        },
        format="json",
    )
    response = env.owner_client.post(reset_url(env), {"role": None}, format="json")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["overrides"] == []
    for role in ("admin", "member", "guest"):
        assert body["roles"][role]["permissions"] == sorted(DEFAULT_MATRIX[role])
    assert RolePermission.objects.filter(workspace=env.workspace).count() == 132


def test_reset_is_owner_only(env):
    assert_error(
        env.admin_client.post(reset_url(env), {"role": "member"}, format="json"),
        403,
        "permission_denied",
    )


# ------------------------------------------------------------------- D.5


@pytest.mark.parametrize("role", ["admin", "member", "guest"])
def test_my_permissions_for_each_role(env, role):
    response = getattr(env, f"{role}_client").get(mine_url(env))
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["workspace_id"] == str(env.workspace.id)
    assert body["role"] == role
    assert body["version"] == version(env)
    assert body["permissions"] == sorted(DEFAULT_MATRIX[role])
    assert body["spaces"] == []


def test_my_permissions_for_owner_is_the_full_catalog(env):
    body = env.owner_client.get(mine_url(env)).json()
    assert body["role"] == "owner"
    assert body["permissions"] == sorted(ALL_CODES)
    # bootstrap "Jamoa bo'limi" ni yaratuvchiga manager qilib biriktirgan
    assert body["spaces"] == [{"space_id": str(env.space.id), "access": "manager"}]


def test_my_permissions_reflects_the_matrix(env):
    env.owner_client.put(
        matrix_url(env),
        {"expected_version": version(env), "roles": {"guest": {"comment.create": False}}},
        format="json",
    )
    body = env.guest_client.get(mine_url(env)).json()
    assert "comment.create" not in body["permissions"]
    assert body["version"] == version(env)


def test_my_permissions_is_404_for_outsiders(env):
    assert_error(env.outsider_client.get(mine_url(env)), 404, "not_found")
