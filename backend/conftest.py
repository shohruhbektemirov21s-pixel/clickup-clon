import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.serializers import token_pair_for
from apps.core.enums import WorkspaceRole
from apps.workspaces.models import WorkspaceMember
from apps.workspaces.services import bootstrap_workspace

PASSWORD = "S3cure!passw0rd"


def make_user(email, full_name=""):
    return User.objects.create_user(email=email, password=PASSWORD, full_name=full_name)


def client_for(user):
    client = APIClient()
    tokens = token_pair_for(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture(autouse=True, scope="session")
def _celery_always_eager():
    """Testlar HECH QACHON broker'ga murojaat qilmaydi.

    `CELERY_TASK_ALWAYS_EAGER` standarti `REDIS_URL` bo'shligiga bog'liq
    (`config/settings.py`), ya'ni Redis o'rnatilgan mashinada u o'chiq
    bo'lardi va test to'plami mavjud bo'lmagan worker'ni kutib qotib
    qolardi. Bu yerda ilova obyektining o'zida majburlaymiz — Django
    sozlamasini keyin o'zgartirish Celery konfiguratsiyasiga o'tmaydi.
    """
    from config.celery import app as celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield


@pytest.fixture(autouse=True)
def _reset_permission_cache():
    """docs/DESIGN_PERMISSIONS.md R3 — permission cache never leaks across tests."""
    from django.core.cache import cache

    from apps.core.access import clear_permission_cache

    cache.clear()
    clear_permission_cache()
    yield
    cache.clear()
    clear_permission_cache()


@pytest.fixture
def api():
    return APIClient()


class Env:
    """A bootstrapped workspace with one user per role."""

    def __init__(self):
        self.owner = make_user("owner@test.dev", "Owner One")
        self.admin = make_user("admin@test.dev", "Admin Two")
        self.member = make_user("member@test.dev", "Member Three")
        self.guest = make_user("guest@test.dev", "Guest Four")
        self.outsider = make_user("outsider@test.dev", "Out Sider")

        self.workspace = bootstrap_workspace(self.owner, name="Acme Inc.")
        for user, role in [
            (self.admin, WorkspaceRole.ADMIN),
            (self.member, WorkspaceRole.MEMBER),
            (self.guest, WorkspaceRole.GUEST),
        ]:
            WorkspaceMember.objects.create(workspace=self.workspace, user=user, role=role)

        self.space = self.workspace.spaces.get(name="Jamoa bo'limi")
        self.list = self.space.lists.get(name="Boshlash")

        self.owner_client = client_for(self.owner)
        self.admin_client = client_for(self.admin)
        self.member_client = client_for(self.member)
        self.guest_client = client_for(self.guest)
        self.outsider_client = client_for(self.outsider)


@pytest.fixture
def env(db):
    return Env()


def assert_error(response, status_code, code):
    assert response.status_code == status_code, response.content
    body = response.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) >= {"code", "message", "details"}
    assert body["error"]["code"] == code
    return body["error"]
