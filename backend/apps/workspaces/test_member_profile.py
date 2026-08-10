"""A'zo profili va ish maydoni faoliyat tasmasi — API_CONTRACT.md §4.1 / §10.8.

Bu faylning asosiy mavzusi — **sizib chiqish yo'qligi**: profil raqamlari va
faoliyat tasmasi har doim CHAQIRUVCHINING ko'rish doirasida qoladi, a'zo
bo'lmagan `user_id` esa 404 beradi (403 emas — mavjudlik oshkor qilinmaydi).
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.access import bump_permissions_version
from apps.core.enums import SpaceAccess, StatusType
from apps.tasks.models import Task
from apps.workspaces import services
from apps.workspaces.models import RolePermission, SpaceMember, TaskList
from conftest import assert_error, client_for, make_user

pytestmark = pytest.mark.django_db


def profile_url(workspace_id, user_id):
    return f"/api/v1/workspaces/{workspace_id}/members/{user_id}/profile/"


def activity_url(workspace_id):
    return f"/api/v1/workspaces/{workspace_id}/activity/"


def _grant(env, role, code):
    """Matritsaga bitta kod qo'shadi va versiyani oshiradi (R3)."""
    RolePermission.objects.update_or_create(
        workspace=env.workspace,
        role=role,
        permission=code,
        defaults={"allowed": True},
    )
    bump_permissions_version(env.workspace)


def _make_task(env, task_list, title, *, assignees=(), due_date=None, actor=None):
    from apps.tasks import services as task_services

    return task_services.create_task(
        task_list,
        {
            "title": title,
            "assignee_ids": [str(u.id) for u in assignees],
            "due_date": due_date,
        },
        actor or env.owner,
    )


@pytest.fixture
def private_space(env):
    """Yopiq bo'lim + ro'yxat. Mehmon uni ko'rmaydi (legacy §1.7 qoidasi)."""
    space = services.create_space(
        env.workspace, env.owner, name="Yopiq loyiha", is_private=True
    )
    task_list = TaskList.objects.create(
        space=space, name="Yopiq ro'yxat", position="n", created_by=env.owner
    )
    return space, task_list


# ------------------------------------------------------------------ happy path


def test_owner_sees_own_profile(env):
    _make_task(env, env.list, "O'zimga vazifa", assignees=[env.owner])
    response = env.owner_client.get(profile_url(env.workspace.id, env.owner.id))
    assert response.status_code == 200, response.content
    body = response.json()

    assert set(body.keys()) == {
        "user",
        "role",
        "joined_at",
        "last_active_at",
        "stats",
        "spaces",
    }
    assert body["user"]["email"] == env.owner.email
    # `profession` — profil yorlig'i, UserSummary orqali keladi.
    assert "profession" in body["user"]
    assert body["role"] == "owner"
    assert body["joined_at"].endswith("Z")
    assert set(body["stats"].keys()) == {
        "open_tasks",
        "overdue_tasks",
        "due_today",
        "completed_tasks",
        "created_tasks",
        "comments",
    }
    assert body["stats"]["open_tasks"] == 1
    assert body["stats"]["created_tasks"] == 1
    assert body["spaces"][0]["name"] == "Jamoa bo'limi"
    assert body["spaces"][0]["open_tasks"] == 1


def test_member_sees_another_members_profile_with_buckets(env):
    now = timezone.now()
    _make_task(env, env.list, "Muddati o'tgan", assignees=[env.admin],
               due_date=now - timedelta(days=2))
    _make_task(env, env.list, "Bugun kechqurun", assignees=[env.admin],
               due_date=now + timedelta(hours=2))
    _make_task(env, env.list, "Muddatsiz", assignees=[env.admin])

    response = env.member_client.get(profile_url(env.workspace.id, env.admin.id))
    assert response.status_code == 200, response.content
    stats = response.json()["stats"]
    assert stats["open_tasks"] == 3
    assert stats["overdue_tasks"] == 1
    # `due_today` va `overdue_tasks` kesishmaydi — bosh sahifadagi guruhlash
    # bilan bir xil qoida.
    assert stats["due_today"] == 1
    assert response.json()["role"] == "admin"


