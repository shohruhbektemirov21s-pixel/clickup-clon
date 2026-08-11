import random
import threading
import time

import pytest
from django.db import OperationalError, connection, connections
from django.test.utils import CaptureQueriesContext

from apps.core.access import bump_permissions_version
from apps.core.enums import STATUS_ORDER, SpaceAccess, TaskStatus, WatcherSource
from apps.core.ordering import MAX_LEN_BEFORE_REBALANCE, _guard, evenly_spaced, midstring
from apps.tasks import services
from apps.tasks.filters import ALLOWED_ORDERING_FIELDS
from apps.tasks.models import Task, TaskActivity
from apps.tasks.views import MAX_TASKS_PER_GROUP
from apps.workspaces.models import RolePermission, SpaceMember, TaskList
from conftest import assert_error

pytestmark = pytest.mark.django_db


def tasks_url(list_id):
    return f"/api/v1/lists/{list_id}/tasks/"


def task_url(task_id, suffix=""):
    return f"/api/v1/tasks/{task_id}/{suffix}"


def workspace_tasks_url(workspace_id):
    return f"/api/v1/workspaces/{workspace_id}/tasks/"


def set_permission(workspace, role, code, allowed):
    """Bitta katalog kodini shu ish maydoni uchun yoqadi/o'chiradi.

    `bump_permissions_version` — matritsani yozishning yagona to'g'ri yo'li
    (R3): u kesh kalitidagi versiyani oshiradi, aks holda shu test ichida
    allaqachon qurilgan matritsa eskirgan holda qolib ketardi.
    """
    RolePermission.objects.update_or_create(
        workspace=workspace, role=role, permission=code, defaults={"allowed": allowed}
    )
    bump_permissions_version(workspace)


@pytest.fixture
def empty_list(env):
    """A fresh list with no sample tasks.

    2026-08 siyosati: `list.create` endi faqat admin+ da, shuning uchun setup
    `admin_client` bilan quriladi (ilgari `member_client` edi).
    """
    response = env.admin_client.post(
        f"/api/v1/spaces/{env.space.id}/lists/", {"name": "Fresh"}, format="json"
    )
    return TaskList.objects.get(pk=response.json()["id"])


def close_thread_connections():
    """Ishchi oqim tugagach DB ulanishlarini haqiqatan yopadi.

    `connections.close_all()` yetarli emas: Django'ning SQLite backend'i
    xotiradagi bazani yo'q qilib yubormaslik uchun `close()` ni e'tiborsiz
    qoldiradi, natijada oqimning ulanishi GC'gacha ochiq qolib
    `ResourceWarning` beradi. `cache=shared` bazasi yo'qolmaydi — asosiy
    oqimning ulanishi ochiq turibdi.
    """
    for conn in connections.all(initialized_only=True):
        raw, conn.connection = conn.connection, None
        if raw is not None:
            raw.close()


@pytest.fixture
def captured_events(monkeypatch):
    """Har bir WebSocket freymini ushlaydi: `(group, event_type, payload)`.

    `_send` — barcha emitterlar o'tadigan yagona nuqta, shuning uchun kanal
    qatlamini ko'tarmasdan haqiqiy payload tekshiriladi.
    """
    frames = []
    monkeypatch.setattr(
        "apps.realtime.events._send",
        lambda group, event_type, payload: frames.append((group, event_type, payload)),
    )
    return frames


def make_space(env, name, *, is_private=False):
    """Admin nomidan yangi bo'lim + undagi ro'yxat.

    Ilgari uchinchi qaytim qiymati shu bo'limning status to'plami edi;
    statuslar endi global kodlar (`TaskStatus`), ya'ni qaytariladigan narsa
    qolmadi.
    """
    space = env.admin_client.post(
        f"/api/v1/workspaces/{env.workspace.id}/spaces/",
        {"name": name, "is_private": is_private},
        format="json",
    )
    assert space.status_code == 201, space.content
    space = space.json()
    task_list = env.admin_client.post(
        f"/api/v1/spaces/{space['id']}/lists/", {"name": f"{name} ro'yxati"}, format="json"
    )
    assert task_list.status_code == 201, task_list.content
    return space, task_list.json()


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
    assert body["status"] == TaskStatus.TODO.value
    assert body["is_deleted"] is False
    # creator is auto-watcher
    assert [w["id"] for w in body["watchers"]] == [str(env.member.id)]
    empty_list.refresh_from_db()
    assert empty_list.task_count == 1


def test_create_task_rejects_an_unknown_status_code(env, empty_list):
    """(b) Status yopiq kod to'plami — undan tashqari qiymat 400.

    Ilgari bu test "begona ro'yxatning statusi" ni tekshirardi
    (`invalid_status_for_list`). Bunday holat endi MAVJUD EMAS: status
    ro'yxatga bog'liq emas, shuning uchun yagona xato — noma'lum kod.
    """
    for bad in ["complete", "", "todo "]:
        response = env.member_client.post(
            tasks_url(empty_list.id), {"title": "X", "status": bad}, format="json"
        )
        error = assert_error(response, 400, "validation_error")
        assert "status" in error["details"], (bad, error)


