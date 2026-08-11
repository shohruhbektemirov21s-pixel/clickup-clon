from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.access import bump_permissions_version
from apps.core.enums import TaskStatus
from apps.workspaces import services
from apps.workspaces.models import (
    Folder,
    Invitation,
    RolePermission,
    Space,
    SpaceMember,
    TaskList,
    Workspace,
    WorkspaceMember,
)
from conftest import assert_error, client_for, make_user

pytestmark = pytest.mark.django_db


def ws_url(workspace_id, suffix=""):
    return f"/api/v1/workspaces/{workspace_id}/{suffix}"


# ------------------------------------------------------------- workspaces


def test_create_workspace_bootstraps_and_sets_my_role(env):
    response = env.member_client.post(
        "/api/v1/workspaces/", {"name": "Side Project"}, format="json"
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["my_role"] == "owner"
    assert body["member_count"] == 1
    assert body["slug"]
    space = Space.objects.get(workspace_id=body["id"])
    assert space.name == "Jamoa bo'limi"
    # A fresh workspace starts from zero — scaffolding only, no sample tasks.
    assert space.lists.get().tasks.count() == 0


def test_workspace_list_shows_only_memberships(env):
    response = env.outsider_client.get("/api/v1/workspaces/")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"count", "next", "previous", "results"}
    assert body["count"] == 0

    mine = env.guest_client.get("/api/v1/workspaces/")
    assert mine.json()["count"] == 1
    assert mine.json()["results"][0]["my_role"] == "guest"


def test_workspace_patch_is_owner_only(env):
    url = ws_url(env.workspace.id)
    denied = env.admin_client.patch(url, {"name": "Nope"}, format="json")
    assert_error(denied, 403, "permission_denied")
    ok = env.owner_client.patch(url, {"name": "Acme Renamed"}, format="json")
    assert ok.status_code == 200
    assert ok.json()["name"] == "Acme Renamed"


def test_workspace_delete_requires_confirm_name(env):
    """204 o'zi hech nimani isbotlamaydi — butun daraxt yo'q bo'lishi SHART."""
    from apps.tasks.models import Task

    url = ws_url(env.workspace.id)
    bad = env.owner_client.delete(url, {"confirm_name": "wrong"}, format="json")
    assert_error(bad, 400, "validation_error")
    # ...va rad etilgan urinish hech narsani o'chirmagan.
    assert Workspace.objects.filter(pk=env.workspace.id).exists()

    task = Task.objects.create(
        list=env.list,
        status=TaskStatus.TODO,
        title="O'chib ketishi kerak",
        position="n",
        created_by=env.owner,
        updated_by=env.owner,
    )
    workspace_id, space_id, list_id = env.workspace.id, env.space.id, env.list.id

    ok = env.owner_client.delete(url, {"confirm_name": "Acme Inc."}, format="json")
    assert ok.status_code == 204
    assert not Workspace.objects.filter(pk=workspace_id).exists()
    assert not Space.objects.filter(pk=space_id).exists()
    assert not TaskList.objects.filter(pk=list_id).exists()
    assert not WorkspaceMember.objects.filter(workspace_id=workspace_id).exists()
    assert not SpaceMember.objects.filter(space_id=space_id).exists()
    # Yumshoq o'chirilganlari ham qolmasligi kerak (idish o'chirilganda
    # vazifalar `hard_delete()` bilan ketadi).
    assert not Task.all_objects.filter(pk=task.pk).exists()


def test_workspace_read_is_an_enforced_code_not_a_decoration(env):
    """`workspace.read` matritsada bor — demak uni o'chirish ISHLASHI kerak."""
    RolePermission.objects.update_or_create(
        workspace=env.workspace,
        role="member",
        permission="workspace.read",
        defaults={"allowed": False},
    )
    bump_permissions_version(env.workspace)

    assert_error(env.member_client.get(ws_url(env.workspace.id)), 403, "permission_denied")
    assert_error(
        env.member_client.get(ws_url(env.workspace.id, "tree/")), 403, "permission_denied"
    )
    assert_error(
        env.member_client.get(ws_url(env.workspace.id, "search/?q=Boshlash")),
        403,
        "permission_denied",
    )
    # §C.4 tartibi buzilmaydi: a'zo bo'lmagan odam uchun baribir 404.
    assert_error(env.outsider_client.get(ws_url(env.workspace.id)), 404, "not_found")
    # owner qulflangan (AD-3) va admin'ning kodi olinmagan.
    assert env.owner_client.get(ws_url(env.workspace.id)).status_code == 200
    assert env.admin_client.get(ws_url(env.workspace.id, "tree/")).status_code == 200


def test_client_supplied_id_is_not_a_global_existence_oracle(env):
    """§1.4 — `409` qayta urinishni aniqlash uchun, begona resursni ochish uchun emas."""
    # (a) O'z doirasidagi dublikat — kontrakt talab qilgani, 409.
    dup = env.admin_client.post(
        f"/api/v1/spaces/{env.space.id}/lists/",
        {"id": str(env.list.id), "name": "Boshqa nom"},
        format="json",
    )
    assert_error(dup, 409, "conflict")

    # (b) Boshqa ish maydonidagi ro'yxatning id'si. Ilgari bu ham 409 berardi
    # va shu bilan "bu UUID band" degan javobni har qanday odamga sotardi.
    other_owner = make_user("other-owner@test.dev")
    other_workspace = services.bootstrap_workspace(other_owner, name="Boshqa kompaniya")
    foreign_list = other_workspace.spaces.get().lists.get()
    created = env.admin_client.post(
        f"/api/v1/spaces/{env.space.id}/lists/",
        {"id": str(foreign_list.id), "name": "Yangi ro'yxat"},
        format="json",
    )
    assert created.status_code == 201, created.content
    assert created.json()["id"] != str(foreign_list.id)
    foreign_list.refresh_from_db()
    assert foreign_list.name == "Boshlash"  # begona resursga tegilmagan

    # (c) Xuddi shu qoida ish maydonining o'zida ham.
    outsider_created = env.outsider_client.post(
        "/api/v1/workspaces/", {"id": str(env.workspace.id), "name": "Nusxa"}, format="json"
    )
    assert outsider_created.status_code == 201, outsider_created.content
    assert outsider_created.json()["id"] != str(env.workspace.id)
    mine = env.member_client.post(
        "/api/v1/workspaces/", {"id": str(env.workspace.id), "name": "Yana"}, format="json"
    )
    assert_error(mine, 409, "conflict")


