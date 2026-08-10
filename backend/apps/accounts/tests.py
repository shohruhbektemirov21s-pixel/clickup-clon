from datetime import timedelta
from unittest import mock

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.models import User
from apps.accounts.serializers import token_pair_for
from apps.core.enums import InvitationStatus, WorkspaceRole
from apps.workspaces.models import Invitation, Workspace, WorkspaceMember
from apps.workspaces.services import create_invitation
from conftest import PASSWORD, assert_error, make_user

pytestmark = pytest.mark.django_db

REGISTER = "/api/v1/auth/register/"
DEMO = "/api/v1/auth/demo/"
LOGIN = "/api/v1/auth/login/"
REFRESH = "/api/v1/auth/refresh/"
LOGOUT = "/api/v1/auth/logout/"
PASSWORD_CHANGE = "/api/v1/auth/password/change/"
ME = "/api/v1/me/"


def test_health_is_public(api):
    response = api.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_returns_tokens_and_user(api):
    response = api.post(
        REGISTER,
        {"email": "Maya@Acme.io", "password": PASSWORD, "full_name": "Maya Chen"},
        format="json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert set(body.keys()) == {"access", "refresh", "user"}
    assert body["user"]["email"] == "maya@acme.io"  # stored lowercase
    assert body["user"]["full_name"] == "Maya Chen"
    assert Workspace.objects.count() == 0  # no workspace_name -> no bootstrap


def test_register_with_workspace_name_bootstraps(api):
    response = api.post(
        REGISTER,
        {"email": "founder@acme.io", "password": PASSWORD, "workspace_name": "Acme"},
        format="json",
    )
    assert response.status_code == 201
    workspace = Workspace.objects.get(name="Acme")
    space = workspace.spaces.get()
    assert space.name == "Jamoa bo'limi"
    statuses = list(space.status_set.statuses.order_by("order"))
    assert [s.name for s in statuses] == ["BAJARILADI", "JARAYONDA", "BAJARILDI"]
    assert [s.type for s in statuses] == ["open", "active", "closed"]
    task_list = space.lists.get()
    assert task_list.name == "Boshlash"
    # Scaffolding only: a new account starts from zero, with no sample tasks.
    assert task_list.tasks.count() == 0


def test_register_duplicate_email_validation_error(api, db):
    make_user("dup@test.dev")
    response = api.post(
        REGISTER, {"email": "DUP@test.dev", "password": PASSWORD}, format="json"
    )
    error = assert_error(response, 400, "validation_error")
    assert "email" in error["details"]


def test_login_and_wrong_password(api, db):
    make_user("login@test.dev")
    ok = api.post(LOGIN, {"email": "login@test.dev", "password": PASSWORD}, format="json")
    assert ok.status_code == 200
    assert set(ok.json().keys()) == {"access", "refresh", "user"}

    bad = api.post(LOGIN, {"email": "login@test.dev", "password": "wrong"}, format="json")
    assert_error(bad, 401, "authentication_failed")


def test_refresh_rotates_and_blacklists_old_token(api, db):
    make_user("rot@test.dev")
    tokens = api.post(LOGIN, {"email": "rot@test.dev", "password": PASSWORD}, format="json").json()
    first = api.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")
    assert first.status_code == 200
    body = first.json()
    assert "access" in body and "refresh" in body
    assert body["refresh"] != tokens["refresh"]

    replay = api.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")
    assert_error(replay, 401, "token_not_valid")


def test_logout_blacklists_that_refresh_token(api, db):
    make_user("out@test.dev")
    tokens = api.post(LOGIN, {"email": "out@test.dev", "password": PASSWORD}, format="json").json()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    response = api.post(LOGOUT, {"refresh": tokens["refresh"]}, format="json")
    assert response.status_code == 204
    replay = api.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")
    assert_error(replay, 401, "token_not_valid")


def test_password_change(api, db):
    make_user("pw@test.dev")
    tokens = api.post(LOGIN, {"email": "pw@test.dev", "password": PASSWORD}, format="json").json()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    wrong = api.post(
        PASSWORD_CHANGE,
        {"current_password": "nope", "new_password": "N3w!passw0rd"},
        format="json",
    )
    error = assert_error(wrong, 400, "validation_error")
    assert "current_password" in error["details"]

    ok = api.post(
        PASSWORD_CHANGE,
        {"current_password": PASSWORD, "new_password": "N3w!passw0rd"},
        format="json",
    )
    assert ok.status_code == 200
    assert set(ok.json().keys()) == {"access", "refresh"}
    # every pre-existing refresh token is now blacklisted
    replay = api.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")
    assert_error(replay, 401, "token_not_valid")


def test_me_get_and_patch(env):
    response = env.member_client.get(ME)
    assert response.status_code == 200
    assert response.json()["email"] == "member@test.dev"

    patched = env.member_client.patch(
        ME, {"full_name": "New Name", "timezone": "Europe/Berlin"}, format="json"
    )
    assert patched.status_code == 200
    assert patched.json()["full_name"] == "New Name"
    assert patched.json()["timezone"] == "Europe/Berlin"

    bad = env.member_client.patch(ME, {"timezone": "Mars/Olympus"}, format="json")
    error = assert_error(bad, 400, "validation_error")
    assert "timezone" in error["details"]


def test_unauthenticated_requests_get_401_envelope(api):
    response = api.get(ME)
    assert_error(response, 401, "authentication_failed")


def test_garbage_token_is_token_not_valid(api):
    api.credentials(HTTP_AUTHORIZATION="Bearer not-a-jwt")
    response = api.get(ME)
    assert_error(response, 401, "token_not_valid")


# ---------------------------------------------------------------------------
# Kasb roli (profession) — profil ma'lumoti, RUXSAT ROLI EMAS
# ---------------------------------------------------------------------------


def test_register_stores_profession_and_it_grants_nothing(api, db):
    response = api.post(
        REGISTER,
        {
            "email": "pm@acme.io",
            "password": PASSWORD,
            "full_name": "Pardaboy Menejer",
            "profession": "project_manager",
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    assert response.json()["user"]["profession"] == "project_manager"

    user = User.objects.get(email="pm@acme.io")
    assert user.profession == "project_manager"
    # Kasb roli hech qanday vakolat bermaydi.
    assert user.is_staff is False
    assert user.is_superuser is False
    assert WorkspaceMember.objects.filter(user=user).count() == 0
    assert Workspace.objects.count() == 0


def test_profession_does_not_change_workspace_role(env):
    """`profession` va `WorkspaceRole` butunlay alohida o'qlar."""
    env.guest.profession = "project_manager"
    env.guest.save(update_fields=["profession"])

    membership = WorkspaceMember.objects.get(workspace=env.workspace, user=env.guest)
    assert membership.role == WorkspaceRole.GUEST

    # Mehmon PM "kasbi" bilan ham bo'lim yarata olmaydi (403).
    response = env.guest_client.post(
        f"/api/v1/workspaces/{env.workspace.id}/spaces/", {"name": "PM bo'limi"}, format="json"
    )
    assert response.status_code == 403, response.content


def test_profession_is_patchable_and_validated(env):
    ok = env.member_client.patch(ME, {"profession": "designer"}, format="json")
    assert ok.status_code == 200
    assert ok.json()["profession"] == "designer"

    blank = env.member_client.patch(ME, {"profession": ""}, format="json")
    assert blank.status_code == 200
    assert blank.json()["profession"] == ""

    bad = env.member_client.patch(ME, {"profession": "ceo"}, format="json")
    error = assert_error(bad, 400, "validation_error")
    assert "profession" in error["details"]


def test_register_rejects_unknown_profession(api, db):
    response = api.post(
        REGISTER,
        {"email": "x@acme.io", "password": PASSWORD, "profession": "hacker"},
        format="json",
    )
    error = assert_error(response, 400, "validation_error")
    assert "profession" in error["details"]
    assert User.objects.filter(email="x@acme.io").count() == 0


# ---------------------------------------------------------------------------
# Invite bilan ro'yxatdan o'tish — DESIGN_PERMISSIONS §D.8
# ---------------------------------------------------------------------------


def _invite(env, email="carlos@client.com", role=WorkspaceRole.GUEST):
    return create_invitation(env.workspace, env.owner, email=email, role=role)


def test_register_with_invite_token_joins_workspace(api, env):
    invitation = _invite(env, role=WorkspaceRole.MEMBER)
    workspaces_before = Workspace.objects.count()

    response = api.post(
        REGISTER,
        {
            "email": "Carlos@Client.com",  # CI mos keladi
            "password": PASSWORD,
            "full_name": "Carlos Vega",
            "profession": "developer",
            "invite_token": invitation.token,
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert set(body.keys()) == {"access", "refresh", "user", "workspace_id"}
    assert body["workspace_id"] == str(env.workspace.id)
    assert body["user"]["email"] == "carlos@client.com"
    assert body["user"]["profession"] == "developer"

    user = User.objects.get(email="carlos@client.com")
    membership = WorkspaceMember.objects.get(workspace=env.workspace, user=user)
    assert membership.role == WorkspaceRole.MEMBER  # rol AYNAN taklifdan
    assert membership.invited_by_id == env.owner.id
    assert user.is_staff is False and user.is_superuser is False

    invitation.refresh_from_db()
    assert invitation.status == InvitationStatus.ACCEPTED
    assert invitation.accepted_by_id == user.id
    assert invitation.accepted_at is not None

    env.workspace.refresh_from_db()
    assert env.workspace.member_count == WorkspaceMember.objects.filter(
        workspace=env.workspace
    ).count()
    # Yangi workspace bootstrap QILINMAYDI.
    assert Workspace.objects.count() == workspaces_before


def test_register_with_invite_ignores_client_supplied_role(api, env):
    """MUST-1: mijozning `role` maydoni hech qachon ishlatilmaydi."""
    invitation = _invite(env, role=WorkspaceRole.GUEST)
    response = api.post(
        REGISTER,
        {
            "email": "carlos@client.com",
            "password": PASSWORD,
            "full_name": "Carlos Vega",
            "invite_token": invitation.token,
            "role": "owner",
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    user = User.objects.get(email="carlos@client.com")
    membership = WorkspaceMember.objects.get(workspace=env.workspace, user=user)
    assert membership.role == WorkspaceRole.GUEST
    assert WorkspaceMember.objects.filter(
        workspace=env.workspace, role=WorkspaceRole.OWNER
    ).count() == 1


def test_register_with_invite_and_workspace_name_is_rejected(api, env):
    invitation = _invite(env)
    response = api.post(
        REGISTER,
        {
            "email": "carlos@client.com",
            "password": PASSWORD,
            "full_name": "Carlos Vega",
            "invite_token": invitation.token,
            "workspace_name": "O'zimniki",
        },
        format="json",
    )
    error = assert_error(response, 400, "validation_error")
    assert "workspace_name" in error["details"]
    assert User.objects.filter(email="carlos@client.com").count() == 0


def test_register_with_invite_email_mismatch(api, env):
    invitation = _invite(env)
    response = api.post(
        REGISTER,
        {
            "email": "someone.else@client.com",
            "password": PASSWORD,
            "full_name": "Carlos Vega",
            "invite_token": invitation.token,
        },
        format="json",
    )
    error = assert_error(response, 400, "validation_error")
    assert "email" in error["details"]
    assert User.objects.filter(email="someone.else@client.com").count() == 0
    invitation.refresh_from_db()
    assert invitation.status == InvitationStatus.PENDING


def test_register_with_invite_requires_full_name(api, env):
    invitation = _invite(env)
    response = api.post(
        REGISTER,
        {
            "email": "carlos@client.com",
            "password": PASSWORD,
            "full_name": "C",
            "invite_token": invitation.token,
        },
        format="json",
    )
    error = assert_error(response, 400, "validation_error")
    assert "full_name" in error["details"]
    assert User.objects.count() == 5  # env foydalanuvchilari o'zgarmadi


def test_register_with_expired_invite_is_404_and_atomic(api, env):
    invitation = _invite(env)
    Invitation.objects.filter(pk=invitation.pk).update(
        expires_at=timezone.now() - timedelta(days=1)
    )
    before = User.objects.count()

    response = api.post(
        REGISTER,
        {
            "email": "carlos@client.com",
            "password": PASSWORD,
            "full_name": "Carlos Vega",
            "invite_token": invitation.token,
        },
        format="json",
    )
    assert_error(response, 404, "not_found")
    assert User.objects.count() == before  # atomiklik: hech kim yaratilmadi


def test_register_with_unknown_invite_token_is_404(api, env):
    response = api.post(
        REGISTER,
        {
            "email": "carlos@client.com",
            "password": PASSWORD,
            "full_name": "Carlos Vega",
            "invite_token": "definitely-not-a-real-token",
        },
        format="json",
    )
    assert_error(response, 404, "not_found")
    assert User.objects.filter(email="carlos@client.com").count() == 0


def test_register_with_revoked_invite_is_409(api, env):
    """Bekor qilingan taklif → 409 (holat terminal, mavjudligi allaqachon ma'lum)."""
    invitation = _invite(env)
    invitation.status = InvitationStatus.REVOKED
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["status", "revoked_at", "updated_at"])

    response = api.post(
        REGISTER,
        {
            "email": "carlos@client.com",
            "password": PASSWORD,
            "full_name": "Carlos Vega",
            "invite_token": invitation.token,
        },
        format="json",
    )
    assert_error(response, 409, "conflict")
    assert User.objects.filter(email="carlos@client.com").count() == 0


def test_invite_token_cannot_be_used_twice(api, env):
    invitation = _invite(env, role=WorkspaceRole.MEMBER)
    payload = {
        "email": "carlos@client.com",
        "password": PASSWORD,
        "full_name": "Carlos Vega",
        "invite_token": invitation.token,
    }
    first = api.post(REGISTER, payload, format="json")
    assert first.status_code == 201, first.content
    assert WorkspaceMember.objects.filter(workspace=env.workspace).count() == 5

    # Aynan bir xil payload takrorlansa — email allaqachon band.
    replay = api.post(REGISTER, payload, format="json")
    error = assert_error(replay, 400, "validation_error")
    assert "email" in error["details"]

    # Boshqa email bilan bir xil token — taklif iste'mol qilingan → 409.
    second = api.post(
        REGISTER, {**payload, "email": "carlos+2@client.com"}, format="json"
    )
    assert_error(second, 409, "conflict")
    # Ikkinchi WorkspaceMember yaratilmadi.
    assert WorkspaceMember.objects.filter(workspace=env.workspace).count() == 5
    assert User.objects.filter(email="carlos+2@client.com").count() == 0


def test_consumed_invite_token_with_fresh_email_is_409(api, env):
    """Taklif iste'mol qilingan, lekin email hali band emas → toza 409."""
    invitation = _invite(env, role=WorkspaceRole.MEMBER)
    Invitation.objects.filter(pk=invitation.pk).update(status=InvitationStatus.ACCEPTED)

    response = api.post(
        REGISTER,
        {
            "email": "carlos@client.com",
            "password": PASSWORD,
            "full_name": "Carlos Vega",
            "invite_token": invitation.token,
        },
        format="json",
    )
    assert_error(response, 409, "conflict")
    assert User.objects.filter(email="carlos@client.com").count() == 0
    assert WorkspaceMember.objects.filter(workspace=env.workspace).count() == 4


def test_register_with_invite_weak_password_keeps_invitation_pending(api, env):
    invitation = _invite(env)
    response = api.post(
        REGISTER,
        {
            "email": "carlos@client.com",
            "password": "12345",
            "full_name": "Carlos Vega",
            "invite_token": invitation.token,
        },
        format="json",
    )
    error = assert_error(response, 400, "validation_error")
    assert "password" in error["details"]
    assert User.objects.filter(email="carlos@client.com").count() == 0
    invitation.refresh_from_db()
    assert invitation.status == InvitationStatus.PENDING
    assert WorkspaceMember.objects.filter(workspace=env.workspace).count() == 4


# ---------------------------------------------------------------------------
# Demo rejim — POST auth/demo/
# ---------------------------------------------------------------------------

DEMO_EMAIL = "demo@test.dev"


def _demo_rate(rate):
    """`SimpleRateThrottle.THROTTLE_RATES` import vaqtida bog'lanadi, shuning
    uchun `override_settings` yetarli emas — lug'atning o'zini patch qilamiz."""
    return mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"demo": rate})


def make_demo_user(email=None, full_name=""):
    """Demo tugmasi faqat `is_readonly` hisobga kiritadi (views.DemoLoginView)."""
    user = make_user(email or DEMO_EMAIL, full_name)
    user.is_readonly = True
    user.save(update_fields=["is_readonly"])
    return user


@override_settings(DEMO_MODE=True, DEMO_USER_EMAIL=DEMO_EMAIL)
def test_demo_login_returns_tokens(api, db):
    from apps.workspaces.services import bootstrap_workspace

    user = make_demo_user(DEMO_EMAIL, "Demo Foydalanuvchi")
    workspace = bootstrap_workspace(user, name="Demo ish maydoni")

    response = api.post(DEMO, {}, format="json")
    assert response.status_code == 200, response.content
    body = response.json()
    assert set(body.keys()) == {"access", "refresh", "user", "workspace_id"}
    assert body["user"]["email"] == DEMO_EMAIL
    assert body["workspace_id"] == str(workspace.id)

    # Qaytgan token haqiqatda ishlaydi.
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    me = api.get(ME)
    assert me.status_code == 200
    assert me.json()["id"] == str(user.id)


@override_settings(DEMO_MODE=False, DEMO_USER_EMAIL=DEMO_EMAIL)
def test_demo_login_disabled_is_404(api, db):
    make_demo_user()
    response = api.post(DEMO, {}, format="json")
    assert_error(response, 404, "not_found")


@override_settings(DEMO_MODE=True, DEMO_USER_EMAIL="nobody@test.dev")
def test_demo_login_missing_user_is_404(api, db):
    response = api.post(DEMO, {}, format="json")
    assert_error(response, 404, "not_found")


@override_settings(DEMO_MODE=True, DEMO_USER_EMAIL=DEMO_EMAIL)
def test_demo_login_refuses_staff_account(api, db):
    """Eskalatsiya bloki: demo tugmasi hech qachon staff hisob bermaydi."""
    user = make_demo_user()
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    assert_error(api.post(DEMO, {}, format="json"), 404, "not_found")

    user.is_staff = False
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    assert_error(api.post(DEMO, {}, format="json"), 404, "not_found")

    user.is_superuser = False
    user.save(update_fields=["is_superuser"])
    assert api.post(DEMO, {}, format="json").status_code == 200


@override_settings(DEMO_MODE=True, DEMO_USER_EMAIL=DEMO_EMAIL)
def test_demo_login_inactive_user_is_404(api, db):
    user = make_demo_user()
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert_error(api.post(DEMO, {}, format="json"), 404, "not_found")


def test_demo_login_is_throttled(api, db):
    make_demo_user()
    with override_settings(DEMO_MODE=True, DEMO_USER_EMAIL=DEMO_EMAIL), _demo_rate("2/hour"):
        assert api.post(DEMO, {}, format="json").status_code == 200
        assert api.post(DEMO, {}, format="json").status_code == 200
        assert_error(api.post(DEMO, {}, format="json"), 429, "throttled")


# ---------------------------------------------------------------------------
# Faqat o'qish hisobi (`is_readonly`) — demo tugmasi shunga kiritadi
# ---------------------------------------------------------------------------


def test_readonly_account_cannot_write_even_as_owner(env):
    """Bayroq rolidan ustun: egasi bo'lsa ham hech narsa o'zgartira olmaydi."""
    from apps.core.access import get_membership, has_perm

    env.owner.is_readonly = True
    env.owner.save(update_fields=["is_readonly"])
    membership = get_membership(env.owner, env.workspace.id)

    assert has_perm(membership, "task.read") is True
    for code in ("task.create", "task.delete", "space.create", "workspace.delete"):
        assert has_perm(membership, code) is False, code

    response = env.owner_client.post(
        f"/api/v1/lists/{env.list.id}/tasks/", {"title": "Yozmoqchi"}, format="json"
    )
    assert_error(response, 403, "permission_denied")


def test_readonly_flag_only_removes_permissions(env):
    """Rol bermagan o'qish huquqi bayroq tufayli QO'SHILIB qolmasin."""
    from apps.core.access import get_membership, has_perm, my_permissions

    env.guest.is_readonly = True
    env.guest.save(update_fields=["is_readonly"])
    membership = get_membership(env.guest, env.workspace.id)

    # Mehmon roli yopiq bo'limlarni ko'rmaydi — bayroq buni o'zgartirmaydi.
    assert has_perm(membership, "space.read_private") is False
    # `member.read` 2026-08 (katalog v4) dan guest'da HAM bor, shuning uchun
    # "rol bermagan o'qish" namunasi sifatida `invitation.read` olinadi.
    assert has_perm(membership, "invitation.read") is False  # guest'da yo'q
    assert has_perm(membership, "member.read") is True  # rol berdi, bayroq emas

    codes = my_permissions(membership)
    assert "task.read" in codes
    assert not any(c.endswith((".create", ".update", ".delete")) for c in codes)


def test_readonly_account_still_reads_tasks(env):
    env.member.is_readonly = True
    env.member.save(update_fields=["is_readonly"])
    response = env.member_client.get(f"/api/v1/workspaces/{env.workspace.id}/tasks/")
    assert response.status_code == 200


@override_settings(DEMO_MODE=True, DEMO_USER_EMAIL=DEMO_EMAIL)
def test_demo_login_refuses_a_writable_account(api, db):
    """Noto'g'ri sozlama ochiq eshikka aylanmasin: hisob readonly bo'lishi shart."""
    make_user(DEMO_EMAIL)  # is_readonly=False
    assert_error(api.post(DEMO, {}, format="json"), 404, "not_found")


def test_readonly_account_is_blocked_on_paths_outside_the_matrix(env):
    """Fail-closed qulf: ruxsat matritsasidan o'tmaydigan yozish yo'llari ham yopiq.

    AppSec auditi topgan holat — `is_readonly` faqat `has_perm` ichida
    tekshirilganda parolni almashtirish, workspace'dan chiqish, profilni
    tahrirlash va workspace yaratish ochiq qolardi. Demo paroli `seed_demo`
    da ochiq yozilgani uchun bu hisobni butunlay egallab olish demakdi.
    """
    env.member.is_readonly = True
    env.member.save(update_fields=["is_readonly"])
    client = env.member_client

    blocked = [
        ("post", PASSWORD_CHANGE, {"current_password": PASSWORD, "new_password": "N3w!passw0rd"}),
        ("post", f"/api/v1/workspaces/{env.workspace.id}/members/leave/", {}),
        ("patch", ME, {"full_name": "Buzg'unchi"}),
        ("post", "/api/v1/workspaces/", {"name": "Spam"}),
        ("post", "/api/v1/invitations/accept/", {"token": "x"}),
    ]
    for method, url, body in blocked:
        response = getattr(client, method)(url, body, format="json")
        assert response.status_code == 403, f"{method.upper()} {url} -> {response.status_code}"

    # O'qish buzilmaydi.
    assert client.get(ME).status_code == 200
    assert client.get(f"/api/v1/workspaces/{env.workspace.id}/tasks/").status_code == 200


def test_readonly_account_may_still_end_its_own_session(env):
    """Chiqish va token yangilash — sessiyaga tegishli, ma'lumotga emas."""
    env.member.is_readonly = True
    env.member.save(update_fields=["is_readonly"])
    tokens = token_pair_for(env.member)

    client = env.member_client
    assert client.post(LOGOUT, {"refresh": tokens["refresh"]}, format="json").status_code == 204
