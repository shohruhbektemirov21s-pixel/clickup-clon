"""Bo'lim a'zolari (PM biriktiruvi) — docs/DESIGN_PERMISSIONS.md §D.6 / §B.5 / F-5.

Bu fayl bitta savolga javob beradi: *"loyiha menejeri o'z bo'limiga mos
odamlarni tanlay oladimi va bunda hech kim o'z vakolatidan oshib ketmaydimi?"*

Uch invariant tekshiriladi:

1. **Lokal manager = lokal PM.** `SpaceMember(access=manager)` faqat shu bo'lim
   ichida `SPACE_MANAGER_GRANTS` beradi — bo'limni o'chirish, a'zolarni
   workspace'dan chiqarish yoki teglarni boshqarish HECH QACHON kirmaydi (F-5).
2. **Eng past huquq g'olib.** `viewer` qatori workspace rolidan ustun: admin
   ham `viewer` bo'lsa bo'lim ichida yoza olmaydi (§B.5).
3. **Mavjudlik oshkor qilinmaydi.** Ko'rinmaydigan bo'lim → 404, ruxsat yo'q →
   403, noto'g'ri `user_id` → 400 (§C.4 / §D.6 xato jadvali).

FIXTURE SIYOSATI: bo'lim/ro'yxat/vazifa **servis qatlami** orqali yaratiladi,
API orqali emas. Shunda testlar `DEFAULT_MATRIX` ning kelajakdagi
o'zgarishlariga (masalan `member` endi bo'lim yarata olmasligi) bog'liq bo'lmaydi
va faqat o'z mavzusini o'lchaydi.
"""

import pytest

from apps.core.enums import SpaceAccess, SpaceMemberSource
from apps.tasks import services as task_services
from apps.workspaces import services
from apps.workspaces.models import SpaceMember, TaskList
from conftest import assert_error

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------- helpers


def members_url(space_id):
    return f"/api/v1/spaces/{space_id}/members/"


def member_url(space_id, user_id):
    return f"/api/v1/spaces/{space_id}/members/{user_id}/"


def bulk_url(space_id):
    return f"/api/v1/spaces/{space_id}/members/bulk/"


def grant(space, user, access, *, source=SpaceMemberSource.MANUAL):
    row, _ = SpaceMember.objects.update_or_create(
        space=space, user=user, defaults={"access": access, "source": source}
    )
    return row


@pytest.fixture
def space(env):
    """Ochiq bo'lim. Yaratuvchi (admin) avtomatik `manager` bo'ladi (§B.6)."""
    return services.create_space(env.workspace, env.admin, name="Loyiha A")


@pytest.fixture
def private_space(env):
    return services.create_space(env.workspace, env.admin, name="Yopiq loyiha", is_private=True)


@pytest.fixture
def task_list(space, env):
    return TaskList.objects.create(
        space=space, name="Sprint 1", position="n", created_by=env.admin
    )


# ------------------------------------------------------------------ PM qo'shadi


def test_local_manager_can_add_member(env, space):
    """Oddiy `member` bo'lim menejeri qilinsa, bo'limga odam qo'sha oladi (F-5)."""
    grant(space, env.member, SpaceAccess.MANAGER)

    response = env.member_client.post(
        members_url(space.id),
        {"user_id": str(env.guest.id), "access": "contributor"},
        format="json",
    )

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["user"]["id"] == str(env.guest.id)
    assert body["access"] == "contributor"
    assert body["source"] == "manual"
    assert body["added_by_id"] == str(env.member.id)
    assert body["space_id"] == str(space.id)
    assert SpaceMember.objects.filter(space=space, user=env.guest).exists()


def test_plain_member_cannot_add_member(env, space):
    """Lokal qator yo'q → workspace roli hal qiladi; `member` da manage yo'q → 403."""
    response = env.member_client.post(
        members_url(space.id), {"user_id": str(env.guest.id)}, format="json"
    )
    assert_error(response, 403, "permission_denied")
    assert not SpaceMember.objects.filter(space=space, user=env.guest).exists()


def test_admin_can_add_member_without_local_row(env, space):
    """Workspace `space.manage_members` (default: admin) lokal qatorsiz ham yetadi."""
    response = env.admin_client.post(
        members_url(space.id), {"user_id": str(env.member.id)}, format="json"
    )
    assert response.status_code == 201, response.content
    # `access` berilmagan → contributor (§D.6 default).
    assert response.json()["access"] == "contributor"


def test_any_visible_member_can_read_the_roster(env, space):
    """O'qish uchun alohida ruxsat yo'q — bo'limni ko'rgan odam jamoani ko'radi."""
    grant(space, env.member, SpaceAccess.VIEWER)
    response = env.member_client.get(members_url(space.id))
    assert response.status_code == 200, response.content
    user_ids = {row["user"]["id"] for row in response.json()["results"]}
    assert str(env.member.id) in user_ids
    # Menejerlar tepada (ACCESS_RANK), alifbo emas.
    assert response.json()["results"][0]["access"] == "manager"


