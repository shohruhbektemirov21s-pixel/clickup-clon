import random

import pytest

from apps.core.ordering import _guard, evenly_spaced, midstring
from apps.tasks.models import Task, TaskActivity
from apps.workspaces.models import TaskList
from conftest import assert_error

pytestmark = pytest.mark.django_db


def tasks_url(list_id):
    return f"/api/v1/lists/{list_id}/tasks/"


def task_url(task_id, suffix=""):
    return f"/api/v1/tasks/{task_id}/{suffix}"


@pytest.fixture
def empty_list(env):
    """A fresh list with no sample tasks."""
    response = env.member_client.post(
        f"/api/v1/spaces/{env.space.id}/lists/", {"name": "Fresh"}, format="json"
    )
    return TaskList.objects.get(pk=response.json()["id"])


# ------------------------------------------------------------- ordering unit tests


def test_midstring_contract():
    assert midstring(None, None) == "n"
    for prev, nxt in [("a", "b"), ("a", "aV"), ("zz", None), (None, "n"), ("n", None)]:
        key = midstring(prev, nxt)
        if prev:
            assert prev < key
        if nxt:
            assert key < nxt
        assert not key.endswith("0")


def test_midstring_property_random():
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    rng = random.Random(42)
    keys = ["n"]
    for _ in range(2000):
        keys.sort()
        i = rng.randrange(len(keys) + 1)
        prev = keys[i - 1] if i > 0 else None
        nxt = keys[i] if i < len(keys) else None
        if prev is not None and nxt is not None and prev >= nxt:
            continue
        key = _guard(midstring(prev, nxt))
        assert (prev or "") < key
        assert nxt is None or key < nxt
        assert all(c in alphabet for c in key)
        keys.append(key)
    assert len(keys) == len(set(keys))


def test_evenly_spaced():
    for n in (1, 3, 60, 200):
        keys = evenly_spaced(n)
        assert len(keys) == n
        assert keys == sorted(keys)
        assert len(set(keys)) == n
        assert not any(k.endswith("0") for k in keys)


def test_repeated_same_gap_insertion_depth():
    low, high = "a", "b"
    key = None
    for _ in range(200):
        key = midstring(low, high)
        assert low < key < high
        high = key  # keep squeezing the same gap
    assert len(key) <= 64


# ------------------------------------------------------------- task CRUD


def test_create_task_defaults(env, empty_list):
    response = env.member_client.post(tasks_url(empty_list.id), {"title": "  First  "}, format="json")
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["title"] == "First"
    assert body["position"] == "n"
    assert body["priority"] == "none"
    default_status = env.statuses[0]
    assert body["status_id"] == str(default_status.id)
    assert body["is_deleted"] is False
    # creator is auto-watcher
    assert [w["id"] for w in body["watchers"]] == [str(env.member.id)]
    empty_list.refresh_from_db()
    assert empty_list.task_count == 1


def test_create_task_invalid_status_for_list(env, empty_list):
    other_space = env.admin_client.post(
        f"/api/v1/workspaces/{env.workspace.id}/spaces/", {"name": "Second"}, format="json"
    ).json()
    foreign_status = env.admin_client.get(
        f"/api/v1/spaces/{other_space['id']}/status-set/"
    ).json()["statuses"][0]
    response = env.member_client.post(
        tasks_url(empty_list.id),
        {"title": "X", "status_id": foreign_status["id"]},
        format="json",
    )
    assert_error(response, 400, "invalid_status_for_list")


def test_description_fields_must_come_together(env, empty_list):
    response = env.member_client.post(
        tasks_url(empty_list.id),
        {"title": "X", "description_html": "<p>hi</p>"},
        format="json",
    )
    assert_error(response, 400, "validation_error")

    ok = env.member_client.post(
        tasks_url(empty_list.id),
        {
            "title": "X",
            "description_html": "<p>hi</p><script>alert(1)</script>",
            "description_json": {"type": "doc", "content": []},
        },
        format="json",
    )
    assert ok.status_code == 201
    assert "<script>" not in ok.json()["description_html"]  # sanitised


def test_patch_task_assignees_and_tags(env, empty_list):
    tag = env.member_client.post(
        f"/api/v1/workspaces/{env.workspace.id}/tags/",
        {"name": "backend", "color": "#FD71AF"},
        format="json",
    ).json()
    task = env.member_client.post(tasks_url(empty_list.id), {"title": "X"}, format="json").json()

    patched = env.member_client.patch(
        task_url(task["id"]),
        {"assignee_ids": [str(env.guest.id)], "tag_ids": [tag["id"]], "priority": "urgent"},
        format="json",
    )
    assert patched.status_code == 200, patched.content
    body = patched.json()
    assert [a["id"] for a in body["assignees"]] == [str(env.guest.id)]
    assert [t["name"] for t in body["tags"]] == ["backend"]
    assert body["priority"] == "urgent"
    # assignment auto-adds the watcher
    assert str(env.guest.id) in [w["id"] for w in body["watchers"]]

    # non-member assignee -> 400
    bad = env.member_client.patch(
        task_url(task["id"]), {"assignee_ids": [str(env.outsider.id)]}, format="json"
    )
    assert_error(bad, 400, "validation_error")


