"""Bildirishnomalar va ro'yxatdan o'tgan foydalanuvchini qo'shish — §19 / §4.

Faylning ikki mavzusi bor:

1. **Qo'shish oqimi** — `POST workspaces/{id}/members/` haqiqatan a'zolik
   yaratadimi, ruxsatsizni to'xtatadimi va qo'shilgan odam xabar oladimi.
2. **Bildirishnomaning egaligi** — hech kim begonasini o'qiy, sanay yoki
   o'qilgan deb belgilay olmasligi.
"""

import pytest

from apps.core.enums import InvitationStatus, WorkspaceRole
from apps.notifications.models import Notification, NotificationKind
from apps.workspaces.models import Invitation, WorkspaceMember
from conftest import assert_error, client_for, make_user

pytestmark = pytest.mark.django_db


def members_url(workspace_id):
    return f"/api/v1/workspaces/{workspace_id}/members/"


def search_url(workspace_id):
    return f"/api/v1/workspaces/{workspace_id}/user-search/"


# --------------------------------------------------------------- qo'shish


def test_admin_adds_a_registered_user_directly(env):
    newcomer = make_user("newcomer@test.dev", "New Comer")

    response = env.admin_client.post(
        members_url(env.workspace.id),
        {"user_id": str(newcomer.id), "role": "member"},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.json()["user"]["id"] == str(newcomer.id)
    assert response.json()["role"] == "member"
    assert WorkspaceMember.objects.filter(
        workspace=env.workspace, user=newcomer
    ).exists()
    env.workspace.refresh_from_db()
    assert env.workspace.member_count == 5


def test_the_added_user_gets_a_notification_and_admins_get_one_too(env):
    newcomer = make_user("newcomer@test.dev", "New Comer")

    env.admin_client.post(
        members_url(env.workspace.id),
        {"user_id": str(newcomer.id), "role": "member"},
        format="json",
    )

    added = Notification.objects.get(user=newcomer)
    assert added.kind == NotificationKind.MEMBER_ADDED
    assert added.url == f"/w/{env.workspace.id}"
    assert added.read_at is None
    # Owner xabardor qilinadi, harakatni qilgan adminning o'ziga esa yozilmaydi.
    assert Notification.objects.filter(
        user=env.owner, kind=NotificationKind.MEMBER_JOINED
    ).exists()
    assert not Notification.objects.filter(user=env.admin).exists()


def test_adding_consumes_a_pending_invitation_for_the_same_email(env):
    newcomer = make_user("newcomer@test.dev", "New Comer")
    invitation = Invitation.objects.create(
        workspace=env.workspace,
        email="NEWCOMER@test.dev",
        role="member",
        token="tok_for_newcomer",
        expires_at=env.workspace.created_at.replace(year=2099),
    )

    env.admin_client.post(
        members_url(env.workspace.id),
        {"user_id": str(newcomer.id), "role": "member"},
        format="json",
    )

    invitation.refresh_from_db()
    assert invitation.status == InvitationStatus.ACCEPTED
    assert invitation.accepted_by_id == newcomer.id


def test_adding_the_same_person_twice_is_a_conflict(env):
    response = env.admin_client.post(
        members_url(env.workspace.id),
        {"user_id": str(env.member.id), "role": "member"},
        format="json",
    )
    assert_error(response, 409, "conflict")


def test_owner_role_cannot_be_granted_through_this_endpoint(env):
    newcomer = make_user("newcomer@test.dev", "New Comer")
    response = env.admin_client.post(
        members_url(env.workspace.id),
        {"user_id": str(newcomer.id), "role": "owner"},
        format="json",
    )
    assert_error(response, 400, "validation_error")
    assert not WorkspaceMember.objects.filter(user=newcomer).exists()


def test_an_unknown_user_id_is_a_validation_error_not_a_404(env):
    response = env.admin_client.post(
        members_url(env.workspace.id),
        {"user_id": "00000000-0000-0000-0000-000000000000", "role": "member"},
        format="json",
    )
    assert_error(response, 400, "validation_error")


def test_a_plain_member_cannot_add_anybody(env):
    newcomer = make_user("newcomer@test.dev", "New Comer")
    response = env.member_client.post(
        members_url(env.workspace.id),
        {"user_id": str(newcomer.id), "role": "member"},
        format="json",
    )
    assert_error(response, 403, "permission_denied")
    assert not WorkspaceMember.objects.filter(user=newcomer).exists()


def test_an_outsider_gets_404_for_the_whole_workspace(env):
    newcomer = make_user("newcomer@test.dev", "New Comer")
    response = env.outsider_client.post(
        members_url(env.workspace.id),
        {"user_id": str(newcomer.id), "role": "member"},
        format="json",
    )
    assert response.status_code in (403, 404)
    assert not WorkspaceMember.objects.filter(user=newcomer).exists()


# ---------------------------------------------------------------- qidiruv


def test_user_search_marks_who_is_already_a_member(env):
    make_user("kandidat@test.dev", "Kandidat Nomzod")

    response = env.admin_client.get(search_url(env.workspace.id), {"q": "kandidat"})

    assert response.status_code == 200, response.content
    rows = response.json()["results"]
    assert [row["user"]["email"] for row in rows] == ["kandidat@test.dev"]
    assert rows[0]["is_member"] is False
    assert rows[0]["role"] is None

    response = env.admin_client.get(search_url(env.workspace.id), {"q": "member@"})
    row = response.json()["results"][0]
    assert row["is_member"] is True
    assert row["role"] == WorkspaceRole.MEMBER


def test_user_search_needs_two_characters(env):
    make_user("kandidat@test.dev", "Kandidat Nomzod")
    response = env.admin_client.get(search_url(env.workspace.id), {"q": "k"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_user_search_is_closed_to_members_and_guests(env):
    assert_error(
        env.member_client.get(search_url(env.workspace.id), {"q": "test"}),
        403,
        "permission_denied",
    )
    assert_error(
        env.guest_client.get(search_url(env.workspace.id), {"q": "test"}),
        403,
        "permission_denied",
    )


# ----------------------------------------------------------- bildirishnoma


def _notify(user, workspace, **kwargs):
    from apps.notifications.services import notify

    return notify(
        user=user,
        workspace=workspace,
        kind=NotificationKind.MEMBER_ADDED,
        title=kwargs.pop("title", "Sinov"),
        **kwargs,
    )


def test_the_list_only_ever_returns_your_own_notifications(env):
    _notify(env.member, env.workspace, title="Meniki")
    _notify(env.admin, env.workspace, title="Boshqaniki")

    response = env.member_client.get("/api/v1/notifications/")

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["title"] == "Meniki"


def test_unread_count_and_marking_one_read(env):
    notification = _notify(env.member, env.workspace, title="Birinchi")
    _notify(env.member, env.workspace, title="Ikkinchi")

    assert env.member_client.get("/api/v1/notifications/unread-count/").json() == {
        "count": 2
    }

    response = env.member_client.post(f"/api/v1/notifications/{notification.id}/read/")
    assert response.status_code == 200, response.content
    assert response.json()["is_read"] is True
    assert env.member_client.get("/api/v1/notifications/unread-count/").json() == {
        "count": 1
    }

    # Idempotent: ikkinchi marta ham 200, sanoq o'zgarmaydi.
    assert (
        env.member_client.post(f"/api/v1/notifications/{notification.id}/read/").status_code
        == 200
    )
    assert env.member_client.get("/api/v1/notifications/unread-count/").json() == {
        "count": 1
    }


def test_unread_filter_and_read_all(env):
    _notify(env.member, env.workspace, title="Birinchi")
    _notify(env.member, env.workspace, title="Ikkinchi")

    response = env.member_client.post("/api/v1/notifications/read-all/", format="json")
    assert response.status_code == 200
    assert response.json() == {"updated": 2}

    unread = env.member_client.get("/api/v1/notifications/", {"unread": "true"})
    assert unread.json()["count"] == 0


def test_you_cannot_mark_somebody_elses_notification_read(env):
    notification = _notify(env.admin, env.workspace, title="Boshqaniki")

    response = env.member_client.post(f"/api/v1/notifications/{notification.id}/read/")

    assert_error(response, 404, "not_found")
    notification.refresh_from_db()
    assert notification.read_at is None


def test_removing_a_member_notifies_them_but_leaving_does_not(env):
    env.admin_client.delete(f"{members_url(env.workspace.id)}{env.member.id}/")
    assert Notification.objects.filter(
        user=env.member, kind=NotificationKind.MEMBER_REMOVED
    ).exists()

    # O'zi chiqib ketgan odamga xabar yozilmaydi.
    env.guest_client.post(f"{members_url(env.workspace.id)}leave/")
    assert not Notification.objects.filter(
        user=env.guest, kind=NotificationKind.MEMBER_REMOVED
    ).exists()


def test_role_change_notifies_the_target(env):
    env.owner_client.patch(
        f"{members_url(env.workspace.id)}{env.member.id}/",
        {"role": "admin"},
        format="json",
    )
    notification = Notification.objects.get(
        user=env.member, kind=NotificationKind.ROLE_CHANGED
    )
    assert "Admin" in notification.body


def test_assigning_a_task_notifies_the_assignee_but_not_the_actor(env):
    response = env.owner_client.post(
        f"/api/v1/lists/{env.list.id}/tasks/",
        {"title": "Hisobot", "assignee_ids": [str(env.member.id), str(env.owner.id)]},
        format="json",
    )
    assert response.status_code == 201, response.content

    assert Notification.objects.filter(
        user=env.member, kind=NotificationKind.TASK_ASSIGNED
    ).exists()
    assert not Notification.objects.filter(
        user=env.owner, kind=NotificationKind.TASK_ASSIGNED
    ).exists()


def test_accepting_an_invitation_notifies_the_inviter(env):
    invitation = Invitation.objects.create(
        workspace=env.workspace,
        email="tashqi@test.dev",
        role="member",
        token="tok_accept_me",
        invited_by=env.admin,
        expires_at=env.workspace.created_at.replace(year=2099),
    )
    guest_user = make_user("tashqi@test.dev", "Tashqi Odam")

    response = client_for(guest_user).post(
        "/api/v1/invitations/accept/", {"token": invitation.token}, format="json"
    )
    assert response.status_code in (200, 201), response.content

    assert Notification.objects.filter(
        user=env.admin, kind=NotificationKind.INVITATION_ACCEPTED
    ).exists()
