"""2026-08 AppSec auditining qolgan uchta topilmasi — regressiya qulfi.

Har bir blok bitta topilmani qulflaydi:

**Y-1 · Chiqarilgan a'zoning WebSocket'i.** Consumer a'zolikni faqat
`connect()` da bir marta tekshiradi, ya'ni REST allaqachon `404` qaytarayotgan
bo'lsa ham ochiq soket `task.*` / `comment.*` / `attachment.*` / `list.updated`
freymlarini oqizishda davom etardi. `_remove_member()` endi `commit` dan keyin
`access.revoked` chiqaradi; `space_id=None` bo'lgani uchun u ikkala
consumer'ni ham (ro'yxat va ish maydoni) 4403 bilan yopadi.

**Y-2 · `assignee_ids` orqali `task.assign` ni chetlab o'tish.** `task.assign`
katalogda admin-only, lekin `POST lists/{id}/tasks/` faqat `task.create` ni,
`PATCH tasks/{id}/` esa faqat `require_task_editor` ni tekshirardi. Eskalatsiya
zanjiri: yopiq bo'limdagi vazifaga biriktirilgan past huquqli foydalanuvchi
begona odamni assignee qilib qo'shadi → `_grant_assignee_space_access` unga
`SpaceMember(viewer)` yozadi → begona odam **butun yopiq bo'limni** o'qiy
oladi, ya'ni `space.manage_members` (admin-only) `task.update_assigned`
(guest-level) orqali aylanib o'tiladi. Ikki qavat yopildi: view'da
`task.assign`, servisda `space.manage_members`.

**Y-3 · `is_private` ni oddiy `space.update` bilan o'zgartirish.**
`space.update` `SPACE_MANAGER_GRANTS` ichida, ya'ni bo'lim menejeri (PM) yopiq
bo'limni butun jamoaga ocha olardi. Yangi admin-only kod
`space.change_visibility` (katalog v5) buni ajratdi.
"""

import pytest

from apps.core.enums import SpaceAccess, SpaceMemberSource, WorkspaceRole
from apps.realtime import events as realtime_events
from apps.tasks import services as task_services
from apps.workspaces import services
from apps.workspaces.models import RolePermission, SpaceMember, TaskList, WorkspaceMember
from conftest import assert_error, client_for, make_user

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------- helpers


def space_url(space_id):
    return f"/api/v1/spaces/{space_id}/"


def task_url(task_id):
    return f"/api/v1/tasks/{task_id}/"


def tasks_url(list_id):
    return f"/api/v1/lists/{list_id}/tasks/"


def grant_space(space, user, access):
    row, _ = SpaceMember.objects.update_or_create(
        space=space, user=user, defaults={"access": access, "source": SpaceMemberSource.MANUAL}
    )
    return row


def grant_code(workspace, role, code):
    """Matritsaga bitta kod qo'shadi va keshni bekor qiladi (R3)."""
    from apps.core.access import bump_permissions_version

    RolePermission.objects.update_or_create(
        workspace=workspace, role=role, permission=code, defaults={"allowed": True}
    )
    bump_permissions_version(workspace)


@pytest.fixture
def revocations(monkeypatch):
    """`emit_access_revoked` josusi — chaqiruvlar argumentlari bilan."""
    calls = []

    def spy(user_id, *, workspace_id, space_id=None):
        calls.append(
            {
                "user_id": str(user_id),
                "workspace_id": str(workspace_id),
                "space_id": space_id,
            }
        )

    monkeypatch.setattr(realtime_events, "emit_access_revoked", spy)
    return calls


@pytest.fixture
def private_space(env):
    """Yopiq bo'lim; yaratuvchi (admin) avtomatik `manager` bo'ladi (§B.6)."""
    return services.create_space(
        env.workspace, env.admin, name="Yopiq loyiha", is_private=True
    )


@pytest.fixture
def private_list(env, private_space):
    return TaskList.objects.create(
        space=private_space, name="Yopiq ro'yxat", position="n", created_by=env.admin
    )


@pytest.fixture
def stranger(env):
    """Yopiq bo'limga hech qanday aloqasi yo'q ish maydoni mehmoni."""
    user = make_user("stranger@test.dev", "Stranger Five")
    WorkspaceMember.objects.create(
        workspace=env.workspace, user=user, role=WorkspaceRole.GUEST
    )
    user.client = client_for(user)
    return user


# =========================================================== Y-1 · access.revoked


