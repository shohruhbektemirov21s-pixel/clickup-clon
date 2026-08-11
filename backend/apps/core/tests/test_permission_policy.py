"""2026-08 ruxsat siyosati — `member` = "ko'radi + o'ziga biriktirilganini bajaradi".

Mahsulot talabi (aynan):

    "Admin va proyekt menejeri o'zgartirish/o'chirish imkoniyatiga ega bo'lsin.
     Qolganlar tasklarni ko'rishi. Biriktirilgan userlar esa ishlar/fayllarni
     joylash imkoniyatiga ega bo'lsin."

Ya'ni:

* `admin`/`owner` — hamma narsa (o'zgarmadi);
* `member` — o'qish + `task.create` + `task.update_assigned` + izoh/fayl;
  begona vazifani tahrirlay/o'chira olmaydi, bo'lim/jild/ro'yxat yarata olmaydi;
* **"proyekt menejeri"** alohida workspace roli EMAS — bu bo'lim darajasidagi
  `SpaceAccess.MANAGER` (`apps.core.access.SPACE_MANAGER_GRANTS`), ya'ni PM
  faqat **o'z bo'limi ichida** to'liq boshqaradi, bo'limning o'zini o'chira
  olmaydi (§F-5).

Bu fayl siyosatni REST darajasida qulflaydi — `permissions.py` dagi jadval
o'zgarsa shu testlar yiqiladi.
"""

import shutil
import tempfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.enums import SpaceAccess
from apps.tasks.models import Task
from apps.workspaces.models import SpaceMember
from conftest import assert_error

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------- utils


def tasks_url(list_id):
    return f"/api/v1/lists/{list_id}/tasks/"


def task_url(task_id, suffix=""):
    return f"/api/v1/tasks/{task_id}/{suffix}"


@pytest.fixture(autouse=True)
def media_root(settings):
    """Fayl yuklash testlari repo `media/` ini iflos qilmasin."""
    path = tempfile.mkdtemp(prefix="clickup-policy-")
    settings.MEDIA_ROOT = path
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def foreign_task(env):
    """Admin yaratgan, member'ga biriktirilmagan vazifa."""
    response = env.admin_client.post(
        tasks_url(env.list.id), {"title": "Begona vazifa"}, format="json"
    )
    assert response.status_code == 201, response.content
    return response.json()