# ------------------------------------------------------- eng past huquq g'olib


def test_viewer_cannot_write_inside_the_space(env, space):
    """§B.5 — `viewer` qatori workspace rolidan USTUN: admin ham yoza olmaydi."""
    grant(space, env.admin, SpaceAccess.VIEWER)

    create_list = env.admin_client.post(
        f"/api/v1/spaces/{space.id}/lists/", {"name": "Yangi ro'yxat"}, format="json"
    )
    assert_error(create_list, 403, "permission_denied")

    rename_space = env.admin_client.patch(
        f"/api/v1/spaces/{space.id}/", {"name": "Boshqa nom"}, format="json"
    )
    assert_error(rename_space, 403, "permission_denied")

    add_member = env.admin_client.post(
        members_url(space.id), {"user_id": str(env.member.id)}, format="json"
    )
    assert_error(add_member, 403, "permission_denied")

    # Lekin o'qish qoladi.
    assert env.admin_client.get(members_url(space.id)).status_code == 200


def test_viewer_keeps_read_access_to_tasks(env, space, task_list):
    grant(space, env.guest, SpaceAccess.VIEWER)
    task_services.create_task(task_list, {"title": "Ko'rinadigan vazifa"}, env.admin)
    response = env.guest_client.get(f"/api/v1/lists/{task_list.id}/tasks/")
    assert response.status_code == 200, response.content


# ---------------------------------------------------------- manager ichkarida


def test_manager_can_edit_inside_the_space_but_not_delete_it(env, space, task_list):
    """F-5: lokal manager `list.*` / `space.update` oladi, `space.delete` — YO'Q."""
    grant(space, env.member, SpaceAccess.MANAGER)

    created = env.member_client.post(
        f"/api/v1/spaces/{space.id}/lists/", {"name": "PM ro'yxati"}, format="json"
    )
    assert created.status_code == 201, created.content

    renamed = env.member_client.patch(
        f"/api/v1/lists/{created.json()['id']}/", {"name": "Qayta nomlandi"}, format="json"
    )
    assert renamed.status_code == 200, renamed.content

    deleted = env.member_client.delete(f"/api/v1/lists/{created.json()['id']}/")
    assert deleted.status_code == 204, deleted.content

    updated_space = env.member_client.patch(
        f"/api/v1/spaces/{space.id}/", {"name": "PM bo'limi"}, format="json"
    )
    assert updated_space.status_code == 200, updated_space.content

    # Bo'limning O'ZINI o'chirish lokal manager'ga hech qachon berilmaydi.
    destroyed = env.member_client.delete(
        f"/api/v1/spaces/{space.id}/", {"confirm_name": "PM bo'limi"}, format="json"
    )
    assert_error(destroyed, 403, "permission_denied")


def test_manager_cannot_touch_workspace_members(env, space):
    """`member.*` `SPACE_MANAGER_GRANTS` ga kirmaydi — PM odamni ishdan haydolmaydi."""
    grant(space, env.member, SpaceAccess.MANAGER)
    response = env.member_client.delete(
        f"/api/v1/workspaces/{env.workspace.id}/members/{env.guest.id}/"
    )
    assert_error(response, 403, "permission_denied")


# ---------------------------------------------------------------- PATCH/DELETE


def test_patch_changes_access_and_delete_removes_the_row(env, space):
    grant(space, env.member, SpaceAccess.MANAGER)
    env.member_client.post(
        members_url(space.id), {"user_id": str(env.guest.id)}, format="json"
    )

    patched = env.member_client.patch(
        member_url(space.id, env.guest.id), {"access": "viewer"}, format="json"
    )
    assert patched.status_code == 200, patched.content
    assert patched.json()["access"] == "viewer"

    removed = env.member_client.delete(member_url(space.id, env.guest.id))
    assert removed.status_code == 204, removed.content
    assert not SpaceMember.objects.filter(space=space, user=env.guest).exists()


def test_patch_unknown_space_member_is_404(env, space):
    response = env.admin_client.patch(
        member_url(space.id, env.guest.id), {"access": "viewer"}, format="json"
    )
    assert_error(response, 404, "not_found")


def test_patch_rejects_unknown_access_value(env, space):
    grant(space, env.guest, SpaceAccess.CONTRIBUTOR)
    response = env.admin_client.patch(
        member_url(space.id, env.guest.id), {"access": "superuser"}, format="json"
    )
    assert_error(response, 400, "validation_error")


# ------------------------------------------------------------------- xatolar


