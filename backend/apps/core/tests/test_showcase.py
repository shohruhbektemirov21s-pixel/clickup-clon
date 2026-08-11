"""`GET /api/v1/public/showcase/` — anonim landing ma'lumoti.

Bu API'dagi YAGONA autentifikatsiyasiz o'qish endpointi, shuning uchun testlar
asosan "nima chiqmasligi kerak" ga qaratilgan: sozlanmagan holatda hech
kimning yozuvi, sozlangan holatda ham email va yopiq bo'lim nomlari.
"""

import pytest
from django.urls import reverse

from apps.core.permissions import ALL_CODES

URL = "/api/v1/public/showcase/"


def make_task(env, title, position="n"):
    """`bootstrap_workspace` ro'yxatni bo'sh qoldiradi — vazifani o'zimiz qo'yamiz."""
    from apps.core.enums import TaskStatus
    from apps.tasks.models import Task

    return Task.objects.create(
        list=env.list,
        status=TaskStatus.TODO,
        title=title,
        position=position,
        created_by=env.owner,
    )


def test_url_is_registered():
    assert reverse("v1:public-showcase") == URL


@pytest.mark.django_db
def test_anonymous_can_read_it(api, settings):
    """Landing tizimga kirmagan mehmonga ko'rinadi — 401 bo'lmasligi shart."""
    settings.SHOWCASE_WORKSPACE_ID = ""
    response = api.get(URL)
    assert response.status_code == 200, response.content
    assert set(response.json().keys()) == {"stats", "matrix", "workspace"}


@pytest.mark.django_db
def test_stats_count_real_rows(env, api, settings):
    settings.SHOWCASE_WORKSPACE_ID = ""
    make_task(env, "Birinchi vazifa")
    stats = api.get(URL).json()["stats"]

    assert stats["permission_codes"] == len(ALL_CODES)
    assert stats["roles"] == 4
    assert stats["workspaces"] == 1
    assert stats["members"] == 5  # conftest.Env beshta foydalanuvchi yaratadi
    # `bootstrap_workspace` bitta bo'lim + tanishtiruvchi vazifalarni yaratadi.
    assert stats["spaces"] >= 1
    assert stats["tasks"] == 1


@pytest.mark.django_db
def test_workspace_is_null_when_not_configured(env, api, settings):
    """Default holat: hech kimning mazmuni anonim oshkor bo'lmaydi."""
    settings.SHOWCASE_WORKSPACE_ID = ""
    assert api.get(URL).json()["workspace"] is None


@pytest.mark.django_db
def test_unknown_or_malformed_id_does_not_500(env, api, settings):
    settings.SHOWCASE_WORKSPACE_ID = "not-a-uuid"
    response = api.get(URL)
    assert response.status_code == 200, response.content
    assert response.json()["workspace"] is None


@pytest.mark.django_db
def test_configured_workspace_exposes_its_content(env, api, settings):
    make_task(env, "Ko'rinadigan vazifa")
    settings.SHOWCASE_WORKSPACE_ID = str(env.workspace.id)
    block = api.get(URL).json()["workspace"]

    assert block is not None
    assert block["name"] == "Acme Inc."
    assert block["list_name"] == "Boshlash"
    assert [s["name"] for s in block["spaces"]] == ["Jamoa bo'limi"]
    assert [t["title"] for t in block["tasks"]] == ["Ko'rinadigan vazifa"]


@pytest.mark.django_db
def test_emails_are_never_exposed(env, api, settings):
    """Biriktirilganlar faqat bosh harf bilan chiqadi — email hech qachon."""
    from apps.tasks.models import TaskAssignee

    task = make_task(env, "Biriktirilgan vazifa")
    TaskAssignee.objects.create(task=task, user=env.member)

    settings.SHOWCASE_WORKSPACE_ID = str(env.workspace.id)
    raw = api.get(URL).content.decode()

    assert "member@test.dev" not in raw
    assert "@test.dev" not in raw
    people = api.get(URL).json()["workspace"]["tasks"]
    initials = [p["initials"] for task_row in people for p in task_row["people"]]
    assert "MT" in initials  # "Member Three"


@pytest.mark.django_db
def test_private_spaces_are_never_named(env, api, settings):
    """Yopiq bo'lim faqat sanaladi; nomi ham, vazifalari ham chiqmaydi."""
    from apps.workspaces.models import Space

    Space.objects.create(
        workspace=env.workspace,
        name="Maxfiy loyiha",
        is_private=True,
        position="z",
        created_by=env.owner,
    )

    settings.SHOWCASE_WORKSPACE_ID = str(env.workspace.id)
    raw = api.get(URL).content.decode()
    assert "Maxfiy loyiha" not in raw

    locked = [s for s in api.get(URL).json()["workspace"]["spaces"] if s["locked"]]
    assert len(locked) == 1
    assert locked[0]["count"] == 1


@pytest.mark.django_db
def test_owner_column_is_always_allowed(env, api, settings):
    """AD-3: owner qatori DB'da yo'q, shuning uchun u har doim True bo'lishi kerak."""
    settings.SHOWCASE_WORKSPACE_ID = ""
    matrix = api.get(URL).json()["matrix"]

    assert matrix["roles"][0] == "Egasi"
    assert matrix["rows"], "matritsa bo'sh bo'lmasligi kerak"
    for row in matrix["rows"]:
        assert row["allow"][0] is True, row["code"]
        assert len(row["allow"]) == len(matrix["roles"])


@pytest.mark.django_db
def test_only_get_is_allowed(api, settings):
    settings.SHOWCASE_WORKSPACE_ID = ""
    assert api.post(URL, {}, format="json").status_code == 405
