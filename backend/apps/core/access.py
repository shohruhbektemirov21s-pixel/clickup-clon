"""Workspace-scoped access helpers.

Contract rules (docs/API_CONTRACT.md section 1.7):
- out-of-workspace resources are NEVER disclosed -> 404, never 403;
- in-workspace but role-forbidden -> 403;
- guests cannot see private spaces at all -> 404.
"""

from rest_framework.exceptions import NotFound, PermissionDenied

from apps.core.enums import ROLE_RANK, WorkspaceRole

MIN_RANK = {
    "owner": ROLE_RANK[WorkspaceRole.OWNER],
    "admin": ROLE_RANK[WorkspaceRole.ADMIN],
    "member": ROLE_RANK[WorkspaceRole.MEMBER],
    "guest": ROLE_RANK[WorkspaceRole.GUEST],
}


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
    if ROLE_RANK[membership.role] < MIN_RANK[min_role]:
        raise PermissionDenied()
    return membership


def check_space_visible(membership, space):
    """Guests never see private spaces (existence not disclosed)."""
    if membership.role == WorkspaceRole.GUEST and space.is_private:
        raise NotFound()


def visible_spaces_q(membership):
    from django.db.models import Q

    if membership.role == WorkspaceRole.GUEST:
        return Q(is_private=False)
    return Q()