def test_user_from_another_workspace_is_400(env, space):
    """§D.6: `user_id` workspace a'zosi emas → 400 (404 emas — bo'lim ko'rinadi)."""
    response = env.admin_client.post(
        members_url(space.id), {"user_id": str(env.outsider.id)}, format="json"
    )
    error = assert_error(response, 400, "validation_error")
    assert "user_id" in error["details"]


def test_duplicate_space_member_is_409(env, space):
    env.admin_client.post(members_url(space.id), {"user_id": str(env.member.id)}, format="json")
    response = env.admin_client.post(
        members_url(space.id), {"user_id": str(env.member.id)}, format="json"
    )
    assert_error(response, 409, "conflict")
    assert SpaceMember.objects.filter(space=space, user=env.member).count() == 1


def test_last_manager_of_a_private_space_cannot_be_removed(env, private_space):
    """§D.6 `last_manager` — yopiq bo'lim boshqaruvsiz qulflanib qolmasin."""
    assert (
        SpaceMember.objects.filter(
            space=private_space, access=SpaceAccess.MANAGER
        ).count()
        == 1
    )

    response = env.owner_client.delete(member_url(private_space.id, env.admin.id))
    error = assert_error(response, 409, "conflict")
    assert error["details"]["reason"] == "last_manager"

    demote = env.owner_client.patch(
        member_url(private_space.id, env.admin.id), {"access": "contributor"}, format="json"
    )
    assert assert_error(demote, 409, "conflict")["details"]["reason"] == "last_manager"

    # Ikkinchi menejer paydo bo'lsa cheklov yo'qoladi.
    grant(private_space, env.member, SpaceAccess.MANAGER)
    assert env.owner_client.delete(member_url(private_space.id, env.admin.id)).status_code == 204


def test_last_manager_guard_does_not_apply_to_open_spaces(env, space):
    """Ochiq bo'limni workspace admini baribir boshqaradi — cheklov ortiqcha."""
    response = env.owner_client.delete(member_url(space.id, env.admin.id))
    assert response.status_code == 204, response.content


def test_invisible_space_is_404_everywhere(env, private_space):
    """Yopiq bo'lim mehmonga umuman mavjud emas (§C.4) — 403 EMAS, 404."""
    for response in (
        env.guest_client.get(members_url(private_space.id)),
        env.guest_client.post(
            members_url(private_space.id), {"user_id": str(env.member.id)}, format="json"
        ),
        env.guest_client.patch(
            member_url(private_space.id, env.admin.id), {"access": "viewer"}, format="json"
        ),
        env.guest_client.delete(member_url(private_space.id, env.admin.id)),
        env.guest_client.post(bulk_url(private_space.id), {"add": []}, format="json"),
    ):
        assert_error(response, 404, "not_found")


def test_outsider_never_sees_the_space(env, space):
    assert_error(env.outsider_client.get(members_url(space.id)), 404, "not_found")


# ---------------------------------------------------------------------- bulk