def test_out_of_workspace_is_404_never_403(env):
    response = env.outsider_client.get(ws_url(env.workspace.id))
    assert_error(response, 404, "not_found")
    tree = env.outsider_client.get(ws_url(env.workspace.id, "tree/"))
    assert_error(tree, 404, "not_found")


def test_tree_shape(env):
    response = env.member_client.get(ws_url(env.workspace.id, "tree/"))
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Acme Inc."
    space = body["spaces"][0]
    assert space["name"] == "Jamoa bo'limi"
    assert space["folders"] == []
    assert space["lists"][0]["name"] == "Boshlash"
    assert space["lists"][0]["task_count"] == 0
    assert space["lists"][0]["open_task_count"] == 0


# ------------------------------------------------------------- members


def test_member_roster_order_and_guest_can_read_it(env):
    """2026-08: `member.read` guest'ga ham berildi — roster hammaga ochiq.

    Ilgari bu test mehmon uchun `403` kutardi. Endi `200`, ammo emaillar
    mehmondan yashiriladi — `apps/core/tests/test_permission_policy.py`
    dagi `test_guest_sees_names_but_not_emails` shuni qulflaydi.
    """
    response = env.member_client.get(ws_url(env.workspace.id, "members/"))
    assert response.status_code == 200
    roles = [m["role"] for m in response.json()["results"]]
    assert roles == ["owner", "admin", "member", "guest"]

    as_guest = env.guest_client.get(ws_url(env.workspace.id, "members/"))
    assert as_guest.status_code == 200, as_guest.content
    assert [m["role"] for m in as_guest.json()["results"]] == roles


def test_role_change_rules(env):
    member_url = ws_url(env.workspace.id, f"members/{env.member.id}/")
    owner_url = ws_url(env.workspace.id, f"members/{env.owner.id}/")

    # admin may move members among admin/member/guest
    ok = env.admin_client.patch(member_url, {"role": "guest"}, format="json")
    assert ok.status_code == 200
    assert ok.json()["role"] == "guest"

    # admin may not grant owner, nor touch an owner
    denied = env.admin_client.patch(member_url, {"role": "owner"}, format="json")
    assert_error(denied, 403, "permission_denied")
    denied = env.admin_client.patch(owner_url, {"role": "member"}, format="json")
    assert_error(denied, 403, "permission_denied")

    # member/guest callers are 403
    denied = env.member_client.patch(member_url, {"role": "member"}, format="json")
    assert_error(denied, 403, "permission_denied")

    # owner can promote to owner
    ok = env.owner_client.patch(member_url, {"role": "owner"}, format="json")
    assert ok.status_code == 200


def test_last_owner_invariants(env):
    owner_url = ws_url(env.workspace.id, f"members/{env.owner.id}/")
    demote = env.owner_client.patch(owner_url, {"role": "member"}, format="json")
    assert_error(demote, 409, "conflict")
    remove = env.owner_client.delete(owner_url)
    assert_error(remove, 409, "conflict")
    leave = env.owner_client.post(ws_url(env.workspace.id, "members/leave/"))
    assert_error(leave, 409, "conflict")


def test_member_leave_and_removal(env):
    leave = env.member_client.post(ws_url(env.workspace.id, "members/leave/"))
    assert leave.status_code == 204
    # subsequent requests in the workspace are 404
    after = env.member_client.get(ws_url(env.workspace.id))
    assert_error(after, 404, "not_found")

    remove = env.admin_client.delete(ws_url(env.workspace.id, f"members/{env.guest.id}/"))
    assert remove.status_code == 204
    env.workspace.refresh_from_db()
    assert env.workspace.member_count == 2  # owner + admin remain


# --------------------------------------------- atomicity & side effects
#
# Bu blok "yarim bajarilgan" holatlarni qulflaydi. Har bir test amalning
# O'RTASIDA yiqiladi va DBda hech qanday iz qolmasligini tekshiradi. Ilgari
# bu yo'llar tranzaksiyasiz edi: chaqiruvchi 500 olardi, lekin a'zo yarim
# o'chirilgan, taklif yarim qabul qilingan yoki jild yarim ajratilgan bo'lib
# qolardi.


def _boom(*args, **kwargs):
    raise RuntimeError("qasddan yiqilish")


def test_member_removal_is_all_or_nothing(env, monkeypatch):
    from apps.tasks.models import Task, TaskAssignee

    task = Task.objects.create(
        list=env.list,
        status=TaskStatus.TODO,
        title="Biriktirilgan",
        position="n",
        created_by=env.owner,
        updated_by=env.owner,
    )
    TaskAssignee.objects.create(task=task, user=env.member, assigned_by=env.owner)
    SpaceMember.objects.create(space=env.space, user=env.member, access="contributor")

    # Oxirgi qadam (`member_count` ni yangilash) yiqiladi.
    monkeypatch.setattr(services, "refresh_member_count", _boom)
    response = env.owner_client.delete(ws_url(env.workspace.id, f"members/{env.member.id}/"))
    assert response.status_code == 500

    assert WorkspaceMember.objects.filter(workspace=env.workspace, user=env.member).exists()
    assert SpaceMember.objects.filter(space=env.space, user=env.member).exists()
    assert TaskAssignee.objects.filter(task=task, user=env.member).exists()