@pytest.fixture
def assigned_task(env):
    """Admin yaratgan, **member'ga biriktirilgan** vazifa."""
    response = env.admin_client.post(
        tasks_url(env.list.id),
        {"title": "Mening ishim", "assignee_ids": [str(env.member.id)]},
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()


@pytest.fixture
def pm(env):
    """`member` ni `env.space` bo'limining menejeri (PM) qiladi."""
    SpaceMember.objects.create(
        space=env.space, user=env.member, access=SpaceAccess.MANAGER
    )
    return env.member_client


# --------------------------------------------------------------------- member


def test_member_cannot_edit_or_delete_someone_elses_task(env, foreign_task):
    """`task.update` / `task.delete` / `task.move` member'dan olib tashlandi."""
    edit = env.member_client.patch(
        task_url(foreign_task["id"]), {"title": "Ruxsatsiz tahrir"}, format="json"
    )
    assert_error(edit, 403, "permission_denied")

    move = env.member_client.patch(
        task_url(foreign_task["id"], "move/"),
        {"list_id": str(env.list.id), "status": foreign_task["status"]},
        format="json",
    )
    assert_error(move, 403, "permission_denied")

    removed = env.member_client.delete(task_url(foreign_task["id"]))
    assert_error(removed, 403, "permission_denied")

    # ...lekin ko'rish va izoh yozish qoladi.
    assert env.member_client.get(task_url(foreign_task["id"])).status_code == 200
    comment = env.member_client.post(
        task_url(foreign_task["id"], "comments/"),
        {"body_html": "<p>Ko'rdim</p>", "body_json": {"type": "doc"}},
        format="json",
    )
    assert comment.status_code == 201, comment.content


def test_member_can_edit_a_task_assigned_to_them(env, assigned_task):
    """`task.update_assigned` + `TaskAssignee` qatori → 200."""
    response = env.member_client.patch(
        task_url(assigned_task["id"]),
        {"title": "Bajarilmoqda", "priority": "high"},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["title"] == "Bajarilmoqda"

    # ...ammo o'chirish baribir mumkin emas: `task.delete` yo'q.
    assert_error(
        env.member_client.delete(task_url(assigned_task["id"])), 403, "permission_denied"
    )


def test_member_can_attach_a_file_to_their_assigned_task(env, assigned_task):
    """Talab: biriktirilgan user ishlar/fayllarni joylay olishi kerak."""
    response = env.member_client.post(
        f"/api/v1/tasks/{assigned_task['id']}/attachments/",
        {
            "file": SimpleUploadedFile(
                "hisobot.pdf", b"%PDF-1.7 salom", content_type="application/pdf"
            )
        },
        format="multipart",
    )
    assert response.status_code == 201, response.content
    assert response.json()["original_name"] == "hisobot.pdf"

    listing = env.member_client.get(f"/api/v1/tasks/{assigned_task['id']}/attachments/")
    assert listing.status_code == 200
    assert listing.json()["count"] == 1


def test_member_can_still_create_a_task(env):
    """`task.create` ataylab qoldirildi — a'zo ish qo'sha oladi."""
    response = env.member_client.post(
        tasks_url(env.list.id), {"title": "Yangi ish"}, format="json"
    )
    assert response.status_code == 201, response.content


@pytest.mark.parametrize(
    "label,method,url_fn,payload",
    [
        (
            "space_create",
            "post",
            lambda env: f"/api/v1/workspaces/{env.workspace.id}/spaces/",
            {"name": "Yangi bo'lim"},
        ),
        (
            "folder_create",
            "post",
            lambda env: f"/api/v1/spaces/{env.space.id}/folders/",
            {"name": "Yangi jild"},
        ),
        (
            "list_create",
            "post",
            lambda env: f"/api/v1/spaces/{env.space.id}/lists/",
            {"name": "Yangi ro'yxat"},
        ),
        (
            "space_update",
            "patch",
            lambda env: f"/api/v1/spaces/{env.space.id}/",
            {"name": "Qayta nomlangan"},
        ),
        (
            "list_update",
            "patch",
            lambda env: f"/api/v1/lists/{env.list.id}/",
            {"name": "Qayta nomlangan"},
        ),
        ("list_delete", "delete", lambda env: f"/api/v1/lists/{env.list.id}/", None),
    ],
)
def test_member_cannot_create_spaces_lists_or_folders(env, label, method, url_fn, payload):
    """Struktura endi faqat admin+ (yoki o'z bo'limidagi PM) qo'lida."""
    call = getattr(env.member_client, method)
    response = call(url_fn(env), payload, format="json") if payload else call(url_fn(env))
    assert_error(response, 403, "permission_denied")


def test_member_cannot_edit_or_delete_tags(env):
    """`tag.create` qoldi, `tag.update` / `tag.delete` olib tashlandi."""
    url = f"/api/v1/workspaces/{env.workspace.id}/tags/"
    created = env.member_client.post(url, {"name": "Backend"}, format="json")
    assert created.status_code == 201, created.content
    tag_id = created.json()["id"]

    assert_error(
        env.member_client.patch(f"/api/v1/tags/{tag_id}/", {"name": "X"}, format="json"),
        403,
        "permission_denied",
    )
    assert_error(
        env.member_client.delete(f"/api/v1/tags/{tag_id}/"), 403, "permission_denied"
    )


# ---------------------------------------------------------------------- admin


def test_admin_still_edits_and_deletes_everything(env):
    """Talab: admin o'zgartirish/o'chirish imkoniyatini to'liq saqlaydi."""
    task = env.member_client.post(
        tasks_url(env.list.id), {"title": "A'zo yaratgan"}, format="json"
    ).json()

    edited = env.admin_client.patch(
        task_url(task["id"]), {"title": "Admin tahriri"}, format="json"
    )
    assert edited.status_code == 200, edited.content

    folder = env.admin_client.post(
        f"/api/v1/spaces/{env.space.id}/folders/", {"name": "Admin jildi"}, format="json"
    )
    assert folder.status_code == 201, folder.content

    new_list = env.admin_client.post(
        f"/api/v1/spaces/{env.space.id}/lists/", {"name": "Admin ro'yxati"}, format="json"
    )
    assert new_list.status_code == 201, new_list.content

    assert env.admin_client.delete(task_url(task["id"])).status_code == 204
    cascade = env.admin_client.delete(
        f"/api/v1/folders/{folder.json()['id']}/?strategy=cascade"
    )
    assert cascade.status_code == 204, cascade.content
    gone = env.admin_client.delete(f"/api/v1/lists/{new_list.json()['id']}/")
    assert gone.status_code == 204, gone.content


# ------------------------------------------------------- space manager ("PM")


def test_space_manager_edits_and_deletes_inside_their_space(env, pm, foreign_task):
    """`SPACE_MANAGER_GRANTS` — PM o'z bo'limida admin kabi ishlaydi."""
    edited = pm.patch(task_url(foreign_task["id"]), {"title": "PM tahriri"}, format="json")
    assert edited.status_code == 200, edited.content

    folder = pm.post(
        f"/api/v1/spaces/{env.space.id}/folders/", {"name": "PM jildi"}, format="json"
    )
    assert folder.status_code == 201, folder.content

    new_list = pm.post(
        f"/api/v1/spaces/{env.space.id}/lists/", {"name": "PM ro'yxati"}, format="json"
    )
    assert new_list.status_code == 201, new_list.content

    renamed_space = pm.patch(
        f"/api/v1/spaces/{env.space.id}/", {"name": "PM bo'limi"}, format="json"
    )
    assert renamed_space.status_code == 200, renamed_space.content

    assert pm.delete(task_url(foreign_task["id"])).status_code == 204
    assert pm.delete(f"/api/v1/lists/{new_list.json()['id']}/").status_code == 204


def test_space_manager_cannot_delete_the_space_itself(env, pm):
    """§F-5: `space.delete`, `member.*`, `workspace.*` PM ga hech qachon o'tmaydi."""
    assert_error(pm.delete(f"/api/v1/spaces/{env.space.id}/"), 403, "permission_denied")
    assert_error(
        pm.post(
            f"/api/v1/workspaces/{env.workspace.id}/spaces/",
            {"name": "Yangi"},
            format="json",
        ),
        403,
        "permission_denied",
    )
    assert_error(
        pm.post(
            f"/api/v1/workspaces/{env.workspace.id}/invitations/",
            {"email": "x@client.com", "role": "member"},
            format="json",
        ),
        403,
        "permission_denied",
    )


def test_space_manager_authority_stops_at_their_space(env, pm):
    """PM huquqi **lokal**: boshqa bo'limda u oddiy member bo'lib qoladi."""
    other = env.admin_client.post(
        f"/api/v1/workspaces/{env.workspace.id}/spaces/",
        {"name": "Boshqa bo'lim"},
        format="json",
    ).json()
    denied = pm.post(
        f"/api/v1/spaces/{other['id']}/lists/", {"name": "Yo'q"}, format="json"
    )
    assert_error(denied, 403, "permission_denied")


# ---------------------------------------------------------------------- guest


def test_guest_can_still_read_tasks(env, foreign_task):
    """Guest ustuni o'zgarmadi: o'qiydi, izoh yozadi, yozishga urinsa 403."""
    detail = env.guest_client.get(task_url(foreign_task["id"]))
    assert detail.status_code == 200, detail.content

    listing = env.guest_client.get(tasks_url(env.list.id))
    assert listing.status_code == 200
    assert listing.json()["count"] >= 1

    attachments = env.guest_client.get(
        f"/api/v1/tasks/{foreign_task['id']}/attachments/"
    )
    assert attachments.status_code == 200

    assert_error(
        env.guest_client.post(tasks_url(env.list.id), {"title": "Yo'q"}, format="json"),
        403,
        "permission_denied",
    )
    assert_error(
        env.guest_client.patch(
            task_url(foreign_task["id"]), {"title": "Yo'q"}, format="json"
        ),
        403,
        "permission_denied",
    )


def test_policy_did_not_touch_the_data_model(env, foreign_task):
    """Siyosat faqat ruxsatga tegdi — migratsiya/ma'lumot o'zgarishi yo'q."""
    assert Task.objects.filter(list=env.list).count() == 1


# ------------------------------------------- jamoa ko'rinishi + email himoyasi


def members_url(env):
    return f"/api/v1/workspaces/{env.workspace.id}/members/"


def profile_url(env, user):
    return f"/api/v1/workspaces/{env.workspace.id}/members/{user.id}/profile/"


def test_guest_can_read_the_member_roster(env):
    """2026-08 (v4): `member.read` guest'da ham — jamoa hammaga ko'rinadi."""
    response = env.guest_client.get(members_url(env))
    assert response.status_code == 200, response.content
    assert [m["role"] for m in response.json()["results"]] == [
        "owner",
        "admin",
        "member",
        "guest",
    ]


def test_guest_can_open_a_member_profile(env):
    response = env.guest_client.get(profile_url(env, env.member))
    assert response.status_code == 200, response.content
    assert response.json()["user"]["full_name"] == env.member.full_name


def test_guest_sees_names_but_not_emails(env, assigned_task):
    """AppSec O-1: mehmon ism/avatarni ko'radi, begona `email` — `null`."""
    roster = env.guest_client.get(members_url(env)).json()["results"]
    others = [m for m in roster if m["user"]["id"] != str(env.guest.id)]
    assert others, roster
    for row in others:
        assert row["user"]["email"] is None, row
        assert row["user"]["full_name"], row  # ism ochiq qoladi
        assert row["user"]["avatar_color"], row

    # Vazifa payload'i ham himoyalangan: assignee / created_by / watchers.
    task = env.guest_client.get(task_url(assigned_task["id"])).json()
    assert task["assignees"][0]["full_name"] == env.member.full_name
    assert task["assignees"][0]["email"] is None
    assert task["created_by"]["email"] is None
    assert all(w["email"] is None for w in task["watchers"])

    # Izoh muallifi ham.
    env.admin_client.post(
        task_url(assigned_task["id"], "comments/"),
        {"body_html": "<p>Salom</p>", "body_json": {"type": "doc"}},
        format="json",
    )
    comments = env.guest_client.get(task_url(assigned_task["id"], "comments/")).json()
    assert comments["results"][0]["author"]["email"] is None

    # Profil sahifasi ham.
    profile = env.guest_client.get(profile_url(env, env.member)).json()
    assert profile["user"]["email"] is None


def test_guest_sees_own_email(env):
    """O'z emailini yashirish ma'nosiz — profil sahifasi buzilardi."""
    roster = env.guest_client.get(members_url(env)).json()["results"]
    me = next(m for m in roster if m["user"]["id"] == str(env.guest.id))
    assert me["user"]["email"] == env.guest.email

    own_profile = env.guest_client.get(profile_url(env, env.guest)).json()
    assert own_profile["user"]["email"] == env.guest.email

    # `/me/` da a'zolik konteksti yo'q — maskalanmaydi.
    assert env.guest_client.get("/api/v1/me/").json()["email"] == env.guest.email


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_member_and_admin_still_see_emails(env, role, assigned_task):
    client = getattr(env, f"{role}_client")
    roster = client.get(members_url(env)).json()["results"]
    assert all(row["user"]["email"] for row in roster), roster

    task = client.get(task_url(assigned_task["id"])).json()
    assert task["assignees"][0]["email"] == env.member.email
    assert task["created_by"]["email"] == env.admin.email