def test_start_date_after_due_date(env, empty_list):
    response = env.member_client.post(
        tasks_url(empty_list.id),
        {
            "title": "X",
            "start_date": "2026-08-20T00:00:00Z",
            "due_date": "2026-08-10T00:00:00Z",
        },
        format="json",
    )
    assert_error(response, 400, "validation_error")


# ------------------------------------------------------------- move / reorder


def make_tasks(env, task_list, titles):
    out = []
    for title in titles:
        response = env.member_client.post(tasks_url(task_list.id), {"title": title}, format="json")
        out.append(response.json())
    return out


def test_move_reorder_within_column(env, empty_list):
    a, b, c = make_tasks(env, empty_list, ["A", "B", "C"])
    moved = env.member_client.patch(
        task_url(c["id"], "move/"),
        {
            "list_id": str(empty_list.id),
            "status_id": a["status_id"],
            "before_id": a["id"],
            "after_id": b["id"],
        },
        format="json",
    )
    assert moved.status_code == 200, moved.content
    assert moved.json()["rebalanced"] is False
    listing = env.member_client.get(tasks_url(empty_list.id)).json()["results"]
    assert [t["title"] for t in listing] == ["A", "C", "B"]
    # exactly one row changed position: A and B keep theirs
    assert listing[0]["position"] == a["position"]
    assert listing[2]["position"] == b["position"]


def test_move_cross_list_and_status(env, empty_list):
    (task,) = make_tasks(env, empty_list, ["Ship it"])
    closed = env.statuses[2]
    target = env.list  # Getting Started
    moved = env.member_client.patch(
        task_url(task["id"], "move/"),
        {"list_id": str(target.id), "status_id": str(closed.id)},
        format="json",
    )
    assert moved.status_code == 200, moved.content
    body = moved.json()
    assert body["list_id"] == str(target.id)
    assert body["status_id"] == str(closed.id)
    assert body["completed_at"] is not None  # closed-type sets completed_at

    empty_list.refresh_from_db()
    assert empty_list.task_count == 0
    target.refresh_from_db()
    assert target.task_count == 4


def test_move_missing_status_and_stale_neighbours(env, empty_list):
    a, b = make_tasks(env, empty_list, ["A", "B"])
    no_status = env.member_client.patch(
        task_url(a["id"], "move/"), {"list_id": str(empty_list.id)}, format="json"
    )
    assert_error(no_status, 400, "validation_error")

    # neighbour from a different column -> 409 position_conflict
    other_status = env.statuses[1]
    stale = env.member_client.patch(
        task_url(a["id"], "move/"),
        {
            "list_id": str(empty_list.id),
            "status_id": str(other_status.id),
            "before_id": b["id"],  # b is in the open column, not in-progress
        },
        format="json",
    )
    assert_error(stale, 409, "position_conflict")


def test_group_by_status_shape(env, empty_list):
    make_tasks(env, empty_list, ["A", "B"])
    response = env.member_client.get(tasks_url(empty_list.id) + "?group_by=status")
    assert response.status_code == 200
    body = response.json()
    assert body["group_by"] == "status"
    assert [g["status_id"] for g in body["groups"]] == [str(s.id) for s in env.statuses]
    counts = {g["status_id"]: g["count"] for g in body["groups"]}
    assert counts[str(env.statuses[0].id)] == 2
    assert counts[str(env.statuses[1].id)] == 0  # empty groups included


# ------------------------------------------------------------- delete / restore


def test_soft_delete_restore_and_include_deleted(env, empty_list):
    (task,) = make_tasks(env, empty_list, ["Doomed"])
    deleted = env.member_client.delete(task_url(task["id"]))
    assert deleted.status_code == 204

    gone = env.member_client.get(task_url(task["id"]))
    assert_error(gone, 404, "not_found")
    assert env.member_client.get(tasks_url(empty_list.id)).json()["count"] == 0

    # include_deleted is admin+ only
    denied = env.member_client.get(tasks_url(empty_list.id) + "?include_deleted=true")
    assert_error(denied, 403, "permission_denied")
    visible = env.admin_client.get(tasks_url(empty_list.id) + "?include_deleted=true")
    assert visible.json()["count"] == 1
    assert visible.json()["results"][0]["is_deleted"] is True

    # restore: only {"deleted_at": null}, admin+ only
    denied = env.member_client.patch(task_url(task["id"]), {"deleted_at": None}, format="json")
    assert_error(denied, 403, "permission_denied")
    bad_value = env.admin_client.patch(
        task_url(task["id"]), {"deleted_at": "2026-01-01T00:00:00Z"}, format="json"
    )
    assert_error(bad_value, 400, "validation_error")
    restored = env.admin_client.patch(task_url(task["id"]), {"deleted_at": None}, format="json")
    assert restored.status_code == 200, restored.content
    assert restored.json()["is_deleted"] is False