def test_invitation_accept_is_all_or_nothing(env, monkeypatch):
    invitation = _new_invitation(env, email="atomic@x.io", role="member")
    invited = make_user("atomic@x.io")

    monkeypatch.setattr(services, "refresh_member_count", _boom)
    response = client_for(invited).post(
        "/api/v1/invitations/accept/", {"token": invitation.token}, format="json"
    )
    assert response.status_code == 500

    assert not WorkspaceMember.objects.filter(workspace=env.workspace, user=invited).exists()
    invitation.refresh_from_db()
    assert invitation.status == "pending"
    assert invitation.accepted_by_id is None
    assert invitation.accepted_at is None


def test_folder_detach_is_all_or_nothing(env, monkeypatch):
    folders_url = f"/api/v1/spaces/{env.space.id}/folders/"
    folder_id = env.admin_client.post(folders_url, {"name": "Atomik"}, format="json").json()["id"]
    inside = env.admin_client.post(
        f"/api/v1/spaces/{env.space.id}/lists/",
        {"name": "Ichkarida", "folder_id": folder_id},
        format="json",
    ).json()

    original = services.detach_folder_lists

    def detach_then_fail(folder):
        original(folder)
        raise RuntimeError("qasddan yiqilish")

    monkeypatch.setattr(services, "detach_folder_lists", detach_then_fail)
    response = env.admin_client.delete(f"/api/v1/folders/{folder_id}/?strategy=detach")
    assert response.status_code == 500

    # Ro'yxat hali ham jildda va jildning o'zi ham joyida.
    assert Folder.objects.filter(pk=folder_id).exists()
    assert str(TaskList.objects.get(pk=inside["id"]).folder_id) == folder_id


def test_making_a_space_private_backfills_bumps_and_revokes(
    env, monkeypatch, django_capture_on_commit_callbacks
):
    """`is_private` — chegara, oddiy ustun emas (§B.5).

    Uni o'zgartirish (a) menejer biriktiradi, (b) `permissions_version` ni
    oshiradi va (c) ko'rinishni yo'qotgan har bir odamning ochiq soketini
    yopadi. Ilgari `serializer.save()` uchalasini ham o'tkazib yuborardi.
    """
    from apps.realtime import events as realtime_events

    revoked = []
    monkeypatch.setattr(
        realtime_events,
        "emit_access_revoked",
        lambda user_id, **kw: revoked.append((str(user_id), kw.get("space_id"))),
    )
    space = services.create_space(env.workspace, env.admin, name="Reklama")
    SpaceMember.objects.filter(space=space, user=env.admin).delete()
    before = Workspace.objects.get(pk=env.workspace.id).permissions_version
    assert env.guest_client.get(f"/api/v1/spaces/{space.id}/").status_code == 200

    with django_capture_on_commit_callbacks(execute=True):
        response = env.admin_client.patch(
            f"/api/v1/spaces/{space.id}/", {"is_private": True}, format="json"
        )
    assert response.status_code == 200, response.content
    assert response.json()["is_private"] is True

    # (a) yaratuvchi menejer sifatida qaytariladi — bo'lim qulflanib qolmasin.
    assert SpaceMember.objects.filter(space=space, user=env.admin, access="manager").exists()
    # (b) klient `my-permissions/` ni qayta o'qishi uchun versiya oshadi.
    assert Workspace.objects.get(pk=env.workspace.id).permissions_version > before
    # (c) faqat ko'rinishni YO'QOTGAN odam (mehmon) xabar oladi.
    assert revoked == [(str(env.guest.id), space.id)]
    assert_error(env.guest_client.get(f"/api/v1/spaces/{space.id}/"), 404, "not_found")

    # Qiymat o'zgarmasa hech qanday yon ta'sir bo'lmaydi.
    revoked.clear()
    unchanged = Workspace.objects.get(pk=env.workspace.id).permissions_version
    again = env.admin_client.patch(
        f"/api/v1/spaces/{space.id}/", {"name": "Reklama 2", "is_private": True}, format="json"
    )
    assert again.status_code == 200, again.content
    assert revoked == []
    assert Workspace.objects.get(pk=env.workspace.id).permissions_version == unchanged


def test_admin_visibility_actions_go_through_the_service(
    env, monkeypatch, django_capture_on_commit_callbacks
):
    """`/admin/` ruxsat qatlamini chetlab o'tolmaydi (§G.3, F-7).

    `queryset.update(is_private=True)` hech qanday yon ta'sir chiqarmasdi —
    mehmon ochiq soket bilan endi yopiq bo'lgan bo'limda qolib ketardi.
    """
    from django.contrib import admin as django_admin

    from apps.realtime import events as realtime_events
    from apps.workspaces.admin import SpaceAdmin

    revoked = []
    monkeypatch.setattr(
        realtime_events, "emit_access_revoked", lambda user_id, **kw: revoked.append(str(user_id))
    )
    space = services.create_space(env.workspace, env.admin, name="Panel")
    before = Workspace.objects.get(pk=env.workspace.id).permissions_version

    space_admin = SpaceAdmin(Space, django_admin.site)
    space_admin.message_user = lambda *args, **kwargs: None

    class _Req:
        user = env.owner

    with django_capture_on_commit_callbacks(execute=True):
        space_admin.make_private(_Req(), Space.objects.filter(pk=space.pk))

    space.refresh_from_db()
    assert space.is_private is True
    assert revoked == [str(env.guest.id)]
    assert Workspace.objects.get(pk=env.workspace.id).permissions_version > before
    assert SpaceMember.objects.filter(space=space, user=env.admin, access="manager").exists()

    revoked.clear()
    with django_capture_on_commit_callbacks(execute=True):
        space_admin.make_public(_Req(), Space.objects.filter(pk=space.pk))
    space.refresh_from_db()
    assert space.is_private is False
    assert revoked == []  # ochilganda hech kim huquq yo'qotmaydi


