import pytest

from apps.workspaces.models import Workspace
from conftest import PASSWORD, assert_error, make_user

pytestmark = pytest.mark.django_db

REGISTER = "/api/v1/auth/register/"
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
    assert task_list.tasks.count() == 3


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