# ------------------------------------------------------------- watch


def test_watch_unwatch_idempotent(env, empty_list):
    (task,) = make_tasks(env, empty_list, ["W"])
    first = env.guest_client.post(task_url(task["id"], "watch/"))
    assert first.status_code == 201
    again = env.guest_client.post(task_url(task["id"], "watch/"))
    assert again.status_code == 200  # already watching
    gone = env.guest_client.delete(task_url(task["id"], "watch/"))
    assert gone.status_code == 204
    gone_again = env.guest_client.delete(task_url(task["id"], "watch/"))
    assert gone_again.status_code == 204


# ------------------------------------------------------------- roles


def test_guest_permissions(env, empty_list):
    denied = env.guest_client.post(tasks_url(empty_list.id), {"title": "no"}, format="json")
    assert_error(denied, 403, "permission_denied")

    a, b = make_tasks(env, empty_list, ["A", "B"])
    not_assigned = env.guest_client.patch(task_url(a["id"]), {"title": "no"}, format="json")
    assert_error(not_assigned, 403, "permission_denied")

    env.member_client.patch(
        task_url(a["id"]), {"assignee_ids": [str(env.guest.id)]}, format="json"
    )
    allowed = env.guest_client.patch(task_url(a["id"]), {"title": "Guest edit"}, format="json")
    assert allowed.status_code == 200
    assert allowed.json()["title"] == "Guest edit"

    delete_denied = env.guest_client.delete(task_url(a["id"]))
    assert_error(delete_denied, 403, "permission_denied")


# ------------------------------------------------------------- filters & queries


def test_filters_and_ordering(env, empty_list):
    a, b, c = make_tasks(env, empty_list, ["Alpha", "Beta", "Gamma"])
    env.member_client.patch(task_url(a["id"]), {"priority": "urgent"}, format="json")
    env.member_client.patch(
        task_url(b["id"]), {"assignee_ids": [str(env.member.id)]}, format="json"
    )

    url = tasks_url(empty_list.id)
    urgent = env.member_client.get(url + "?priority=urgent").json()
    assert [t["title"] for t in urgent["results"]] == ["Alpha"]

    mine = env.member_client.get(url + "?assignee=me").json()
    assert [t["title"] for t in mine["results"]] == ["Beta"]

    unassigned = env.member_client.get(url + "?assignee=none").json()
    assert {t["title"] for t in unassigned["results"]} == {"Alpha", "Gamma"}

    short_q = env.member_client.get(url + "?q=a").json()
    assert short_q["count"] == 0
    found = env.member_client.get(url + "?q=gam").json()
    assert [t["title"] for t in found["results"]] == ["Gamma"]

    bad = env.member_client.get(url + "?ordering=hax")
    assert_error(bad, 400, "validation_error")

    by_title = env.member_client.get(url + "?ordering=-title").json()
    assert [t["title"] for t in by_title["results"]] == ["Gamma", "Beta", "Alpha"]

    # workspace-wide query
    all_tasks = env.member_client.get(
        f"/api/v1/workspaces/{env.workspace.id}/tasks/?q=alpha"
    ).json()
    assert all_tasks["count"] == 1


def test_pagination_envelope_and_limits(env, empty_list):
    make_tasks(env, empty_list, [f"T{i}" for i in range(5)])
    url = tasks_url(empty_list.id)
    page = env.member_client.get(url + "?page_size=2&page=2").json()
    assert set(page.keys()) == {"count", "next", "previous", "results"}
    assert page["count"] == 5
    assert len(page["results"]) == 2
    assert page["previous"] is not None and page["next"] is not None

    too_big = env.member_client.get(url + "?page_size=201")
    assert_error(too_big, 400, "validation_error")

    past_end = env.member_client.get(url + "?page=99")
    assert_error(past_end, 404, "not_found")


def test_db_position_order_matches_python_sort(env, empty_list):
    tasks = make_tasks(env, empty_list, [f"T{i}" for i in range(20)])
    # scramble by moving a few between random neighbours
    rows = Task.objects.filter(list=empty_list).order_by("position")
    positions = [t.position for t in rows]
    assert positions == sorted(positions)