def test_removing_a_member_emits_access_revoked(
    env, revocations, django_capture_on_commit_callbacks
):
    """A'zolikni o'chirish ochiq soketlarni ham yopishi SHART (kontrakt §4)."""
    with django_capture_on_commit_callbacks(execute=True):
        response = env.owner_client.delete(
            f"/api/v1/workspaces/{env.workspace.id}/members/{env.member.id}/"
        )
    assert response.status_code == 204, response.content

    assert len(revocations) == 1, revocations
    call = revocations[0]
    assert call["user_id"] == str(env.member.id)
    assert call["workspace_id"] == str(env.workspace.id)
    # `space_id=None` — bu ish maydoni darajasidagi bekor qilish.
    assert call["space_id"] is None


def test_leaving_the_workspace_emits_access_revoked(
    env, revocations, django_capture_on_commit_callbacks
):
    """`members/leave/` ham xuddi shu yo'ldan (`_remove_member`) o'tadi."""
    with django_capture_on_commit_callbacks(execute=True):
        response = env.member_client.post(
            f"/api/v1/workspaces/{env.workspace.id}/members/leave/"
        )
    assert response.status_code == 204, response.content

    assert len(revocations) == 1, revocations
    assert revocations[0]["user_id"] == str(env.member.id)
    assert revocations[0]["workspace_id"] == str(env.workspace.id)
    assert revocations[0]["space_id"] is None


def test_revocation_is_emitted_only_after_commit(env, revocations):
    """`on_commit` — tranzaksiya yiqilsa soket yopilmasligi kerak."""
    response = env.owner_client.delete(
        f"/api/v1/workspaces/{env.workspace.id}/members/{env.guest.id}/"
    )
    assert response.status_code == 204, response.content
    # Test tranzaksiyasi hech qachon commit bo'lmaydi → callback ishlamaydi.
    assert revocations == []


def test_workspace_wide_revocation_closes_both_consumers():
    """`space_id=None` ikkala consumer'ni ham qamraydi (`revocation_applies`)."""
    from apps.realtime.consumers import ListConsumer, WorkspaceConsumer

    workspace_socket = WorkspaceConsumer.__new__(WorkspaceConsumer)
    workspace_socket.workspace_id = "W1"
    workspace_socket.space_id = None

    list_socket = ListConsumer.__new__(ListConsumer)
    list_socket.workspace_id = "W1"
    list_socket.space_id = "S1"

    workspace_wide = {"workspace_id": "W1", "space_id": None}
    assert workspace_socket.revocation_applies(workspace_wide) is True
    assert list_socket.revocation_applies(workspace_wide) is True

    # Boshqa ish maydoni — tegmaydi.
    other = {"workspace_id": "W2", "space_id": None}
    assert workspace_socket.revocation_applies(other) is False
    assert list_socket.revocation_applies(other) is False

    # Bo'lim darajasidagi bekor qilish o'z bo'limining ro'yxat soketini yopadi.
    # (Yon panel soketining bo'lim darajasidagi xatti-harakati `apps/realtime`
    # ning o'z mavzusi — bu test faqat ish maydoni darajasini qulflaydi.)
    assert list_socket.revocation_applies({"workspace_id": "W1", "space_id": "S1"}) is True


# ============================================================ Y-2 · task.assign