def test_my_permissions_carries_both_counters(env):
    """`version` va `catalog_version` — ikki xil hisoblagich, birlashtirilmaydi."""
    from apps.core.permissions import CATALOG_VERSION

    body = env.guest_client.get(ws_url(env.workspace.id, "my-permissions/")).json()
    assert body["catalog_version"] == CATALOG_VERSION
    assert body["version"] == env.workspace.permissions_version

    # Matritsani tahrirlash `version` ni oshiradi, katalog versiyasini EMAS
    # (katalog kod bilan keladi, deploy'da o'zgaradi).
    bump_permissions_version(env.workspace)
    after = env.guest_client.get(ws_url(env.workspace.id, "my-permissions/")).json()
    assert after["version"] == body["version"] + 1
    assert after["catalog_version"] == CATALOG_VERSION


# ------------------------------------------------------------- invitations


def test_invitation_flow(env, api):
    url = ws_url(env.workspace.id, "invitations/")
    created = env.admin_client.post(
        url, {"email": "carlos@client.com", "role": "guest"}, format="json"
    )
    assert created.status_code == 201, created.content
    body = created.json()
    assert body["status"] == "pending"
    assert "token" not in body

    # duplicate pending -> 409
    dup = env.admin_client.post(url, {"email": "Carlos@client.com", "role": "member"}, format="json")
    assert_error(dup, 409, "conflict")

    # owner role is not invitable
    bad = env.admin_client.post(url, {"email": "x@y.io", "role": "owner"}, format="json")
    assert_error(bad, 400, "validation_error")

    # member cannot list invitations
    denied = env.member_client.get(url)
    assert_error(denied, 403, "permission_denied")

    token = Invitation.objects.get(pk=body["id"]).token

    # public lookup
    lookup = api.get(f"/api/v1/invitations/lookup/?token={token}")
    assert lookup.status_code == 200
    assert lookup.json()["workspace_name"] == "Acme Inc."
    assert lookup.json()["email"] == "carlos@client.com"

    missing = api.get("/api/v1/invitations/lookup/?token=nope")
    assert_error(missing, 404, "not_found")

    # accept must come from the invited email
    invited = make_user("carlos@client.com")
    wrong_user = env.member_client.post(
        "/api/v1/invitations/accept/", {"token": token}, format="json"
    )
    assert_error(wrong_user, 403, "permission_denied")

    accepted = client_for(invited).post(
        "/api/v1/invitations/accept/", {"token": token}, format="json"
    )
    assert accepted.status_code == 200, accepted.content
    assert accepted.json()["workspace_id"] == str(env.workspace.id)
    assert accepted.json()["member"]["role"] == "guest"
    assert WorkspaceMember.objects.filter(workspace=env.workspace, user=invited).exists()

    # replay of a consumed token -> 409
    replay = client_for(invited).post(
        "/api/v1/invitations/accept/", {"token": token}, format="json"
    )
    assert_error(replay, 409, "conflict")


def test_invite_existing_member_conflict_and_revoke(env):
    url = ws_url(env.workspace.id, "invitations/")
    conflict = env.owner_client.post(
        url, {"email": "member@test.dev", "role": "member"}, format="json"
    )
    assert_error(conflict, 409, "conflict")

    created = env.owner_client.post(url, {"email": "new@x.io", "role": "member"}, format="json")
    invitation_id = created.json()["id"]
    revoked = env.owner_client.delete(f"/api/v1/invitations/{invitation_id}/")
    assert revoked.status_code == 204
    again = env.owner_client.delete(f"/api/v1/invitations/{invitation_id}/")
    assert_error(again, 409, "conflict")


def _new_invitation(env, email="resend@x.io", role="member"):
    created = env.owner_client.post(
        ws_url(env.workspace.id, "invitations/"), {"email": email, "role": role}, format="json"
    )
    assert created.status_code == 201, created.content
    return Invitation.objects.get(pk=created.json()["id"])


def resend_url(invitation):
    return f"/api/v1/invitations/{invitation.id}/resend/"


def test_resend_is_throttled_to_one_per_five_minutes(env):
    """`create_invitation` `last_sent_at=now` qo'yadi — darhol qayta yuborish 429."""
    invitation = _new_invitation(env)
    immediate = env.owner_client.post(resend_url(invitation))
    assert_error(immediate, 429, "throttled")
    invitation.refresh_from_db()
    assert invitation.sent_count == 1  # hisoblagich ham qimirlamagan

    # Oyna ochilgach — 200.
    Invitation.objects.filter(pk=invitation.pk).update(
        last_sent_at=timezone.now() - timedelta(minutes=5, seconds=1)
    )
    ok = env.owner_client.post(resend_url(invitation))
    assert ok.status_code == 200, ok.content
    assert ok.json()["sent_count"] == 2


def test_resend_extends_expires_at(env):
    """XAVFSIZLIK: qayta yuborish taklif MUDDATINI uzaytiradi.

    Ya'ni `invitation.manage` ga ega odam bitta taklifni (5 martagacha)
    haftalab tirik ushlab tura oladi. Bu ataylab qilingan xatti-harakat
    (§5), lekin hech qanday test uni qulflamagan edi — endi o'zgarishi
    uchun shu test ham o'zgarishi kerak.
    """
    invitation = _new_invitation(env, email="ttl@x.io")
    original_expiry = invitation.expires_at
    Invitation.objects.filter(pk=invitation.pk).update(
        last_sent_at=timezone.now() - timedelta(minutes=6),
        expires_at=timezone.now() + timedelta(minutes=1),
    )
    response = env.owner_client.post(resend_url(invitation))
    assert response.status_code == 200, response.content

    invitation.refresh_from_db()
    assert invitation.expires_at > original_expiry
    assert invitation.expires_at > timezone.now() + timedelta(days=6)
    assert invitation.last_sent_at is not None

    # ...va uzaytirilgan taklif yana ishlaydi (aynan shu narsa xavfli).
    lookup = env.member_client.get(f"/api/v1/invitations/lookup/?token={invitation.token}")
    assert lookup.status_code == 200