def test_bulk_adds_and_removes_in_one_transaction(env, space):
    grant(space, env.member, SpaceAccess.MANAGER)
    grant(space, env.guest, SpaceAccess.CONTRIBUTOR)

    response = env.member_client.post(
        bulk_url(space.id),
        {
            "add": [
                {"user_id": str(env.owner.id), "access": "contributor"},
                {"user_id": str(env.guest.id), "access": "viewer"},  # upsert
            ],
            "remove": [str(env.admin.id)],
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["added"] == 1  # owner yangi, guest allaqachon a'zo edi
    assert body["removed"] == 1
    by_user = {row["user"]["id"]: row["access"] for row in body["results"]}
    assert by_user[str(env.guest.id)] == "viewer"
    assert by_user[str(env.owner.id)] == "contributor"
    assert str(env.admin.id) not in by_user


def test_bulk_is_all_or_nothing(env, space):
    """Bitta yaroqsiz `user_id` butun partiyani bekor qiladi — qisman yozuv yo'q."""
    grant(space, env.member, SpaceAccess.MANAGER)
    before = set(SpaceMember.objects.filter(space=space).values_list("user_id", flat=True))

    response = env.member_client.post(
        bulk_url(space.id),
        {
            "add": [
                {"user_id": str(env.guest.id), "access": "contributor"},
                {"user_id": str(env.outsider.id), "access": "contributor"},
            ],
            "remove": [],
        },
        format="json",
    )

    assert_error(response, 400, "validation_error")
    after = set(SpaceMember.objects.filter(space=space).values_list("user_id", flat=True))
    assert after == before


def test_bulk_rejects_the_same_user_in_add_and_remove(env, space):
    grant(space, env.member, SpaceAccess.MANAGER)
    response = env.member_client.post(
        bulk_url(space.id),
        {
            "add": [{"user_id": str(env.guest.id), "access": "viewer"}],
            "remove": [str(env.guest.id)],
        },
        format="json",
    )
    assert_error(response, 400, "validation_error")


def test_bulk_respects_the_last_manager_guard(env, private_space):
    response = env.owner_client.post(
        bulk_url(private_space.id),
        {"add": [], "remove": [str(env.admin.id)]},
        format="json",
    )
    assert assert_error(response, 409, "conflict")["details"]["reason"] == "last_manager"


def test_bulk_requires_manage_permission(env, space):
    response = env.member_client.post(
        bulk_url(space.id),
        {"add": [{"user_id": str(env.guest.id), "access": "viewer"}]},
        format="json",
    )
    assert_error(response, 403, "permission_denied")


# ------------------------------------------------------------------ AD-7


@pytest.fixture
def private_list(env, private_space):
    return TaskList.objects.create(
        space=private_space, name="Yopiq ro'yxat", position="n", created_by=env.admin
    )


def test_assignee_gets_auto_space_member(env, private_space, private_list):
    """AD-7 — biriktirilgan odam o'z ishini ko'rishi SHART."""
    assert not SpaceMember.objects.filter(space=private_space, user=env.guest).exists()

    task_services.create_task(
        private_list,
        {"title": "Mehmon uchun vazifa", "assignee_ids": [str(env.guest.id)]},
        env.admin,
    )

    row = SpaceMember.objects.get(space=private_space, user=env.guest)
    assert row.access == SpaceAccess.VIEWER
    assert row.source == SpaceMemberSource.AUTO_ASSIGNEE


def test_assignee_of_a_private_space_task_can_read_it(env, private_list):
    """AD-7 ning maqsadi: mehmon yopiq bo'limdagi o'z vazifasini ko'ra olsin."""
    task = task_services.create_task(
        private_list,
        {"title": "Mehmonning ishi", "assignee_ids": [str(env.guest.id)]},
        env.admin,
    )

    response = env.guest_client.get(f"/api/v1/tasks/{task.id}/")
    assert response.status_code == 200, response.content


def test_auto_assignee_never_downgrades_an_existing_row(env, private_space, private_list):
    """PM ni `viewer` ga tushirib yubormaydi — mavjud qator daxlsiz."""
    grant(private_space, env.member, SpaceAccess.MANAGER)
    task = task_services.create_task(private_list, {"title": "PM vazifasi"}, env.admin)
    task_services.update_task(task, {"assignee_ids": [str(env.member.id)]}, env.admin)

    assert (
        SpaceMember.objects.get(space=private_space, user=env.member).access
        == SpaceAccess.MANAGER
    )


def test_auto_assignee_does_not_demote_someone_who_already_sees_the_space(
    env, space, task_list
):
    """AD-7 ning ASOSIY cheklovi (§B.5 "eng past huquq g'olib" bilan to'qnashuv).

    Ochiq bo'limni mehmon allaqachon ko'radi. Unga `viewer` qatori yozilsa,
    biriktirish uni bo'lim ichida QULFLAB qo'yardi: o'ziga biriktirilgan
    vazifani ham tahrirlay olmasdi. Shuning uchun qator yozilmaydi.
    """
    task = task_services.create_task(
        task_list,
        {"title": "Mehmonning ochiq vazifasi", "assignee_ids": [str(env.guest.id)]},
        env.admin,
    )

    assert not SpaceMember.objects.filter(space=space, user=env.guest).exists()
    edited = env.guest_client.patch(
        f"/api/v1/tasks/{task.id}/", {"title": "Mehmon tahriri"}, format="json"
    )
    assert edited.status_code == 200, edited.content


def test_auto_assignee_does_not_demote_an_admin_in_a_private_space(env, private_space, private_list):
    """Admin `space.read_private` bilan ko'radi — unga viewer qatori yozilmaydi."""
    task_services.create_task(
        private_list,
        {"title": "Admin ishi", "assignee_ids": [str(env.admin.id)]},
        env.owner,
    )
    # Admin bo'lim yaratuvchisi sifatida `manager` bo'lib qoladi, viewer emas.
    assert (
        SpaceMember.objects.get(space=private_space, user=env.admin).access
        == SpaceAccess.MANAGER
    )


# ------------------------------------------------- workspace'dan chiqarish


def test_removing_a_workspace_member_drops_their_space_rows(env, space):
    """§B.4 invarianti: `SpaceMember` `WorkspaceMember` dan uzoq yashamaydi."""
    grant(space, env.member, SpaceAccess.MANAGER)

    response = env.owner_client.delete(
        f"/api/v1/workspaces/{env.workspace.id}/members/{env.member.id}/"
    )

    assert response.status_code == 204, response.content
    assert not SpaceMember.objects.filter(user=env.member).exists()
