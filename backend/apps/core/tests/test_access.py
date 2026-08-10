"""Access layer — docs/DESIGN_PERMISSIONS.md §C."""

import pytest
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.core.access import (
    SPACE_MANAGER_GRANTS,
    SPACE_VIEWER_GRANTS,
    bump_permissions_version,
    clear_permission_cache,
    effective_permissions,
    has_perm,
    has_space_perm,
    my_permissions,
    require_membership_perm,
    require_perm,
    require_space_perm,
    space_access_of,
)
from apps.core.enums import AssignableRole, SpaceAccess, SpaceMemberSource
from apps.core.permissions import ALL_CODES, DEFAULT_MATRIX
from apps.workspaces import services
from apps.workspaces.models import RolePermission, SpaceMember, WorkspaceMember

pytestmark = pytest.mark.django_db


def membership(env, user):
    return WorkspaceMember.objects.select_related("workspace", "user").get(
        workspace=env.workspace, user=user
    )


# ------------------------------------------------------------------ defaults


def test_bootstrap_seeds_the_full_matrix(env):
    """§B.6 — 3 rol × 44 kod = 132 qator."""
    rows = RolePermission.objects.filter(workspace=env.workspace)
    assert rows.count() == len(ALL_CODES) * len(AssignableRole.values) == 132
    assert not rows.filter(role="owner").exists()


def test_ensure_role_permissions_is_idempotent(env):
    assert services.ensure_role_permissions(env.workspace) == 0
    RolePermission.objects.filter(workspace=env.workspace, permission="task.create").delete()
    assert services.ensure_role_permissions(env.workspace) == 3
    assert services.ensure_role_permissions(env.workspace) == 0


def test_effective_permissions_matches_defaults(env):
    effective = effective_permissions(env.workspace)
    for role in AssignableRole.values:
        assert effective[role] == DEFAULT_MATRIX[role]


@pytest.mark.parametrize(
    "role_attr,code,expected",
    [
        ("member", "list.create", True),
        ("member", "space.create", False),
        ("guest", "comment.create", True),
        ("guest", "task.create", False),
        ("admin", "space.create", True),
        ("admin", "workspace.manage_permissions", False),
    ],
)
def test_has_perm_follows_defaults(env, role_attr, code, expected):
    assert has_perm(membership(env, getattr(env, role_attr)), code) is expected


def test_owner_short_circuits_without_rows(env):
    RolePermission.objects.filter(workspace=env.workspace).delete()
    clear_permission_cache()
    owner = membership(env, env.owner)
    assert my_permissions(owner) == ALL_CODES
    assert has_perm(owner, "workspace.manage_permissions") is True


def test_unknown_code_raises_in_debug(env, settings):
    from django.core.exceptions import ImproperlyConfigured

    settings.DEBUG = True
    with pytest.raises(ImproperlyConfigured):
        has_perm(membership(env, env.member), "task.teleport")


# ------------------------------------------------------------ require_* / 404


def test_require_perm_raises_403(env):
    with pytest.raises(PermissionDenied):
        require_perm(membership(env, env.member), "space.create")


def test_require_membership_perm_is_404_before_403(env):
    """C.4: a'zo emas → 404 (mavjudlik oshkor qilinmaydi), keyin 403."""
    with pytest.raises(NotFound):
        require_membership_perm(env.outsider, env.workspace.id, "task.read")
    with pytest.raises(PermissionDenied):
        require_membership_perm(env.guest, env.workspace.id, "task.create")
    assert require_membership_perm(env.member, env.workspace.id, "task.create") is not None


# ------------------------------------------------------------------- caching


def test_permission_revocation_is_immediate(env):
    """R3 merge gate: version bump → keyingi o'qish darhol yangi natija."""
    member = membership(env, env.member)
    assert has_perm(member, "list.create") is True

    RolePermission.objects.filter(
        workspace=env.workspace, role="member", permission="list.create"
    ).update(allowed=False)
    bump_permissions_version(env.workspace)

    # Yangi membership obyekti = yangi request simulyatsiyasi.
    fresh = membership(env, env.member)
    assert has_perm(fresh, "list.create") is False