@pytest.fixture
def assigned_task(env):
    """Admin yaratgan, `member` ga biriktirilgan vazifa (ochiq bo'limda)."""
    response = env.admin_client.post(
        tasks_url(env.list.id),
        {"title": "Mening ishim", "assignee_ids": [str(env.member.id)]},
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()


def test_member_cannot_change_assignees(env, assigned_task):
    """`task.update_assigned` tahrirga yetadi, biriktirishga — YO'Q."""
    denied = env.member_client.patch(
        task_url(assigned_task["id"]),
        {"assignee_ids": [str(env.member.id), str(env.guest.id)]},
        format="json",
    )
    assert_error(denied, 403, "permission_denied")

    from apps.tasks.models import Task

    task = Task.objects.get(pk=assigned_task["id"])
    assert set(task.task_assignees.values_list("user_id", flat=True)) == {env.member.id}


@pytest.fixture
def shared_task(env):
    """Admin yaratgan, `member` VA `guest` ga biriktirilgan vazifa."""
    response = env.admin_client.post(
        tasks_url(env.list.id),
        {"title": "Umumiy ish", "assignee_ids": [str(env.member.id), str(env.guest.id)]},
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()


def test_member_cannot_unassign_a_colleague(env, shared_task):
    """Hamkasbni jimgina yechib tashlash ham `task.assign` talab qiladi."""
    denied = env.member_client.patch(
        task_url(shared_task["id"]), {"assignee_ids": [str(env.member.id)]}, format="json"
    )
    assert_error(denied, 403, "permission_denied")


def test_member_may_unassign_only_themselves(env, shared_task):
    """Ataylab o'yilgan teshik: "vazifani tashlab ketaman" oqimi.

    Farq FAQAT chaqiruvchining o'zi bo'lsa `task.assign` talab qilinmaydi —
    bu hech kimga yangi kirish bermaydi (`_grant_assignee_space_access`
    bo'limni allaqachon ko'rayotgan odamga qator yozmaydi).
    """
    response = env.member_client.patch(
        task_url(shared_task["id"]), {"assignee_ids": [str(env.guest.id)]}, format="json"
    )
    assert response.status_code == 200, response.content
    assert [a["id"] for a in response.json()["assignees"]] == [str(env.guest.id)]


def test_member_can_patch_when_the_assignee_set_is_unchanged(env, assigned_task):
    """Frontend butun obyektni qaytarib yuboradi — bu PATCH sinmasligi SHART."""
    response = env.member_client.patch(
        task_url(assigned_task["id"]),
        {"title": "Bajarilmoqda", "assignee_ids": [str(env.member.id)]},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["title"] == "Bajarilmoqda"


def test_member_cannot_create_a_task_with_assignees(env):
    """`task.create` bor, `task.assign` yo'q → yaratishda biriktirib bo'lmaydi."""
    denied = env.member_client.post(
        tasks_url(env.list.id),
        {"title": "Yangi ish", "assignee_ids": [str(env.guest.id)]},
        format="json",
    )
    assert_error(denied, 403, "permission_denied")

    # ...biriktirmasdan yaratish esa avvalgidek ishlaydi.
    allowed = env.member_client.post(
        tasks_url(env.list.id), {"title": "Yangi ish"}, format="json"
    )
    assert allowed.status_code == 201, allowed.content


def test_admin_can_change_assignees(env, assigned_task):
    response = env.admin_client.patch(
        task_url(assigned_task["id"]),
        {"assignee_ids": [str(env.guest.id)]},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert [a["id"] for a in response.json()["assignees"]] == [str(env.guest.id)]


def test_guest_cannot_assign_a_stranger_to_a_private_space_task(
    env, private_space, private_list, stranger
):
    """Eskalatsiya zanjirining o'zi: guest → begona odam → yopiq bo'lim ochiladi."""
    # Guest bo'lim ichida `contributor`, ya'ni o'ziga biriktirilgan vazifani
    # tahrirlay oladi (viewer bo'lsa hamma yozish allaqachon kesilardi).
    grant_space(private_space, env.guest, SpaceAccess.CONTRIBUTOR)
    task = task_services.create_task(
        private_list,
        {"title": "Mehmonning ishi", "assignee_ids": [str(env.guest.id)]},
        env.admin,
    )
    # Boshlang'ich holat: begona odam bo'limni ko'rmaydi.
    assert not SpaceMember.objects.filter(space=private_space, user=stranger).exists()
    assert env.guest_client.get(task_url(task.id)).status_code == 200

    denied = env.guest_client.patch(
        task_url(task.id),
        {"assignee_ids": [str(env.guest.id), str(stranger.id)]},
        format="json",
    )
    assert_error(denied, 403, "permission_denied")

    # Eng muhimi: hech qanday `SpaceMember` yozilmadi, bo'lim yopiq qoldi.
    assert not SpaceMember.objects.filter(space=private_space, user=stranger).exists()
    assert stranger.client.get(task_url(task.id)).status_code == 404


def test_assigning_someone_who_cannot_see_the_space_needs_manage_members(
    env, private_space, private_list, stranger
):
    """Servis qavati: `task.assign` bor, `space.manage_members` yo'q → 400.

    Bu ikkinchi mudofaa chizig'i — view tekshiruvi kelajakda chetlab
    o'tilsa ham `SpaceMember` yozilmaydi.
    """
    grant_code(env.workspace, WorkspaceRole.MEMBER, "task.assign")
    task = task_services.create_task(
        private_list,
        {"title": "A'zoning ishi", "assignee_ids": [str(env.member.id)]},
        env.admin,
    )

    response = env.member_client.patch(
        task_url(task.id),
        {"assignee_ids": [str(env.member.id), str(stranger.id)]},
        format="json",
    )
    error = assert_error(response, 400, "validation_error")
    assert "assignee_ids" in error["details"]

    assert not SpaceMember.objects.filter(space=private_space, user=stranger).exists()
    # Biriktirish ham qaytarildi (tranzaksiya butunligicha rollback bo'ldi).
    assert set(task.task_assignees.values_list("user_id", flat=True)) == {env.member.id}


def test_admin_assigning_a_stranger_still_grants_space_access(
    env, private_space, private_list, stranger
):
    """AD-7 buzilmadi: `space.manage_members` ga ega aktyor uchun grant ishlaydi."""
    task = task_services.create_task(private_list, {"title": "Admin ishi"}, env.admin)

    response = env.admin_client.patch(
        task_url(task.id), {"assignee_ids": [str(stranger.id)]}, format="json"
    )
    assert response.status_code == 200, response.content

    row = SpaceMember.objects.get(space=private_space, user=stranger)
    assert row.access == SpaceAccess.VIEWER
    assert row.source == SpaceMemberSource.AUTO_ASSIGNEE
    assert stranger.client.get(task_url(task.id)).status_code == 200


# ===================================================== Y-3 · space.change_visibility


def test_space_manager_cannot_open_a_private_space(env, private_space):
    """F-5: PM bo'lim ICHIDA hokim, uning chegarasini o'zgartira olmaydi."""
    grant_space(private_space, env.member, SpaceAccess.MANAGER)

    denied = env.member_client.patch(
        space_url(private_space.id), {"is_private": False}, format="json"
    )
    assert_error(denied, 403, "permission_denied")

    private_space.refresh_from_db()
    assert private_space.is_private is True


def test_space_manager_cannot_close_an_open_space(env):
    """Teskari yo'nalish ham yopiq: PM guest'larni bo'limdan chiqarib yubormasin."""
    space = services.create_space(env.workspace, env.admin, name="Ochiq loyiha")
    grant_space(space, env.member, SpaceAccess.MANAGER)

    denied = env.member_client.patch(
        space_url(space.id), {"is_private": True}, format="json"
    )
    assert_error(denied, 403, "permission_denied")

    space.refresh_from_db()
    assert space.is_private is False


def test_admin_can_change_space_visibility(env, private_space):
    response = env.admin_client.patch(
        space_url(private_space.id), {"is_private": False}, format="json"
    )
    assert response.status_code == 200, response.content
    assert response.json()["is_private"] is False

    private_space.refresh_from_db()
    assert private_space.is_private is False


def test_space_manager_can_still_rename_the_space(env, private_space):
    """`space.update` o'z kuchida qoladi — faqat ko'rinuvchanlik ajratildi."""
    grant_space(private_space, env.member, SpaceAccess.MANAGER)

    response = env.member_client.patch(
        space_url(private_space.id), {"name": "PM bo'limi"}, format="json"
    )
    assert response.status_code == 200, response.content
    assert response.json()["name"] == "PM bo'limi"

    private_space.refresh_from_db()
    assert private_space.is_private is True


def test_space_manager_may_resend_an_unchanged_is_private(env, private_space):
    """Qiymat o'zgarmasa tekshiruv yoqilmaydi — to'liq obyekt PATCH'i ishlaydi."""
    grant_space(private_space, env.member, SpaceAccess.MANAGER)

    response = env.member_client.patch(
        space_url(private_space.id),
        {"name": "PM bo'limi", "is_private": True},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["is_private"] is True


def test_change_visibility_is_admin_only_and_never_local_to_a_manager():
    """Katalog invarianti — `space.delete` bilan bir xil mantiq (§F-5)."""
    from apps.core.access import SPACE_MANAGER_GRANTS, SPACE_VIEWER_GRANTS
    from apps.core.permissions import PERMISSION_BY_CODE

    definition = PERMISSION_BY_CODE["space.change_visibility"]
    assert definition.group == "space"
    assert set(definition.defaults) == {"admin"}
    assert definition.sensitive is True
    assert definition.owner_only is False
    assert "space.change_visibility" not in SPACE_MANAGER_GRANTS
    assert "space.change_visibility" not in SPACE_VIEWER_GRANTS