def test_completed_and_comment_counters(env):
    task = _make_task(env, env.list, "Yopiladigan", assignees=[env.member])
    closed = env.status_set.statuses.get(type=StatusType.CLOSED)
    comment = env.member_client.post(
        f"/api/v1/tasks/{task.id}/comments/",
        {"body_html": "<p>Bajarildi</p>", "body_json": {"type": "doc"}},
        format="json",
    )
    assert comment.status_code == 201, comment.content
    patched = env.member_client.patch(
        f"/api/v1/tasks/{task.id}/", {"status_id": str(closed.id)}, format="json"
    )
    assert patched.status_code == 200, patched.content

    body = env.owner_client.get(profile_url(env.workspace.id, env.member.id)).json()
    assert body["stats"]["completed_tasks"] == 1
    assert body["stats"]["open_tasks"] == 0
    assert body["stats"]["comments"] == 1


# ------------------------------------------------------------------- 404 rules


def test_non_member_user_id_is_404(env):
    stranger = make_user("stranger@test.dev", "Stranger")
    response = env.owner_client.get(profile_url(env.workspace.id, stranger.id))
    assert_error(response, 404, "not_found")


def test_member_of_another_workspace_is_404(env):
    other_owner = make_user("other-owner@test.dev", "Other Owner")
    services.bootstrap_workspace(other_owner, name="Boshqa maydon")
    response = env.owner_client.get(profile_url(env.workspace.id, other_owner.id))
    assert_error(response, 404, "not_found")


def test_outsider_gets_404_not_403(env):
    response = env.outsider_client.get(profile_url(env.workspace.id, env.owner.id))
    assert_error(response, 404, "not_found")


def test_guest_reads_profiles_by_default(env):
    """2026-08 (katalog v4): `member.read` endi guest'da ham default."""
    response = env.guest_client.get(profile_url(env.workspace.id, env.owner.id))
    assert response.status_code == 200, response.content


def test_guest_without_member_read_is_403(env):
    """Matritsadan `member.read` olib tashlansa — profil yana 403 bo'ladi."""
    RolePermission.objects.update_or_create(
        workspace=env.workspace,
        role="guest",
        permission="member.read",
        defaults={"allowed": False},
    )
    bump_permissions_version(env.workspace)

    response = env.guest_client.get(profile_url(env.workspace.id, env.owner.id))
    assert_error(response, 403, "permission_denied")


# ----------------------------------------------------- private-space isolation


def test_guest_stats_exclude_private_space_tasks(env, private_space):
    """Mehmon yopiq bo'limdagi vazifalarni statistikada KO'RMAYDI."""
    space, private_list = private_space
    _make_task(env, private_list, "Yopiq ish", assignees=[env.admin])
    _make_task(env, env.list, "Ochiq ish", assignees=[env.admin])

    # Mehmonga faqat rosterni o'qish huquqini beramiz — bo'lim ko'rinishi
    # o'zgarmaydi (§1.7: guest × private → 404).
    _grant(env, "guest", "member.read")

    guest_body = env.guest_client.get(
        profile_url(env.workspace.id, env.admin.id)
    ).json()
    assert guest_body["stats"]["open_tasks"] == 1
    assert [s["name"] for s in guest_body["spaces"]] == ["Jamoa bo'limi"]

    owner_body = env.owner_client.get(
        profile_url(env.workspace.id, env.admin.id)
    ).json()
    assert owner_body["stats"]["open_tasks"] == 2
    assert {s["name"] for s in owner_body["spaces"]} == {
        "Jamoa bo'limi",
        "Yopiq loyiha",
    }


def test_guest_with_space_membership_sees_that_private_space(env, private_space):
    space, private_list = private_space
    _make_task(env, private_list, "Yopiq ish", assignees=[env.admin])
    _grant(env, "guest", "member.read")
    SpaceMember.objects.create(
        space=space, user=env.guest, access=SpaceAccess.VIEWER
    )

    body = env.guest_client.get(profile_url(env.workspace.id, env.admin.id)).json()
    assert body["stats"]["open_tasks"] == 1
    assert {s["name"] for s in body["spaces"]} == {"Jamoa bo'limi", "Yopiq loyiha"}


# ------------------------------------------------------------------- N+1 guard