# ------------------------------------------------------------- activity history


def activity_url(task_id):
    return task_url(task_id, "activity/")


def test_activity_logged_on_create(env, empty_list):
    (task,) = make_tasks(env, empty_list, ["Historic"])
    body = env.member_client.get(activity_url(task["id"])).json()
    assert body["count"] == 1
    row = body["results"][0]
    assert row["verb"] == "created"
    assert row["to_value"] == "Historic"
    assert row["actor"]["id"] == str(env.member.id)
    assert row["metadata"]["status"] == env.statuses[0].name


def test_activity_status_change_also_records_completed(env, empty_list):
    (task,) = make_tasks(env, empty_list, ["Ship it"])
    closed = env.statuses[2]
    patched = env.member_client.patch(
        task_url(task["id"]), {"status_id": str(closed.id)}, format="json"
    )
    assert patched.status_code == 200, patched.content

    rows = env.member_client.get(activity_url(task["id"])).json()["results"]
    by_verb = {r["verb"]: r for r in rows}
    assert set(by_verb) == {"created", "status_changed", "completed"}

    changed = by_verb["status_changed"]
    assert changed["from_value"] == env.statuses[0].name
    assert changed["to_value"] == closed.name
    assert changed["actor"]["id"] == str(env.member.id)
    assert changed["metadata"]["to_status_id"] == str(closed.id)
    assert by_verb["completed"]["to_value"] == closed.name
    # the created row is the oldest, so it sorts last
    assert rows[-1]["verb"] == "created"


def test_activity_endpoint_shape_and_ordering(env, empty_list):
    (task,) = make_tasks(env, empty_list, ["Alpha"])
    env.member_client.patch(task_url(task["id"]), {"title": "Beta"}, format="json")
    env.member_client.patch(
        task_url(task["id"]),
        {"priority": "urgent", "assignee_ids": [str(env.guest.id)]},
        format="json",
    )

    body = env.member_client.get(activity_url(task["id"])).json()
    assert set(body.keys()) == {"count", "next", "previous", "results"}
    verbs = [r["verb"] for r in body["results"]]
    assert verbs[-1] == "created"
    assert "renamed" in verbs and "priority_changed" in verbs and "assignee_added" in verbs

    timestamps = [r["created_at"] for r in body["results"]]
    assert timestamps == sorted(timestamps, reverse=True)  # newest first

    row = body["results"][0]
    assert set(row.keys()) == {
        "id",
        "verb",
        "actor",
        "from_value",
        "to_value",
        "metadata",
        "created_at",
    }
    # UserSummary — `profession` (kasb yorlig'i) API_CONTRACT.md §2 bo'yicha
    # to'plamning bir qismi; u ruxsatga ta'sir qilmaydi.
    assert set(row["actor"].keys()) == {
        "id",
        "email",
        "full_name",
        "avatar",
        "avatar_color",
        "profession",
    }

    renamed = next(r for r in body["results"] if r["verb"] == "renamed")
    assert (renamed["from_value"], renamed["to_value"]) == ("Alpha", "Beta")
    added = next(r for r in body["results"] if r["verb"] == "assignee_added")
    assert added["to_value"] == env.guest.full_name


def test_activity_non_member_gets_404(env, empty_list):
    (task,) = make_tasks(env, empty_list, ["Private"])
    denied = env.outsider_client.get(activity_url(task["id"]))
    assert_error(denied, 404, "not_found")


def test_activity_empty_for_untouched_task(env):
    """Tasks that pre-date the history table return an empty list, not an error."""
    task = Task.objects.filter(list=env.list).first()
    TaskActivity.objects.filter(task=task).delete()
    body = env.member_client.get(activity_url(task.id)).json()
    assert body["count"] == 0
    assert body["results"] == []


# ------------------------------------------------------------- tags


def test_tag_crud(env):
    url = f"/api/v1/workspaces/{env.workspace.id}/tags/"
    denied = env.guest_client.post(url, {"name": "x"}, format="json")
    assert_error(denied, 403, "permission_denied")

    tag = env.member_client.post(url, {"name": "Backend"}, format="json")
    assert tag.status_code == 201
    dup = env.member_client.post(url, {"name": "backend"}, format="json")
    assert_error(dup, 409, "conflict")

    renamed = env.member_client.patch(
        f"/api/v1/tags/{tag.json()['id']}/", {"name": "Core"}, format="json"
    )
    assert renamed.status_code == 200
    gone = env.member_client.delete(f"/api/v1/tags/{tag.json()['id']}/")
    assert gone.status_code == 204