def test_create_task_with_an_explicit_status_sets_completed_at(env, empty_list):
    """(c) `done` ga tushgan vazifada `completed_at` darhol to'ladi."""
    response = env.member_client.post(
        tasks_url(empty_list.id),
        {"title": "Allaqachon bajarilgan", "status": TaskStatus.DONE.value},
        format="json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["status"] == "done"
    assert body["completed_at"] is not None


def test_patch_status_round_trip_sets_and_clears_completed_at(env, empty_list):
    """(c) `done` ga o'tganda to'ladi, qaytganda TOZALANADI."""
    (task,) = make_tasks(env, empty_list, ["Aylanma"])
    assert task["completed_at"] is None

    done = env.admin_client.patch(
        task_url(task["id"]), {"status": "done"}, format="json"
    )
    assert done.status_code == 200, done.content
    assert done.json()["completed_at"] is not None

    back = env.admin_client.patch(
        task_url(task["id"]), {"status": "review"}, format="json"
    )
    assert back.status_code == 200, back.content
    assert back.json()["completed_at"] is None
    assert back.json()["status"] == "review"

    bad = env.admin_client.patch(
        task_url(task["id"]), {"status": "archived"}, format="json"
    )
    assert_error(bad, 400, "validation_error")


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

    patched = env.admin_client.patch(
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
    bad = env.admin_client.patch(
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
    """Setup uchun vazifalar — `admin_client` bilan.

    `member` hali ham `task.create` ga ega, lekin **begona** vazifani keyin
    tahrirlay/ko'chira/o'chira olmaydi, shuning uchun umumiy CRUD testlari
    admin nomidan quriladi. Member/PM/guest xatti-harakati
    `apps/core/tests/test_permission_policy.py` da alohida tekshiriladi.
    """
    out = []
    for title in titles:
        response = env.admin_client.post(tasks_url(task_list.id), {"title": title}, format="json")
        out.append(response.json())
    return out


def test_move_reorder_within_column(env, empty_list):
    a, b, c = make_tasks(env, empty_list, ["A", "B", "C"])
    moved = env.admin_client.patch(
        task_url(c["id"], "move/"),
        {
            "list_id": str(empty_list.id),
            "status": a["status"],
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
    target = env.list  # Getting Started
    moved = env.admin_client.patch(
        task_url(task["id"], "move/"),
        {"list_id": str(target.id), "status": TaskStatus.DONE.value},
        format="json",
    )
    assert moved.status_code == 200, moved.content
    body = moved.json()
    assert body["list_id"] == str(target.id)
    assert body["status"] == "done"
    assert body["completed_at"] is not None  # `done` yopiq status

    empty_list.refresh_from_db()
    assert empty_list.task_count == 0
    target.refresh_from_db()
    # The bootstrapped list starts empty, so the moved task is the only one.
    assert target.task_count == 1


def test_move_missing_status_and_stale_neighbours(env, empty_list):
    a, b = make_tasks(env, empty_list, ["A", "B"])
    no_status = env.admin_client.patch(
        task_url(a["id"], "move/"), {"list_id": str(empty_list.id)}, format="json"
    )
    assert_error(no_status, 400, "validation_error")

    # neighbour from a different column -> 409 position_conflict
    stale = env.admin_client.patch(
        task_url(a["id"], "move/"),
        {
            "list_id": str(empty_list.id),
            "status": TaskStatus.IN_PROGRESS.value,
            "before_id": b["id"],  # b `todo` ustunida, `in_progress` da emas
        },
        format="json",
    )
    assert_error(stale, 409, "position_conflict")

    bad_code = env.admin_client.patch(
        task_url(a["id"], "move/"),
        {"list_id": str(empty_list.id), "status": "shipped"},
        format="json",
    )
    assert_error(bad_code, 400, "validation_error")


def test_group_by_status_shape(env, empty_list):
    """(d) Doska javobi DOIM to'rtta guruh, DOIM `STATUS_ORDER` tartibida."""
    make_tasks(env, empty_list, ["A", "B"])
    response = env.member_client.get(tasks_url(empty_list.id) + "?group_by=status")
    assert response.status_code == 200
    body = response.json()
    assert body["group_by"] == "status"
    assert [g["status"] for g in body["groups"]] == [c.value for c in STATUS_ORDER]
    assert [g["label"] for g in body["groups"]] == [c.label for c in STATUS_ORDER]
    for group in body["groups"]:
        assert set(group) == {"status", "label", "tasks", "count"}
    counts = {g["status"]: g["count"] for g in body["groups"]}
    assert counts == {"todo": 2, "in_progress": 0, "review": 0, "done": 0}
    assert [t["title"] for t in body["groups"][0]["tasks"]] == ["A", "B"]
    # Bo'sh ustunlar ham chiziladi — doska ustunlari serverdan keladi.
    assert body["groups"][2]["tasks"] == []


def test_group_by_status_always_returns_four_groups_even_when_empty(env, empty_list):
    body = env.member_client.get(tasks_url(empty_list.id) + "?group_by=status").json()
    assert len(body["groups"]) == 4
    assert all(g["count"] == 0 and g["tasks"] == [] for g in body["groups"])


# ------------------------------------------------------------- delete / restore


def test_soft_delete_restore_and_include_deleted(env, empty_list):
    (task,) = make_tasks(env, empty_list, ["Doomed"])
    # 2026-08 siyosati: `task.delete` member'dan olib tashlandi.
    member_denied = env.member_client.delete(task_url(task["id"]))
    assert_error(member_denied, 403, "permission_denied")

    deleted = env.admin_client.delete(task_url(task["id"]))
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
    """Status kodlari + KUZATUVCHILAR TO'PLAMI.

    Ilgari faqat to'rtta status kodi tekshirilardi: `watch_task` /
    `unwatch_task` butunlay bo'sh funksiyalarga aylantirilsa ham test o'tardi.
    """
    (task,) = make_tasks(env, empty_list, ["W"])
    row = Task.objects.get(pk=task["id"])

    def watchers():
        return set(row.task_watchers.values_list("user_id", flat=True))

    assert watchers() == {env.admin.id}  # yaratuvchi avtomatik kuzatuvchi

    first = env.guest_client.post(task_url(task["id"], "watch/"))
    assert first.status_code == 201
    assert watchers() == {env.admin.id, env.guest.id}
    assert {w["id"] for w in first.json()["watchers"]} == {
        str(env.admin.id),
        str(env.guest.id),
    }
    assert row.task_watchers.get(user=env.guest).source == WatcherSource.MANUAL

    again = env.guest_client.post(task_url(task["id"], "watch/"))
    assert again.status_code == 200  # already watching
    assert row.task_watchers.filter(user=env.guest).count() == 1  # takroriy qator yo'q
    assert watchers() == {env.admin.id, env.guest.id}

    gone = env.guest_client.delete(task_url(task["id"], "watch/"))
    assert gone.status_code == 204
    assert watchers() == {env.admin.id}  # faqat o'zi chiqdi, yaratuvchi qoldi

    gone_again = env.guest_client.delete(task_url(task["id"], "watch/"))
    assert gone_again.status_code == 204
    assert watchers() == {env.admin.id}


# ------------------------------------------------------------- roles


def test_guest_permissions(env, empty_list):
    denied = env.guest_client.post(tasks_url(empty_list.id), {"title": "no"}, format="json")
    assert_error(denied, 403, "permission_denied")

    a, b = make_tasks(env, empty_list, ["A", "B"])
    not_assigned = env.guest_client.patch(task_url(a["id"]), {"title": "no"}, format="json")
    assert_error(not_assigned, 403, "permission_denied")

    env.admin_client.patch(
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
    env.admin_client.patch(task_url(a["id"]), {"priority": "urgent"}, format="json")
    env.admin_client.patch(
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

    too_big = env.member_client.get(url + "?page_size=101")
    assert_error(too_big, 400, "validation_error")

    past_end = env.member_client.get(url + "?page=99")
    assert_error(past_end, 404, "not_found")


def test_db_position_order_matches_python_sort(env, empty_list):
    """`position` ustunidagi `db_collation="C"` qarorining qo'riqchisi.

    Bu test ilgari HECH NARSANI tekshirmasdi: izohda "bir nechtasini tasodifiy
    qo'shnilar orasiga ko'chiramiz" deyilgan bo'lsa-da, hech narsa
    ko'chirilmasdi. `make_tasks` kalitlarni o'sish tartibida qo'shadi, ya'ni
    tasdiq `sorted(x) == sorted(x)` ga aylanardi va `move` endpointi butunlay
    o'chirilsa ham o'tardi.

    Endi ustun `move/` endpointi orqali haqiqatan aralashtiriladi (har bir
    ko'chirishdan keyin kutilgan tartib tasdiqlanadi), so'ng DB'ning
    `ORDER BY position` javobi Python'ning kod-nuqtali `sorted()` i bilan
    solishtiriladi. Kalitlarda ham katta harf, ham kichik harf/raqam borligi
    alohida tasdiqlanadi — aynan shu holatda `C` bo'lmagan kollatsiya
    (masalan PostgreSQL `en_US.UTF-8`: "a" < "B") boshqa javob berardi.
    """
    make_tasks(env, empty_list, [f"T{i}" for i in range(12)])
    status = TaskStatus.TODO.value
    rng = random.Random(7)

    def column_ids():
        return [
            str(pk)
            for pk in Task.objects.filter(list=empty_list)
            .order_by("position")
            .values_list("id", flat=True)
        ]

    for _ in range(25):
        ids = column_ids()
        moving = ids.pop(rng.randrange(len(ids)))
        slot = rng.randrange(len(ids) + 1)
        payload = {"list_id": str(empty_list.id), "status": status}
        if slot > 0:
            payload["before_id"] = ids[slot - 1]
        if slot < len(ids):
            payload["after_id"] = ids[slot]
        response = env.admin_client.patch(
            task_url(moving, "move/"), payload, format="json"
        )
        assert response.status_code == 200, response.content
        expected = ids[:slot] + [moving] + ids[slot:]
        assert column_ids() == expected  # ko'chirish haqiqatan tartibni o'zgartirdi

    positions = list(
        Task.objects.filter(list=empty_list)
        .order_by("created_at")
        .values_list("position", flat=True)
    )
    assert len(set(positions)) == len(positions)
    db_order = list(
        Task.objects.filter(list=empty_list)
        .order_by("position")
        .values_list("position", flat=True)
    )
    assert db_order == sorted(positions)

    alphabet_used = set("".join(positions))
    assert any(c.isupper() for c in alphabet_used), positions
    assert any(c.islower() or c.isdigit() for c in alphabet_used), positions


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
    assert row["actor"]["id"] == str(env.admin.id)
    assert row["metadata"]["status"] == "todo"


def test_activity_status_change_also_records_completed(env, empty_list):
    (task,) = make_tasks(env, empty_list, ["Ship it"])
    patched = env.admin_client.patch(
        task_url(task["id"]), {"status": TaskStatus.DONE.value}, format="json"
    )
    assert patched.status_code == 200, patched.content

    rows = env.member_client.get(activity_url(task["id"])).json()["results"]
    by_verb = {r["verb"]: r for r in rows}
    assert set(by_verb) == {"created", "status_changed", "completed"}

    changed = by_verb["status_changed"]
    # Tarix KODNI saqlaydi, o'zbekcha yorliqni emas: tarjima o'zgarsa ham
    # eski qatorlar o'qilishi kerak.
    assert changed["from_value"] == "todo"
    assert changed["to_value"] == "done"
    assert changed["actor"]["id"] == str(env.admin.id)
    assert changed["metadata"]["to_status"] == "done"
    assert changed["metadata"]["from_status"] == "todo"
    assert by_verb["completed"]["to_value"] == "done"
    # the created row is the oldest, so it sorts last
    assert rows[-1]["verb"] == "created"


def test_activity_endpoint_shape_and_ordering(env, empty_list):
    (task,) = make_tasks(env, empty_list, ["Alpha"])
    env.admin_client.patch(task_url(task["id"]), {"title": "Beta"}, format="json")
    env.admin_client.patch(
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
    (created,) = make_tasks(env, env.list, ["Tarixsiz vazifa"])
    task = Task.objects.get(pk=created["id"])
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

    # 2026-08 siyosati: `tag.create` member'da qoldi, `tag.update`/`tag.delete` yo'q.
    member_rename = env.member_client.patch(
        f"/api/v1/tags/{tag.json()['id']}/", {"name": "Nope"}, format="json"
    )
    assert_error(member_rename, 403, "permission_denied")
    member_delete = env.member_client.delete(f"/api/v1/tags/{tag.json()['id']}/")
    assert_error(member_delete, 403, "permission_denied")

    renamed = env.admin_client.patch(
        f"/api/v1/tags/{tag.json()['id']}/", {"name": "Core"}, format="json"
    )
    assert renamed.status_code == 200
    gone = env.admin_client.delete(f"/api/v1/tags/{tag.json()['id']}/")
    assert gone.status_code == 204


# ==================================================================== rebalance


def test_move_rebalances_the_column_when_the_gap_is_exhausted(
    env, empty_list, captured_events
):
    """`rebalance_column()` — repodagi eng murakkab kod — suite'dan yetib
    bo'lmaydigan joyda edi.

    Yagona mavjud test `rebalanced is False` ni tasdiqlardi, HECH BIR test esa
    `True` holatini keltirib chiqarmasdi: `select_for_update()` li ikki
    bosqichli qayta kalitlash hech qachon bajarilmasdi.

    Ustun to'g'ridan-to'g'ri "bo'shliq tugagan" holatga qo'yiladi (aynan shu
    holatga bir xil juftlik orasiga ~150 marta qo'yishdan keyin yetib
    kelinadi; testni sekinlashtirmaslik uchun kalitlar qo'lda yoziladi), so'ng
    bitta HAQIQIY `move/` chaqiruvi qilinadi.
    """
    a, b, c = make_tasks(env, empty_list, ["A", "B", "C"])
    squeezed = "a" + "0" * 47 + "1"
    assert len(midstring("a", squeezed)) > MAX_LEN_BEFORE_REBALANCE
    Task.objects.filter(pk=a["id"]).update(position="a")
    Task.objects.filter(pk=b["id"]).update(position=squeezed)
    Task.objects.filter(pk=c["id"]).update(position="z")

    moved = env.admin_client.patch(
        task_url(c["id"], "move/"),
        {
            "list_id": str(empty_list.id),
            "status": a["status"],
            "before_id": a["id"],
            "after_id": b["id"],
        },
        format="json",
    )
    assert moved.status_code == 200, moved.content
    assert moved.json()["rebalanced"] is True

    positions = dict(
        Task.objects.filter(list=empty_list).values_list("title", "position")
    )
    keys = evenly_spaced(3)
    # tegilmagan ikki qator tekis qayta kalitlandi...
    assert positions["A"] == keys[0]
    assert positions["B"] == keys[1]
    # ...ko'chirilgani esa ular orasiga tushdi, uzun kalit yo'qoldi
    assert keys[0] < positions["C"] < keys[1]
    assert max(len(p) for p in positions.values()) <= 2

    listing = env.member_client.get(tasks_url(empty_list.id)).json()["results"]
    assert [t["title"] for t in listing] == ["A", "C", "B"]  # nisbiy tartib saqlandi

    frames = [f for f in captured_events if f[1] == "task.moved"]
    assert frames, captured_events
    assert all(f[2]["rebalanced"] is True for f in frames)


def test_move_without_rebalance_reports_false_in_the_event(
    env, empty_list, captured_events
):
    a, b, c = make_tasks(env, empty_list, ["A", "B", "C"])
    moved = env.admin_client.patch(
        task_url(c["id"], "move/"),
        {
            "list_id": str(empty_list.id),
            "status": a["status"],
            "before_id": a["id"],
            "after_id": b["id"],
        },
        format="json",
    )
    assert moved.status_code == 200, moved.content
    assert moved.json()["rebalanced"] is False
    frames = [f for f in captured_events if f[1] == "task.moved"]
    assert frames and all(f[2]["rebalanced"] is False for f in frames)


@pytest.mark.django_db(transaction=True)
def test_concurrent_moves_into_the_same_gap(env, empty_list, captured_events):
    """Ikki oqim BIR XIL qo'shni juftlik orasiga ko'chiradi.

    `uniq_task_position_per_column` + qayta urinish mantiqi aynan shu holat
    uchun yozilgan edi, lekin hech qanday test uni ishga tushirmasdi. Yutqazgan
    tomon `IntegrityError` oladi va qayta uriladi; `midstring(prev, next)` esa
    O'SHA kalitni qaytargani uchun ilgari urinishlar hech qachon
    yaqinlashmasdi (3 urinish → 409) — endi g'olibning ustidan bir qadam
    bosiladi.
    """
    a, b = make_tasks(env, empty_list, ["A", "B"])
    x, y = make_tasks(env, empty_list, ["X", "Y"])
    status = TaskStatus.TODO.value
    barrier = threading.Barrier(2, timeout=30)
    outcome = {}

    def move_once(task_id):
        services.move_task(
            Task.objects.select_related("list__space").get(pk=task_id),
            list_id=empty_list.id,
            status=status,
            before_id=a["id"],
            after_id=b["id"],
            actor=env.admin,
        )

    def move(title, task_id):
        try:
            barrier.wait()
            # SQLite'ning test bazasi `cache=shared` rejimidagi xotira bazasi:
            # u yozuvchilarni JADVAL qulfi bilan ajratadi va `SQLITE_LOCKED`
            # ni busy-handler QAYTA URINMAYDI. Bu backend artefakti, mahsulot
            # xatosi emas, shuning uchun faqat shu xato qayta uriniladi —
            # `IntegrityError` / `PositionConflict` esa testni yiqitadi, chunki
            # test aynan ularni tekshiradi. PostgreSQL'da bu tarmoq
            # bajarilmaydi: u yerda qatorlar qulflanadi va ikkala tranzaksiya
            # parallel ketadi.
            deadline = time.monotonic() + 30
            while True:
                try:
                    move_once(task_id)
                    break
                except OperationalError as exc:
                    if "locked" not in str(exc) or time.monotonic() > deadline:
                        raise
                    time.sleep(random.uniform(0.005, 0.03))
            outcome[title] = "ok"
        except BaseException as exc:  # noqa: BLE001 — oqimdagi xato testga chiqsin
            outcome[title] = exc
        finally:
            close_thread_connections()

    threads = [
        threading.Thread(target=move, args=("X", x["id"])),
        threading.Thread(target=move, args=("Y", y["id"])),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
        assert not thread.is_alive()

    assert outcome == {"X": "ok", "Y": "ok"}, outcome

    rows = list(
        Task.objects.filter(list=empty_list)
        .order_by("position")
        .values_list("title", "position")
    )
    titles = [t for t, _ in rows]
    positions = [p for _, p in rows]
    assert len(set(positions)) == len(positions)  # pozitsiyalar noyob
    assert positions == sorted(positions)
    assert titles[0] == "A" and titles[-1] == "B"
    assert set(titles[1:3]) == {"X", "Y"}  # ikkalasi ham A bilan B orasida

    # To'qnashuv HAQIQATAN bo'lganini qulflaymiz: ikkala oqim ham
    # `midstring(A, B)` ni xohlagan, biri uni oldi, ikkinchisi ustidan qadam
    # bosdi. Nudge bo'lmasa bu holat 3 urinishdan keyin 409 bilan tugardi.
    naive = midstring(positions[0], positions[-1])
    assert naive in positions[1:3]
    assert any(p != naive for p in positions[1:3])


# ============================================================ move: destination


def test_move_into_a_space_the_actor_cannot_see_is_404(env, empty_list):
    """Manzil bo'lim ko'rinmasa — 404, mavjudligi oshkor qilinmaydi."""
    SpaceMember.objects.create(space=env.space, user=env.guest, access=SpaceAccess.MANAGER)
    _, hidden_list = make_space(env, "Yopiq", is_private=True)
    (task,) = make_tasks(env, empty_list, ["Mening ishim"])

    denied = env.guest_client.patch(
        task_url(task["id"], "move/"),
        {"list_id": hidden_list["id"], "status": TaskStatus.TODO.value},
        format="json",
    )
    assert_error(denied, 404, "not_found")
    assert Task.objects.get(pk=task["id"]).list_id == empty_list.id


def test_move_into_another_space_checks_the_destination_too(env, empty_list):
    """`task.move` ilgari faqat MANBA bo'limiga nisbatan baholanardi.

    A bo'limining menejeri vazifani o'zi hech qanday yozish huquqiga ega
    bo'lmagan B bo'limiga surib qo'ya olardi: ruxsat manbadan olinib, natija
    manzilda paydo bo'lardi.
    """
    SpaceMember.objects.create(space=env.space, user=env.guest, access=SpaceAccess.MANAGER)
    other, other_list = make_space(env, "Ikkinchi")
    (task,) = make_tasks(env, empty_list, ["Ko'chadi"])
    payload = {"list_id": other_list["id"], "status": TaskStatus.TODO.value}

    denied = env.guest_client.patch(task_url(task["id"], "move/"), payload, format="json")
    assert_error(denied, 403, "permission_denied")
    assert Task.objects.get(pk=task["id"]).list_id == empty_list.id

    # o'sha bo'lim ICHIDA ko'chirish hamon ishlaydi (manba = manzil)
    inside = env.guest_client.patch(
        task_url(task["id"], "move/"),
        {"list_id": str(env.list.id), "status": TaskStatus.IN_PROGRESS.value},
        format="json",
    )
    assert inside.status_code == 200, inside.content

    # manzilda ham menejer bo'lsa — o'tadi
    SpaceMember.objects.create(
        space_id=other["id"], user=env.guest, access=SpaceAccess.MANAGER
    )
    allowed = env.guest_client.patch(task_url(task["id"], "move/"), payload, format="json")
    assert allowed.status_code == 200, allowed.content
    assert allowed.json()["list_id"] == other_list["id"]


def test_admin_may_still_move_across_spaces(env, empty_list):
    _, other_list = make_space(env, "Uchinchi")
    (task,) = make_tasks(env, empty_list, ["Admin ko'chiradi"])
    moved = env.admin_client.patch(
        task_url(task["id"], "move/"),
        {"list_id": other_list["id"], "status": TaskStatus.TODO.value},
        format="json",
    )
    assert moved.status_code == 200, moved.content
    assert moved.json()["list_id"] == other_list["id"]


def test_move_with_a_soft_deleted_neighbour_is_a_conflict(env, empty_list):
    """O'chirilgan qator ustunda yo'q — mijozning ko'rinishi eskirgan."""
    a, b, c = make_tasks(env, empty_list, ["A", "B", "C"])
    assert env.admin_client.delete(task_url(b["id"])).status_code == 204
    base = {"list_id": str(empty_list.id), "status": a["status"]}

    after = env.admin_client.patch(
        task_url(c["id"], "move/"), {**base, "after_id": b["id"]}, format="json"
    )
    assert_error(after, 409, "position_conflict")

    before = env.admin_client.patch(
        task_url(c["id"], "move/"), {**base, "before_id": b["id"]}, format="json"
    )
    assert_error(before, 409, "position_conflict")

    assert Task.objects.get(pk=c["id"]).position == c["position"]  # hech narsa yozilmadi


# ============================================================== task.assign


def test_changing_someone_elses_assignment_requires_task_assign(env, empty_list):
    """`task.assign` YOLG'ON NAZORAT edi: katalogda va grant to'plamlarida bor,
    lekin hech bir endpoint uni tekshirmasdi.

    Zanjir: `task.update_assigned` ga ega a'zo (guest darajasi) o'ziga
    biriktirilgan vazifada `require_task_editor` dan o'tardi, `update_task`
    esa `assignee_ids` ni faqat ish maydoni a'zoligiga tekshirib qo'llardi.
    Yopiq bo'limda bu `_grant_assignee_space_access` orqali begonaga
    `SpaceMember` yozib, unga BUTUN bo'limni ochib berardi — ya'ni
    `space.manage_members` (admin-only) `task.update_assigned` orqali
    aylanib o'tilardi. Qo'shimcha ravishda u barcha hamkasblarini jimgina
    yechib tashlay olardi.
    """
    (task,) = make_tasks(env, empty_list, ["Umumiy ish"])
    assert (
        env.admin_client.patch(
            task_url(task["id"]), {"assignee_ids": [str(env.guest.id)]}, format="json"
        ).status_code
        == 200
    )
    row = Task.objects.get(pk=task["id"])

    def assignees():
        return set(row.task_assignees.values_list("user_id", flat=True))

    assert assignees() == {env.guest.id}

    # guest `task.update_assigned` bilan tahrirlay oladi...
    edit = env.guest_client.patch(task_url(task["id"]), {"title": "Ishlayapman"}, format="json")
    assert edit.status_code == 200

    # ...lekin hamkasbini biriktira olmaydi
    escalate = env.guest_client.patch(
        task_url(task["id"]),
        {"assignee_ids": [str(env.guest.id), str(env.member.id)]},
        format="json",
    )
    assert_error(escalate, 403, "permission_denied")
    assert assignees() == {env.guest.id}

    # ...va boshqani almashtirib qo'ya olmaydi
    swap = env.guest_client.patch(
        task_url(task["id"]), {"assignee_ids": [str(env.member.id)]}, format="json"
    )
    assert_error(swap, 403, "permission_denied")
    assert assignees() == {env.guest.id}


def test_unchanged_assignee_ids_do_not_require_task_assign(env, empty_list):
    """Frontend PATCH'da butun obyektni qaytarib yuboradi — o'zgarmagan
    ro'yxat tahrirni bloklamasligi kerak."""
    (task,) = make_tasks(env, empty_list, ["Umumiy ish"])
    env.admin_client.patch(
        task_url(task["id"]), {"assignee_ids": [str(env.guest.id)]}, format="json"
    )
    same = env.guest_client.patch(
        task_url(task["id"]),
        {"title": "Yangi nom", "assignee_ids": [str(env.guest.id)]},
        format="json",
    )
    assert same.status_code == 200, same.content
    assert same.json()["title"] == "Yangi nom"


def test_self_assignment_is_allowed_without_task_assign(env, empty_list):
    """MAHSULOT QARORI: "vazifani olaman" / "tashlab ketaman" oqimlari
    admin aralashuvisiz ishlaydi.

    Bu kengaytma emas — chaqiruvchi bu nuqtada vazifani ko'rib va tahrirlay
    olib turibdi, `_grant_assignee_space_access` esa bo'limni allaqachon
    ko'rayotgan odamga `SpaceMember` yozmaydi.
    """
    (task,) = make_tasks(env, empty_list, ["Egasiz ish"])
    set_permission(env.workspace, "admin", "task.assign", False)
    row = Task.objects.get(pk=task["id"])

    claim = env.admin_client.patch(
        task_url(task["id"]), {"assignee_ids": [str(env.admin.id)]}, format="json"
    )
    assert claim.status_code == 200, claim.content
    assert set(row.task_assignees.values_list("user_id", flat=True)) == {env.admin.id}

    drop = env.admin_client.patch(task_url(task["id"]), {"assignee_ids": []}, format="json")
    assert drop.status_code == 200, drop.content
    assert set(row.task_assignees.values_list("user_id", flat=True)) == set()

    # ...boshqa birov esa hamon `task.assign` talab qiladi
    other = env.admin_client.patch(
        task_url(task["id"]), {"assignee_ids": [str(env.member.id)]}, format="json"
    )
    assert_error(other, 403, "permission_denied")


def test_an_assignee_may_drop_themselves(env, empty_list):
    """`task.update_assigned` bilan o'zini yechish — 200, boshqasi bilan birga
    yechish — 403."""
    (task,) = make_tasks(env, empty_list, ["Juftlik ishi"])
    env.admin_client.patch(
        task_url(task["id"]),
        {"assignee_ids": [str(env.guest.id), str(env.member.id)]},
        format="json",
    )
    row = Task.objects.get(pk=task["id"])

    both = env.guest_client.patch(task_url(task["id"]), {"assignee_ids": []}, format="json")
    assert_error(both, 403, "permission_denied")  # hamkasbini ham yechib yubormaydi

    only_self = env.guest_client.patch(
        task_url(task["id"]), {"assignee_ids": [str(env.member.id)]}, format="json"
    )
    assert only_self.status_code == 200, only_self.content
    assert set(row.task_assignees.values_list("user_id", flat=True)) == {env.member.id}


def test_unparsable_assignee_ids_fail_closed(env, empty_list):
    """Ruxsat validatsiyadan OLDIN tekshiriladi, shuning uchun parse
    qilinmagan payload "hech narsa o'zgarmadi" deb hisoblanmaydi."""
    (task,) = make_tasks(env, empty_list, ["Ish"])
    env.admin_client.patch(
        task_url(task["id"]), {"assignee_ids": [str(env.guest.id)]}, format="json"
    )
    junk = env.guest_client.patch(
        task_url(task["id"]), {"assignee_ids": ["emas-uuid"]}, format="json"
    )
    assert_error(junk, 403, "permission_denied")
    # ruxsati borida esa oddiy 400
    assert_error(
        env.admin_client.patch(
            task_url(task["id"]), {"assignee_ids": ["emas-uuid"]}, format="json"
        ),
        400,
        "validation_error",
    )


def test_create_with_assignees_needs_task_assign_unless_it_is_self(env, empty_list):
    """Yaratishda ham xuddi shu qoida — `task.create` `task.assign` ni
    o'rnini bosmaydi."""
    denied = env.member_client.post(
        tasks_url(empty_list.id),
        {"title": "Boshqaga", "assignee_ids": [str(env.guest.id)]},
        format="json",
    )
    assert_error(denied, 403, "permission_denied")
    assert not Task.objects.filter(title="Boshqaga").exists()

    mine = env.member_client.post(
        tasks_url(empty_list.id),
        {"title": "O'zimga", "assignee_ids": [str(env.member.id)]},
        format="json",
    )
    assert mine.status_code == 201, mine.content
    assert [a["id"] for a in mine.json()["assignees"]] == [str(env.member.id)]

    junk = env.member_client.post(
        tasks_url(empty_list.id),
        {"title": "Buzuq", "assignee_ids": ["emas-uuid"]},
        format="json",
    )
    assert_error(junk, 403, "permission_denied")  # fail-closed


# ================================================================= task.read


READ_ENDPOINTS = ("list", "board", "detail", "activity", "workspace")


def read_responses(client, workspace_id, list_id, task_id):
    return {
        "list": client.get(tasks_url(list_id)),
        "board": client.get(tasks_url(list_id) + "?group_by=status"),
        "detail": client.get(task_url(task_id)),
        "activity": client.get(task_url(task_id, "activity/")),
        "workspace": client.get(workspace_tasks_url(workspace_id)),
    }


def test_task_read_is_enforced_on_every_read_endpoint(env, empty_list):
    """`task.read` ham yolg'on nazorat edi — u faqat `WorkspaceActivityView`
    da tekshirilardi, ya'ni matritsadan olib tashlash vazifa o'qishga hech
    qanday ta'sir qilmasdi."""
    (task,) = make_tasks(env, empty_list, ["Ko'rinadigan"])
    allowed = read_responses(env.guest_client, env.workspace.id, empty_list.id, task["id"])
    assert {k: r.status_code for k, r in allowed.items()} == dict.fromkeys(READ_ENDPOINTS, 200)

    set_permission(env.workspace, "guest", "task.read", False)
    denied = read_responses(env.guest_client, env.workspace.id, empty_list.id, task["id"])
    assert set(denied) == set(READ_ENDPOINTS)
    for response in denied.values():
        assert_error(response, 403, "permission_denied")

    # kodni qaytarsak — yana ishlaydi (matritsa haqiqatan boshqaradi)
    set_permission(env.workspace, "guest", "task.read", True)
    again = read_responses(env.guest_client, env.workspace.id, empty_list.id, task["id"])
    assert {k: r.status_code for k, r in again.items()} == dict.fromkeys(READ_ENDPOINTS, 200)


def test_task_read_keeps_404_before_403(env, empty_list):
    """C.4 tartibi: mavjud emas / ko'rinmaydi → 404, keyin ruxsat → 403."""
    (task,) = make_tasks(env, empty_list, ["Yashirin"])
    set_permission(env.workspace, "guest", "task.read", False)

    outsider = read_responses(
        env.outsider_client, env.workspace.id, empty_list.id, task["id"]
    )
    for key in ("list", "board", "detail", "activity", "workspace"):
        assert_error(outsider[key], 404, "not_found")

    _, hidden_list = make_space(env, "Yopiq bo'lim", is_private=True)
    hidden_task = env.admin_client.post(
        tasks_url(hidden_list["id"]), {"title": "Yopiq ish"}, format="json"
    ).json()
    # guest yopiq bo'limni ko'rmaydi → ruxsatdan OLDIN 404
    assert_error(env.guest_client.get(task_url(hidden_task["id"])), 404, "not_found")
    assert_error(env.guest_client.get(tasks_url(hidden_list["id"])), 404, "not_found")


# ============================================================ board (group_by)


def test_board_query_count_does_not_scale_with_task_count(env, empty_list):
    """Doska ilgari HAR BIR status uchun alohida `COUNT(*)` + alohida `SELECT`
    yugurtirardi.

    Ustunlar soni endi qat'iy to'rtta, shuning uchun "ustun qo'shib ko'ramiz"
    stsenariysi mavjud emas. Qulflanadigan invariant esa saqlanadi: bitta
    `GROUP BY`, bitta `ROW_NUMBER() OVER (PARTITION BY status)` va o'zgarmas
    `prefetch` lar — ya'ni so'rovlar soni VAZIFALAR soniga ham, ular necha
    ustunga tarqalganiga ham bog'liq emas.
    """
    make_tasks(env, empty_list, ["A", "B"])
    url = tasks_url(empty_list.id) + "?group_by=status"

    def measure():
        env.member_client.get(url)  # ruxsat matritsasi keshini isitamiz
        with CaptureQueriesContext(connection) as ctx:
            response = env.member_client.get(url)
        assert response.status_code == 200, response.content
        return len(ctx.captured_queries), response.json()

    small, body = measure()
    assert len(body["groups"]) == 4

    # Har bir ustunga vazifa tarqatamiz — barcha to'rttasi to'ladi.
    keys = evenly_spaced(24)
    Task.objects.bulk_create(
        [
            Task(
                list=empty_list,
                status=STATUS_ORDER[i % 4],
                title=f"Q{i:02d}",
                position=keys[i],
                created_by=env.admin,
                updated_by=env.admin,
            )
            for i in range(24)
        ]
    )
    large, body = measure()
    assert len(body["groups"]) == 4
    assert sum(g["count"] for g in body["groups"]) == 26
    assert large == small, f"{small} → {large} so'rov: hajm ta'sir qilmasligi kerak"


def test_board_group_size_is_capped_independently_of_page_size(env, empty_list):
    """Doska javobi sahifalanmaydi (§1.5 istisnosi), shuning uchun ustun
    hajmi `page_size` ga emas, qat'iy shiftga bog'liq: aks holda
    `?page_size=100` × 4 ustun = bitta javobda 400 vazifa."""
    keys = evenly_spaced(60)
    Task.objects.bulk_create(
        [
            Task(
                list=empty_list,
                status=TaskStatus.TODO,
                title=f"T{i:02d}",
                position=keys[i],
                created_by=env.admin,
                updated_by=env.admin,
            )
            for i in range(60)
        ]
    )
    url = tasks_url(empty_list.id) + "?group_by=status"

    def column(query):
        body = env.member_client.get(url + query).json()
        return next(g for g in body["groups"] if g["status"] == "todo")

    capped = column("&page_size=100")
    assert capped["count"] == 60  # to'liq son hamon ko'rsatiladi
    assert len(capped["tasks"]) == MAX_TASKS_PER_GROUP
    assert [t["title"] for t in capped["tasks"]] == [
        f"T{i:02d}" for i in range(MAX_TASKS_PER_GROUP)
    ]

    assert len(column("&page_size=5")["tasks"]) == 5  # kichikroq so'rov hurmat qilinadi
    assert_error(
        env.member_client.get(url + "&page_size=101"), 400, "validation_error"
    )


def test_board_groups_apply_filters_ordering_and_match_the_flat_result(env, empty_list):
    """§10.4: filtrlar/tartib guruhlar ichida ham bir xil ishlaydi va
    guruhlar birlashmasi tekis natijaga teng."""
    a, b, c = make_tasks(env, empty_list, ["Alpha", "Beta", "Gamma"])
    tag = env.member_client.post(
        f"/api/v1/workspaces/{env.workspace.id}/tags/", {"name": "core"}, format="json"
    ).json()
    env.admin_client.patch(
        task_url(a["id"]),
        {"assignee_ids": [str(env.member.id)], "tag_ids": [tag["id"]]},
        format="json",
    )
    env.admin_client.patch(
        task_url(b["id"]), {"assignee_ids": [str(env.member.id)]}, format="json"
    )
    url = tasks_url(empty_list.id)

    # `assignee` filtri JOIN + `.distinct()` qo'shadi; oyna funksiyasi
    # DISTINCT'dan oldin hisoblanadi, shuning uchun view avval `pk` to'plamini
    # oladi — shu tarmoq aynan shu yerda qulflanadi.
    grouped = env.member_client.get(url + "?group_by=status&assignee=me").json()
    titles = [t["title"] for g in grouped["groups"] for t in g["tasks"]]
    assert titles == ["Alpha", "Beta"]
    assert sum(g["count"] for g in grouped["groups"]) == 2

    flat = env.member_client.get(url + "?assignee=me").json()
    assert {t["title"] for t in flat["results"]} == set(titles)
    assert flat["count"] == sum(g["count"] for g in grouped["groups"])

    # ichma-ich prefetch oynali so'rovdan keyin ham ishlaydi
    alpha = next(t for t in grouped["groups"][0]["tasks"] if t["title"] == "Alpha")
    assert [x["id"] for x in alpha["assignees"]] == [str(env.member.id)]
    assert [x["name"] for x in alpha["tags"]] == ["core"]

    tagged = env.member_client.get(url + f"?group_by=status&tag={tag['id']}").json()
    assert [t["title"] for g in tagged["groups"] for t in g["tasks"]] == ["Alpha"]

    ordered = env.member_client.get(url + "?group_by=status&ordering=-title").json()
    assert [t["title"] for g in ordered["groups"] for t in g["tasks"]] == [
        "Gamma",
        "Beta",
        "Alpha",
    ]
    assert_error(
        env.member_client.get(url + "?group_by=status&ordering=hax"),
        400,
        "validation_error",
    )


# ============================================================ ordering & filters


def test_ordering_accepts_every_allowed_field(env, empty_list):
    """Ilgari faqat `-title` sinalardi — qolgan besh maydon sukut bilan
    ishlamay qolishi mumkin edi."""
    a, b, c = make_tasks(env, empty_list, ["Alpha", "Beta", "Gamma"])
    env.admin_client.patch(
        task_url(a["id"]),
        {"priority": "low", "due_date": "2026-09-03T00:00:00Z"},
        format="json",
    )
    env.admin_client.patch(
        task_url(b["id"]),
        {"priority": "urgent", "due_date": "2026-09-01T00:00:00Z"},
        format="json",
    )
    env.admin_client.patch(
        task_url(c["id"]),
        {"priority": "high", "due_date": "2026-09-02T00:00:00Z"},
        format="json",
    )
    expected = {
        "position": ["Alpha", "Beta", "Gamma"],
        "title": ["Alpha", "Beta", "Gamma"],
        "created_at": ["Alpha", "Beta", "Gamma"],
        "updated_at": ["Alpha", "Beta", "Gamma"],
        "due_date": ["Beta", "Gamma", "Alpha"],
        "priority_order": ["Beta", "Gamma", "Alpha"],  # urgent(1) < high(2) < low(4)
    }
    # yangi maydon qo'shilsa shu test uni sinashga majbur qiladi
    assert set(expected) == ALLOWED_ORDERING_FIELDS

    url = tasks_url(empty_list.id)
    for field, order in expected.items():
        asc = env.member_client.get(f"{url}?ordering={field}")
        assert asc.status_code == 200, (field, asc.content)
        assert [t["title"] for t in asc.json()["results"]] == order, field

        desc = env.member_client.get(f"{url}?ordering=-{field}")
        assert desc.status_code == 200, (field, desc.content)
        assert [t["title"] for t in desc.json()["results"]] == order[::-1], field


def test_filter_combinations_status_and_tags(env, empty_list):
    a, b, c = make_tasks(env, empty_list, ["Alpha report", "Beta report", "Gamma"])
    tag = env.member_client.post(
        f"/api/v1/workspaces/{env.workspace.id}/tags/", {"name": "core"}, format="json"
    ).json()
    other_tag = env.member_client.post(
        f"/api/v1/workspaces/{env.workspace.id}/tags/", {"name": "ops"}, format="json"
    ).json()
    env.admin_client.patch(
        task_url(a["id"]),
        {
            "priority": "urgent",
            "assignee_ids": [str(env.member.id)],
            "tag_ids": [tag["id"]],
        },
        format="json",
    )
    env.admin_client.patch(task_url(b["id"]), {"priority": "urgent"}, format="json")
    env.admin_client.patch(
        task_url(c["id"]),
        {"assignee_ids": [str(env.member.id)], "tag_ids": [other_tag["id"]]},
        format="json",
    )
    env.admin_client.patch(
        task_url(c["id"]), {"status": TaskStatus.IN_PROGRESS.value}, format="json"
    )
    url = tasks_url(empty_list.id)

    def titles(query):
        response = env.member_client.get(url + query)
        assert response.status_code == 200, response.content
        return [t["title"] for t in response.json()["results"]]

    # turli kalitlar AND bilan birlashadi
    assert titles("?priority=urgent&assignee=me&q=report") == ["Alpha report"]
    assert titles("?priority=urgent&q=report") == ["Alpha report", "Beta report"]
    assert titles("?priority=urgent&assignee=me&q=gamma") == []

    # bitta kalitning takrorlangan qiymatlari OR bilan
    assert set(titles(f"?assignee=me&assignee={env.admin.id}")) == {
        "Alpha report",
        "Gamma",
    }

    # status — endi kodlar bo'yicha; `?status_type=` OLIB TASHLANDI
    # (`status == "done"` yopiq degani, alohida "tur" tushunchasi yo'q).
    assert titles("?status=in_progress") == ["Gamma"]
    assert set(titles("?status=todo&status=in_progress")) == {
        "Alpha report",
        "Beta report",
        "Gamma",
    }
    assert titles("?status=done") == []
    assert_error(
        env.member_client.get(url + "?status=active"), 400, "validation_error"
    )

    # tag
    assert titles(f"?tag={tag['id']}") == ["Alpha report"]
    assert set(titles(f"?tag={tag['id']}&tag={other_tag['id']}")) == {
        "Alpha report",
        "Gamma",
    }
    assert titles(f"?tag={tag['id']}&priority=urgent") == ["Alpha report"]
    assert titles(f"?tag={tag['id']}&priority=low") == []


# ======================================================== workspace-wide tasks


def test_workspace_tasks_pagination_filters_and_private_spaces(env, empty_list):
    """Ilgari bu endpoint uchun faqat `?q=alpha` sinalardi."""
    make_tasks(env, empty_list, [f"T{i:02d}" for i in range(7)])
    private, private_list = make_space(env, "Maxfiy", is_private=True)
    secret = env.admin_client.post(
        tasks_url(private_list["id"]), {"title": "Maxfiy ish"}, format="json"
    )
    assert secret.status_code == 201, secret.content
    url = workspace_tasks_url(env.workspace.id)

    # guest yopiq bo'limni ko'rmaydi → uning vazifasi tasmaga tushmaydi
    guest_body = env.guest_client.get(url + "?page_size=50").json()
    assert "Maxfiy ish" not in [t["title"] for t in guest_body["results"]]
    assert guest_body["count"] == 7

    # ...admin esa ko'radi
    admin_titles = [
        t["title"] for t in env.admin_client.get(url + "?page_size=50").json()["results"]
    ]
    assert "Maxfiy ish" in admin_titles

    # bo'lim a'zosi qilinsa guest ham ko'radi (SpaceMember qo'shimcha ruxsat)
    SpaceMember.objects.create(
        space_id=private["id"], user=env.guest, access=SpaceAccess.VIEWER
    )
    opened = env.guest_client.get(url + "?page_size=50").json()
    assert "Maxfiy ish" in [t["title"] for t in opened["results"]]
    assert opened["count"] == 8

    # sahifalash konverti
    page = env.guest_client.get(url + "?page_size=3&page=2").json()
    assert set(page.keys()) == {"count", "next", "previous", "results"}
    assert page["count"] == 8 and len(page["results"]) == 3
    assert page["next"] and page["previous"]
    assert_error(env.guest_client.get(url + "?page=99"), 404, "not_found")
    assert_error(env.guest_client.get(url + "?page_size=101"), 400, "validation_error")

    # filtrlar shu yerda ham amal qiladi
    env.admin_client.patch(
        task_url(
            env.guest_client.get(url + "?q=T00").json()["results"][0]["id"]
        ),
        {"priority": "urgent"},
        format="json",
    )
    urgent = env.guest_client.get(url + "?priority=urgent").json()
    assert [t["title"] for t in urgent["results"]] == ["T00"]
    assert env.guest_client.get(url + "?q=maxfiy").json()["count"] == 1
    assert_error(env.guest_client.get(url + "?ordering=hax"), 400, "validation_error")


# ======================================================================= tags


def test_tags_from_another_workspace_are_rejected(env, empty_list):
    """`_validate_tags` — tag boshqa ish maydoniniki bo'lsa 400, jimgina
    biriktirilmaydi."""
    other = env.member_client.post("/api/v1/workspaces/", {"name": "Boshqa"}, format="json")
    assert other.status_code == 201, other.content
    other = other.json()
    foreign = env.member_client.post(
        f"/api/v1/workspaces/{other['id']}/tags/", {"name": "tashqi"}, format="json"
    )
    assert foreign.status_code == 201, foreign.content
    foreign = foreign.json()

    (task,) = make_tasks(env, empty_list, ["Ish"])
    denied = env.admin_client.patch(
        task_url(task["id"]), {"tag_ids": [foreign["id"]]}, format="json"
    )
    details = assert_error(denied, 400, "validation_error")["details"]
    assert "tag_ids" in details
    assert not Task.objects.get(pk=task["id"]).task_tags.exists()

    created = env.admin_client.post(
        tasks_url(empty_list.id),
        {"title": "Yangi", "tag_ids": [foreign["id"]]},
        format="json",
    )
    assert_error(created, 400, "validation_error")
    assert not Task.objects.filter(title="Yangi").exists()