def test_stale_version_key_is_never_read(env):
    member = membership(env, env.member)
    before = effective_permissions(member.workspace)
    RolePermission.objects.filter(
        workspace=env.workspace, role="member", permission="task.delete"
    ).update(allowed=False)
    # Bump qilmasak — eski kalit, eski natija (kesh ishlayotganining isboti).
    assert effective_permissions(member.workspace) == before
    bump_permissions_version(env.workspace)
    after = effective_permissions(
        WorkspaceMember.objects.select_related("workspace").get(pk=member.pk).workspace
    )
    assert "task.delete" not in after["member"]


def test_cache_hit_costs_no_queries(env, django_assert_num_queries):
    member = membership(env, env.member)
    effective_permissions(member.workspace)  # warm
    with django_assert_num_queries(0):
        for _ in range(20):
            assert has_perm(member, "task.create") is True
            effective_permissions(member.workspace)


# --------------------------------------------------------------- space scope


@pytest.fixture
def private_space(env):
    return services.create_space(
        env.workspace, env.owner, name="Yopiq loyiha", is_private=True
    )


def test_create_space_makes_creator_a_manager(env, private_space):
    row = SpaceMember.objects.get(space=private_space, user=env.owner)
    assert row.access == SpaceAccess.MANAGER
    assert row.source == SpaceMemberSource.AUTO_CREATOR


def test_bootstrap_space_has_creator_manager(env):
    assert (
        SpaceMember.objects.get(space=env.space, user=env.owner).access
        == SpaceAccess.MANAGER
    )


def test_space_manager_gets_local_grants(env, private_space):
    member = membership(env, env.member)
    assert has_perm(member, "space.update") is False
    SpaceMember.objects.create(
        space=private_space, user=env.member, access=SpaceAccess.MANAGER
    )
    assert space_access_of(member, private_space) == SpaceAccess.MANAGER
    for code in sorted(SPACE_MANAGER_GRANTS):
        assert has_space_perm(member, private_space, code) is True, code
    # F-5: bular hech qachon manager orqali berilmaydi.
    for code in ("space.delete", "member.invite", "workspace.update", "tag.create"):
        assert code not in SPACE_MANAGER_GRANTS
    assert has_space_perm(member, private_space, "space.delete") is False


def test_space_viewer_loses_every_write(env, private_space):
    member = membership(env, env.member)
    SpaceMember.objects.create(
        space=private_space, user=env.member, access=SpaceAccess.VIEWER
    )
    assert has_space_perm(member, private_space, "task.read") is True
    for code in ("task.create", "list.create", "comment.create", "folder.create"):
        assert has_space_perm(member, private_space, code) is False, code
    with pytest.raises(PermissionDenied):
        require_space_perm(member, private_space, "task.create")
    assert SPACE_VIEWER_GRANTS < ALL_CODES


def test_space_contributor_falls_back_to_workspace_role(env, private_space):
    member = membership(env, env.member)
    SpaceMember.objects.create(
        space=private_space, user=env.member, access=SpaceAccess.CONTRIBUTOR
    )
    assert has_space_perm(member, private_space, "task.create") is True
    assert has_space_perm(member, private_space, "space.create") is False


def test_owner_bypasses_space_scoping(env, private_space):
    owner = membership(env, env.owner)
    SpaceMember.objects.filter(space=private_space, user=env.owner).update(
        access=SpaceAccess.VIEWER
    )
    assert has_space_perm(owner, private_space, "task.create") is True


def test_removing_a_member_drops_their_space_rows(env, private_space):
    from apps.workspaces.views import _remove_member

    SpaceMember.objects.create(
        space=private_space, user=env.member, access=SpaceAccess.CONTRIBUTOR
    )
    _remove_member(membership(env, env.member))
    assert not SpaceMember.objects.filter(user=env.member, space=private_space).exists()