def test_profile_query_count_is_bounded(env, private_space, django_assert_max_num_queries):
    """A'zolar/bo'limlar soni oshsa ham so'rovlar soni o'smaydi (agregatlar)."""
    space, private_list = private_space
    for i in range(6):
        services.create_space(env.workspace, env.owner, name=f"Bo'lim {i}")
    for i in range(6):
        _make_task(env, env.list, f"Vazifa {i}", assignees=[env.admin])
        _make_task(env, private_list, f"Yopiq vazifa {i}", assignees=[env.admin])

    url = profile_url(env.workspace.id, env.admin.id)
    env.owner_client.get(url)  # ruxsat keshini isitamiz
    with django_assert_max_num_queries(10):
        response = env.owner_client.get(url)
    assert response.status_code == 200
    assert response.json()["stats"]["open_tasks"] == 12


# ------------------------------------------------------------ activity feed


def test_activity_feed_shape_and_actor_filter(env):
    task = _make_task(env, env.list, "Tasma uchun", assignees=[env.member],
                      actor=env.owner)
    env.member_client.patch(
        f"/api/v1/tasks/{task.id}/", {"title": "Nomi o'zgardi"}, format="json"
    )

    response = env.owner_client.get(activity_url(env.workspace.id))
    assert response.status_code == 200, response.content
    body = response.json()
    assert set(body.keys()) == {"count", "next", "previous", "results"}
    row = body["results"][0]
    assert set(row.keys()) == {
        "id",
        "verb",
        "actor",
        "task",
        "from_value",
        "to_value",
        "created_at",
    }
    assert set(row["task"].keys()) == {"id", "title", "list_id", "list_name"}
    assert row["task"]["list_name"] == env.list.name
    # Yangisidan eskisiga.
    assert row["verb"] == "renamed"

    filtered = env.owner_client.get(
        activity_url(env.workspace.id), {"actor": str(env.member.id)}
    ).json()
    assert filtered["count"] >= 1
    assert {r["actor"]["id"] for r in filtered["results"]} == {str(env.member.id)}

    by_verb = env.owner_client.get(
        activity_url(env.workspace.id), {"verb": "created"}
    ).json()
    assert {r["verb"] for r in by_verb["results"]} == {"created"}


def test_activity_feed_rejects_bad_filters(env):
    assert_error(
        env.owner_client.get(activity_url(env.workspace.id), {"actor": "not-a-uuid"}),
        400,
        "validation_error",
    )
    assert_error(
        env.owner_client.get(activity_url(env.workspace.id), {"verb": "exploded"}),
        400,
        "validation_error",
    )


def test_activity_feed_hides_invisible_spaces(env, private_space):
    space, private_list = private_space
    _make_task(env, private_list, "Yopiq yozuv", actor=env.owner)
    _make_task(env, env.list, "Ochiq yozuv", actor=env.owner)

    guest = env.guest_client.get(activity_url(env.workspace.id)).json()
    titles = {r["task"]["title"] for r in guest["results"]}
    assert titles == {"Ochiq yozuv"}

    owner = env.owner_client.get(activity_url(env.workspace.id)).json()
    assert {r["task"]["title"] for r in owner["results"]} == {
        "Ochiq yozuv",
        "Yopiq yozuv",
    }


def test_activity_feed_hides_deleted_tasks(env):
    task = _make_task(env, env.list, "O'chiriladigan", actor=env.owner)
    deleted = env.owner_client.delete(f"/api/v1/tasks/{task.id}/")
    assert deleted.status_code == 204

    body = env.owner_client.get(activity_url(env.workspace.id)).json()
    assert all(r["task"]["id"] != str(task.id) for r in body["results"])


def test_activity_feed_outsider_is_404(env):
    assert_error(
        env.outsider_client.get(activity_url(env.workspace.id)), 404, "not_found"
    )


def test_activity_feed_query_count_is_bounded(env, django_assert_max_num_queries):
    """`select_related` — yozuvlar soni oshsa ham so'rov soni o'zgarmaydi."""
    for i in range(10):
        _make_task(env, env.list, f"Yozuv {i}", assignees=[env.member], actor=env.owner)

    url = activity_url(env.workspace.id)
    env.owner_client.get(url)  # kesh isitiladi
    with django_assert_max_num_queries(8):
        response = env.owner_client.get(url)
    assert response.status_code == 200
    assert response.json()["count"] >= 20
    assert Task.objects.count() == 10