def test_resend_stops_at_five_sends(env):
    invitation = _new_invitation(env, email="cap@x.io")
    Invitation.objects.filter(pk=invitation.pk).update(
        sent_count=5, last_sent_at=timezone.now() - timedelta(hours=1)
    )
    capped = env.owner_client.post(resend_url(invitation))
    assert_error(capped, 409, "conflict")
    invitation.refresh_from_db()
    assert invitation.sent_count == 5
    assert invitation.status == "pending"  # cheklov taklifni buzmaydi


def test_resend_rejects_non_pending_and_unauthorised_callers(env):
    invitation = _new_invitation(env, email="dead@x.io")

    # `invitation.manage` yo'q -> 403 (409 dan OLDIN).
    denied = env.member_client.post(resend_url(invitation))
    assert_error(denied, 403, "permission_denied")
    # ish maydonidan tashqarida -> 404, taklif mavjudligi oshkor qilinmaydi.
    assert_error(env.outsider_client.post(resend_url(invitation)), 404, "not_found")

    revoked = env.owner_client.delete(f"/api/v1/invitations/{invitation.id}/")
    assert revoked.status_code == 204
    Invitation.objects.filter(pk=invitation.pk).update(
        last_sent_at=timezone.now() - timedelta(hours=1)
    )
    assert_error(env.owner_client.post(resend_url(invitation)), 409, "conflict")

    accepted = _new_invitation(env, email="used@x.io")
    Invitation.objects.filter(pk=accepted.pk).update(
        status="accepted", last_sent_at=timezone.now() - timedelta(hours=1)
    )
    assert_error(env.owner_client.post(resend_url(accepted)), 409, "conflict")


def test_expired_invitation_is_404_everywhere_and_creates_no_member(env, api):
    """Muddat ilgari faqat `register?invite_token=` orqali sinalgan edi.

    `accept/`, `decline/` va ochiq `lookup/` ham xuddi shunday **404** berishi
    kerak (403/409 emas: mavjudligi ham oshkor qilinmaydi) va hech qanday
    a'zolik yaratmasligi shart.
    """
    invitation = _new_invitation(env, email="stale@x.io", role="admin")
    Invitation.objects.filter(pk=invitation.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    invitation.refresh_from_db()

    assert_error(api.get(f"/api/v1/invitations/lookup/?token={invitation.token}"), 404, "not_found")

    invited = make_user("stale@x.io")
    invited_client = client_for(invited)
    accept = invited_client.post(
        "/api/v1/invitations/accept/", {"token": invitation.token}, format="json"
    )
    assert_error(accept, 404, "not_found")
    decline = invited_client.post(
        "/api/v1/invitations/decline/", {"token": invitation.token}, format="json"
    )
    assert_error(decline, 404, "not_found")

    assert not WorkspaceMember.objects.filter(workspace=env.workspace, user=invited).exists()
    assert WorkspaceMember.objects.filter(workspace=env.workspace).count() == 4
    invitation.refresh_from_db()
    assert invitation.status == "pending"  # DB holati o'zgarmaydi, faqat "effective"
    assert invitation.accepted_by_id is None

    # Ro'yxatda esa u `expired` bo'lib ko'rinadi.
    listing = env.owner_client.get(ws_url(env.workspace.id, "invitations/")).json()
    row = next(r for r in listing["results"] if r["id"] == str(invitation.id))
    assert row["status"] == "expired"


def test_invitation_decline(env):
    url = ws_url(env.workspace.id, "invitations/")
    created = env.owner_client.post(url, {"email": "dec@x.io", "role": "member"}, format="json")
    token = Invitation.objects.get(pk=created.json()["id"]).token
    declined = client_for(make_user("dec@x.io")).post(
        "/api/v1/invitations/decline/", {"token": token}, format="json"
    )
    assert declined.status_code == 204
    assert Invitation.objects.get(pk=created.json()["id"]).status == "revoked"


# ------------------------------------------------------------- spaces


def test_space_create_and_visibility(env):
    url = ws_url(env.workspace.id, "spaces/")
    denied = env.member_client.post(url, {"name": "Eng"}, format="json")
    assert_error(denied, 403, "permission_denied")

    created = env.admin_client.post(
        url, {"name": "Private Ops", "is_private": True}, format="json"
    )
    assert created.status_code == 201, created.content
    space_id = created.json()["id"]
    # Status to'plami endi yaratilmaydi — `spaces/{id}/status-set/` yo'q (§9).
    assert env.admin_client.get(f"/api/v1/spaces/{space_id}/status-set/").status_code == 404

    # duplicate name (CI) -> 409
    dup = env.admin_client.post(url, {"name": "private ops"}, format="json")
    assert_error(dup, 409, "conflict")

    # guests never see private spaces
    listing = env.guest_client.get(url)
    names = [s["name"] for s in listing.json()["results"]]
    assert "Private Ops" not in names
    detail = env.guest_client.get(f"/api/v1/spaces/{space_id}/")
    assert_error(detail, 404, "not_found")


def test_space_delete_requires_confirm_name(env):
    bad = env.admin_client.delete(
        f"/api/v1/spaces/{env.space.id}/", {"confirm_name": "x"}, format="json"
    )
    assert_error(bad, 400, "validation_error")
    ok = env.admin_client.delete(
        f"/api/v1/spaces/{env.space.id}/", {"confirm_name": "Jamoa bo'limi"}, format="json"
    )
    assert ok.status_code == 204


# ------------------------------------------------------------- folders & lists


def test_folder_crud_and_detach(env):
    url = f"/api/v1/spaces/{env.space.id}/folders/"
    # 2026-08 siyosati: `folder.*` va `list.*` member'dan olib tashlandi —
    # struktura faqat admin+ (yoki o'z bo'limidagi PM) qo'lida.
    member_denied = env.member_client.post(url, {"name": "Nope"}, format="json")
    assert_error(member_denied, 403, "permission_denied")

    created = env.admin_client.post(url, {"name": "Q3"}, format="json")
    assert created.status_code == 201
    folder_id = created.json()["id"]

    dup = env.admin_client.post(url, {"name": "q3"}, format="json")
    assert_error(dup, 409, "conflict")

    # a list inside the folder
    inside = env.admin_client.post(
        f"/api/v1/spaces/{env.space.id}/lists/",
        {"name": "Sprint 24", "folder_id": folder_id},
        format="json",
    )
    assert inside.status_code == 201
    list_id = inside.json()["id"]

    # ikkala strategiya ham endi admin+ (`folder.delete` ham member'da yo'q)
    denied = env.member_client.delete(f"/api/v1/folders/{folder_id}/?strategy=cascade")
    assert_error(denied, 403, "permission_denied")
    denied_detach = env.member_client.delete(f"/api/v1/folders/{folder_id}/?strategy=detach")
    assert_error(denied_detach, 403, "permission_denied")

    # detach moves lists to the space root
    ok = env.admin_client.delete(f"/api/v1/folders/{folder_id}/?strategy=detach")
    assert ok.status_code == 204
    moved = TaskList.objects.get(pk=list_id)
    assert moved.folder_id is None
    assert moved.space_id == env.space.id


def test_folder_detail_read_and_rename(env):
    """`GET`/`PATCH folders/{id}/` — hech qanday test ularni chaqirmagan edi."""
    folders_url = f"/api/v1/spaces/{env.space.id}/folders/"
    folder = env.admin_client.post(folders_url, {"name": "Q4"}, format="json").json()
    detail = f"/api/v1/folders/{folder['id']}/"

    got = env.member_client.get(detail)
    assert got.status_code == 200, got.content
    body = got.json()
    assert body["name"] == "Q4"
    assert body["space_id"] == str(env.space.id)
    assert body["archived"] is False
    assert body["position"]

    # `folder.update` member'da yo'q (2026-08 siyosati).
    assert_error(env.member_client.patch(detail, {"name": "Yo'q"}, format="json"), 403,
                 "permission_denied")

    renamed = env.admin_client.patch(
        detail, {"name": "Q4 rejalar", "color": "#FF0000", "archived": True}, format="json"
    )
    assert renamed.status_code == 200, renamed.content
    assert renamed.json()["name"] == "Q4 rejalar"
    assert renamed.json()["color"] == "#FF0000"
    assert renamed.json()["archived"] is True

    # nom bo'lim ichida CI-unikal.
    env.admin_client.post(folders_url, {"name": "Q5"}, format="json")
    assert_error(env.admin_client.patch(detail, {"name": "q5"}, format="json"), 409, "conflict")
    # ...o'z nomini qaytadan yuborish esa 409 EMAS.
    assert env.admin_client.patch(detail, {"name": "q4 rejalar"}, format="json").status_code == 200

    # ish maydonidan tashqarida — 404, 403 emas.
    assert_error(env.outsider_client.get(detail), 404, "not_found")
    assert_error(env.outsider_client.patch(detail, {"name": "X"}, format="json"), 404, "not_found")


def test_list_detail_read(env):
    """`GET lists/{id}/` — bu ham hech qachon chaqirilmagan edi."""
    detail = f"/api/v1/lists/{env.list.id}/"
    got = env.member_client.get(detail)
    assert got.status_code == 200, got.content
    body = got.json()
    assert body["id"] == str(env.list.id)
    assert body["name"] == "Boshlash"
    assert body["space_id"] == str(env.space.id)
    assert body["folder_id"] is None
    assert body["task_count"] == 0
    assert body["open_task_count"] == 0
    assert body["default_view"] == "list"

    assert_error(env.outsider_client.get(detail), 404, "not_found")

    # yopiq bo'limdagi ro'yxat mehmon uchun mavjud emas (§1.7).
    private = services.create_space(env.workspace, env.owner, name="Yopiq", is_private=True)
    hidden = TaskList.objects.create(
        space=private, name="Yashirin", position="n", created_by=env.owner
    )
    assert_error(env.guest_client.get(f"/api/v1/lists/{hidden.id}/"), 404, "not_found")
    assert env.admin_client.get(f"/api/v1/lists/{hidden.id}/").status_code == 200


def test_list_create_validation_and_scope_conflict(env):
    url = f"/api/v1/spaces/{env.space.id}/lists/"
    # 403 tekshiruvi validatsiyadan oldin: member uchun `list.create` yo'q.
    member_denied = env.member_client.post(url, {"name": "Nope"}, format="json")
    assert_error(member_denied, 403, "permission_denied")

    dup = env.admin_client.post(url, {"name": "boshlash"}, format="json")
    assert_error(dup, 409, "conflict")

    other_space = env.admin_client.post(
        ws_url(env.workspace.id, "spaces/"), {"name": "Other"}, format="json"
    ).json()
    foreign_folder = env.admin_client.post(
        f"/api/v1/spaces/{other_space['id']}/folders/", {"name": "Elsewhere"}, format="json"
    ).json()
    bad = env.admin_client.post(
        url, {"name": "New List", "folder_id": foreign_folder["id"]}, format="json"
    )
    assert_error(bad, 400, "validation_error")

    patch_folder = env.admin_client.patch(
        f"/api/v1/lists/{env.list.id}/", {"folder_id": None}, format="json"
    )
    assert_error(patch_folder, 400, "validation_error")


def test_list_move_reorder_and_reparent(env):
    """`list.move` endi admin+ — setup va harakatlar `admin_client` bilan."""
    space_lists = f"/api/v1/spaces/{env.space.id}/lists/"
    b = env.admin_client.post(space_lists, {"name": "B"}, format="json").json()
    c = env.admin_client.post(space_lists, {"name": "C"}, format="json").json()
    a = env.list  # position "n"

    # move C between A and B
    moved = env.admin_client.patch(
        f"/api/v1/lists/{c['id']}/move/",
        {"folder_id": None, "before_id": str(a.id), "after_id": b["id"]},
        format="json",
    )
    assert moved.status_code == 200, moved.content
    listing = env.member_client.get(space_lists).json()["results"]
    assert [x["name"] for x in listing] == ["Boshlash", "C", "B"]

    # sending space_id is a validation error (OQ-2 ruling)
    bad = env.admin_client.patch(
        f"/api/v1/lists/{c['id']}/move/",
        {"folder_id": None, "space_id": str(env.space.id)},
        format="json",
    )
    assert_error(bad, 400, "validation_error")

    # stale neighbours -> 409 position_conflict
    folder = env.admin_client.post(
        f"/api/v1/spaces/{env.space.id}/folders/", {"name": "F"}, format="json"
    ).json()
    stale = env.admin_client.patch(
        f"/api/v1/lists/{c['id']}/move/",
        {"folder_id": folder["id"], "before_id": b["id"]},  # b is not in the folder
        format="json",
    )
    assert_error(stale, 409, "position_conflict")

    # re-parent into the folder
    reparented = env.admin_client.patch(
        f"/api/v1/lists/{c['id']}/move/", {"folder_id": folder["id"]}, format="json"
    )
    assert reparented.status_code == 200
    assert reparented.json()["folder_id"] == folder["id"]


# ------------------------------------------------- status sets (OLIB TASHLANDI)
#
# Bu yerda uchta test turardi: `test_space_status_set_put_with_mapping`,
# `test_status_set_invariants` va `test_list_status_set_override_and_delete`.
# Ular BUTUNLAY YO'Q BO'LGAN xatti-harakatni tekshirardi — sozlanadigan status
# to'plami, `status_mapping` bilan qayta yo'naltirish va ro'yxat darajasidagi
# override. Model olib tashlangach, ularni "yangi modelga moslashtirish" mumkin
# emas: moslashtirilgan versiya boshqa narsani tekshirgan bo'lardi. Shuning
# uchun ular o'chirildi va o'rniga endpointlarning haqiqatan yo'qolgani
# qulflanadi (pastda). Yangi status xatti-harakati `apps/tasks/tests.py` da
# sinaladi (`test_create_task_rejects_an_unknown_status_code`,
# `test_patch_status_round_trip_sets_and_clears_completed_at`,
# `test_group_by_status_shape`).


def test_status_set_endpoints_are_gone(env):
    """§9 dagi beshta endpoint 404 bo'lishi SHART.

    Marshrut butunlay olib tashlangani uchun har qanday metod 404 beradi —
    405 emas (405 marshrut hali borligini bildirardi).
    """
    space_url = f"/api/v1/spaces/{env.space.id}/status-set/"
    list_url = f"/api/v1/lists/{env.list.id}/status-set/"
    payload = {"statuses": []}

    assert env.admin_client.get(space_url).status_code == 404
    assert env.admin_client.put(space_url, payload, format="json").status_code == 404
    assert env.admin_client.get(list_url).status_code == 404
    assert env.admin_client.put(list_url, payload, format="json").status_code == 404
    assert env.admin_client.delete(list_url).status_code == 404


# ------------------------------------------------------------- search


def search_url(env, query=""):
    return ws_url(env.workspace.id, f"search/{query}")


def _make_task(task_list, title, actor):
    from apps.tasks import services as task_services

    return task_services.create_task(task_list, {"title": title}, actor)


@pytest.fixture
def haystack(env):
    """Har bir turdan bittadan "Kompas" + mehmonga ko'rinmaydigan juftliklari."""
    from types import SimpleNamespace

    space = services.create_space(env.workspace, env.admin, name="Kompas bo'limi")
    folder = Folder.objects.create(
        space=space, name="Kompas jildi", position="n", created_by=env.admin
    )
    task_list = TaskList.objects.create(
        space=space, folder=folder, name="Kompas ro'yxati", position="n", created_by=env.admin
    )
    task = _make_task(task_list, "Kompas vazifasi", env.admin)

    private = services.create_space(
        env.workspace, env.admin, name="Kompas yashirin bo'limi", is_private=True
    )
    private_list = TaskList.objects.create(
        space=private, name="Kompas yashirin ro'yxati", position="n", created_by=env.admin
    )
    private_task = _make_task(private_list, "Kompas yashirin vazifasi", env.admin)

    # Mehmon OCHIQ bo'limning a'zosi: `visible_spaces_q` OR-ga `space_members`
    # JOIN'ini qo'shadi, ya'ni `distinct()` bo'lmasa bo'lim natijalarda bir
    # necha marta chiqib, `count` ni ham shishirardi.
    SpaceMember.objects.create(space=space, user=env.guest, access="contributor")

    return SimpleNamespace(
        space=space,
        folder=folder,
        task_list=task_list,
        task=task,
        private=private,
        private_list=private_list,
        private_task=private_task,
    )


def test_search_validates_q(env):
    assert_error(env.member_client.get(search_url(env)), 400, "validation_error")
    assert_error(env.member_client.get(search_url(env, "?q=%20%20")), 400, "validation_error")

    # 1 harf -> bo'sh natija, xato emas (contract section 13).
    one_char = env.member_client.get(search_url(env, "?q=x"))
    assert one_char.status_code == 200
    assert one_char.json() == {"count": 0, "next": None, "previous": None, "results": []}


def test_search_returns_every_type_in_the_documented_shape(env, haystack):
    response = env.member_client.get(search_url(env, "?q=Kompas"))
    assert response.status_code == 200, response.content
    body = response.json()
    assert set(body.keys()) == {"count", "next", "previous", "results"}
    # A'zo (mehmon emas) yopiq bo'limni ham ko'radi: 2 vazifa + 2 ro'yxat +
    # 1 jild + 2 bo'lim.
    assert body["count"] == 7
    assert len(body["results"]) == 7
    assert body["next"] is None and body["previous"] is None

    # Turlar tartibi qat'iy: vazifa -> ro'yxat -> jild -> bo'lim.
    assert [r["type"] for r in body["results"]] == [
        "task", "task", "list", "list", "folder", "space", "space",
    ]
    for row in body["results"]:
        assert set(row.keys()) == {"type", "item"}
        assert "id" in row["item"]

    by_type = {}
    for row in body["results"]:
        by_type.setdefault(row["type"], []).append(row["item"])
    # To'liq obyektlar qaytadi, id emas.
    assert by_type["task"][0]["assignees"] == []
    assert by_type["task"][0]["status"] == "todo"
    assert {t["title"] for t in by_type["task"]} == {
        "Kompas vazifasi", "Kompas yashirin vazifasi"
    }
    assert by_type["folder"][0]["space_id"] == str(haystack.space.id)
    assert by_type["space"][0]["id"] == str(haystack.space.id)
    assert by_type["list"][0]["task_count"] == 1

    # Arxivlangan narsalar hech qachon chiqmaydi.
    haystack.folder.archived = True
    haystack.folder.save(update_fields=["archived"])
    after = env.member_client.get(search_url(env, "?q=Kompas")).json()
    assert after["count"] == 6
    assert "folder" not in {r["type"] for r in after["results"]}


def test_search_paginates_without_duplicating_or_dropping_rows(env, haystack):
    seen, page, guard = [], 1, 0
    while True:
        guard += 1
        assert guard < 10
        body = env.member_client.get(
            search_url(env, f"?q=Kompas&page_size=2&page={page}")
        ).json()
        assert body["count"] == 7  # `count` har sahifada bir xil
        assert len(body["results"]) <= 2
        seen.extend((r["type"], r["item"]["id"]) for r in body["results"])
        if body["next"] is None:
            break
        page += 1

    assert page == 4
    assert len(seen) == 7
    assert len(set(seen)) == 7  # turlar chegarasida na dublikat, na yo'qolish

    # Chegaradan tashqaridagi sahifa -> 404 (DRF standarti), 500 emas.
    assert env.member_client.get(
        search_url(env, "?q=Kompas&page_size=2&page=9")
    ).status_code == 404
    assert_error(
        env.member_client.get(search_url(env, "?q=Kompas&page_size=999")),
        400,
        "validation_error",
    )


def test_search_never_leaks_private_space_content_to_a_guest(env, haystack):
    """Eng muhim invariant: mehmon yopiq bo'limning NOMINI ham ko'rmaydi."""
    body = env.guest_client.get(search_url(env, "?q=Kompas")).json()

    # `count` filtrlashdan KEYIN hisoblanadi (section 13) -- 6 emas, 4.
    assert body["count"] == 4
    assert len(body["results"]) == 4

    ids = {r["item"]["id"] for r in body["results"]}
    assert str(haystack.private.id) not in ids
    assert str(haystack.private_list.id) not in ids
    assert str(haystack.private_task.id) not in ids

    blob = str(body)
    assert "yashirin" not in blob

    # `space_members` JOIN'i ochiq bo'limni takrorlab yubormaydi.
    spaces = [r for r in body["results"] if r["type"] == "space"]
    assert len(spaces) == 1
    assert spaces[0]["item"]["id"] == str(haystack.space.id)

    # Ish maydonidan tashqaridagi odam uchun esa endpoint umuman yo'q.
    assert_error(env.outsider_client.get(search_url(env, "?q=Kompas")), 404, "not_found")


def test_search_query_count_does_not_grow_with_the_result_set(
    env, haystack, django_assert_max_num_queries
):
    """N+1 qaytib kelmasin.

    Ilgari har bir vazifa ~4 ta qo'shimcha so'rov keltirardi (biriktirilganlar,
    teglar, kuzatuvchilar prefetch qilinmagan) VA butun natija to'plami
    sahifalashdan OLDIN Python ro'yxatiga aylantirilardi: 5 ta moslikda 26,
    50 tasida 206 so'rov. Endi son natija hajmidan mustaqil.
    """
    for i in range(40):
        _make_task(haystack.task_list, f"Kompas ko'p {i}", env.admin)

    with django_assert_max_num_queries(16):
        big = env.member_client.get(search_url(env, "?q=Kompas&page_size=50"))
    assert big.status_code == 200, big.content
    assert big.json()["count"] == 47
    assert len(big.json()["results"]) == 47

    # Bitta sahifa ham xuddi shu byudjetda.
    with django_assert_max_num_queries(16):
        small = env.member_client.get(search_url(env, "?q=Kompas&page_size=5"))
    assert small.json()["count"] == 47
    assert len(small.json()["results"]) == 5


def test_search_still_matches_descriptions_and_the_bootstrap_list(env):
    from apps.tasks.models import Task

    found = env.member_client.get(search_url(env, "?q=Boshlash"))
    assert found.status_code == 200
    assert {item["type"] for item in found.json()["results"]} == {"list"}

    Task.objects.create(
        list=env.list,
        status=TaskStatus.TODO,
        title="Sarlavhada yo'q",
        description_html="<p>Ichida esa parolniyangilash bor</p>",
        position="n",
        created_by=env.member,
        updated_by=env.member,
    )
    by_body = env.member_client.get(search_url(env, "?q=parolniyangilash")).json()
    assert by_body["count"] == 1
    assert by_body["results"][0]["type"] == "task"
    assert by_body["results"][0]["item"]["title"] == "Sarlavhada yo'q"
