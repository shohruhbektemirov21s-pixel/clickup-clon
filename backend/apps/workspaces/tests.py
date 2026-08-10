import pytest

from apps.workspaces.models import Invitation, Space, TaskList, WorkspaceMember
from conftest import assert_error, client_for, make_user

pytestmark = pytest.mark.django_db


def ws_url(workspace_id, suffix=""):
    return f"/api/v1/workspaces/{workspace_id}/{suffix}"


# ------------------------------------------------------------- workspaces


def test_create_workspace_bootstraps_and_sets_my_role(env):
    response = env.member_client.post(
        "/api/v1/workspaces/", {"name": "Side Project"}, format="json"
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["my_role"] == "owner"
    assert body["member_count"] == 1
    assert body["slug"]
    space = Space.objects.get(workspace_id=body["id"])
    assert space.name == "Jamoa bo'limi"
    # A fresh workspace starts from zero — scaffolding only, no sample tasks.
    assert space.lists.get().tasks.count() == 0


def test_workspace_list_shows_only_memberships(env):
    response = env.outsider_client.get("/api/v1/workspaces/")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"count", "next", "previous", "results"}
    assert body["count"] == 0

    mine = env.guest_client.get("/api/v1/workspaces/")
    assert mine.json()["count"] == 1
    assert mine.json()["results"][0]["my_role"] == "guest"


def test_workspace_patch_is_owner_only(env):
    url = ws_url(env.workspace.id)
    denied = env.admin_client.patch(url, {"name": "Nope"}, format="json")
    assert_error(denied, 403, "permission_denied")
    ok = env.owner_client.patch(url, {"name": "Acme Renamed"}, format="json")
    assert ok.status_code == 200
    assert ok.json()["name"] == "Acme Renamed"


def test_workspace_delete_requires_confirm_name(env):
    url = ws_url(env.workspace.id)
    bad = env.owner_client.delete(url, {"confirm_name": "wrong"}, format="json")
    assert_error(bad, 400, "validation_error")
    ok = env.owner_client.delete(url, {"confirm_name": "Acme Inc."}, format="json")
    assert ok.status_code == 204


def test_out_of_workspace_is_404_never_403(env):
    response = env.outsider_client.get(ws_url(env.workspace.id))
    assert_error(response, 404, "not_found")
    tree = env.outsider_client.get(ws_url(env.workspace.id, "tree/"))
    assert_error(tree, 404, "not_found")


def test_tree_shape(env):
    response = env.member_client.get(ws_url(env.workspace.id, "tree/"))
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Acme Inc."
    space = body["spaces"][0]
    assert space["name"] == "Jamoa bo'limi"
    assert space["folders"] == []
    assert space["lists"][0]["name"] == "Boshlash"
    assert space["lists"][0]["task_count"] == 0
    assert space["lists"][0]["open_task_count"] == 0


# ------------------------------------------------------------- members


def test_member_roster_order_and_guest_can_read_it(env):
    """2026-08: `member.read` guest'ga ham berildi — roster hammaga ochiq.

    Ilgari bu test mehmon uchun `403` kutardi. Endi `200`, ammo emaillar
    mehmondan yashiriladi — `apps/core/tests/test_permission_policy.py`
    dagi `test_guest_sees_names_but_not_emails` shuni qulflaydi.
    """
    response = env.member_client.get(ws_url(env.workspace.id, "members/"))
    assert response.status_code == 200
    roles = [m["role"] for m in response.json()["results"]]
    assert roles == ["owner", "admin", "member", "guest"]

    as_guest = env.guest_client.get(ws_url(env.workspace.id, "members/"))
    assert as_guest.status_code == 200, as_guest.content
    assert [m["role"] for m in as_guest.json()["results"]] == roles


def test_role_change_rules(env):
    member_url = ws_url(env.workspace.id, f"members/{env.member.id}/")
    owner_url = ws_url(env.workspace.id, f"members/{env.owner.id}/")

    # admin may move members among admin/member/guest
    ok = env.admin_client.patch(member_url, {"role": "guest"}, format="json")
    assert ok.status_code == 200
    assert ok.json()["role"] == "guest"

    # admin may not grant owner, nor touch an owner
    denied = env.admin_client.patch(member_url, {"role": "owner"}, format="json")
    assert_error(denied, 403, "permission_denied")
    denied = env.admin_client.patch(owner_url, {"role": "member"}, format="json")
    assert_error(denied, 403, "permission_denied")

    # member/guest callers are 403
    denied = env.member_client.patch(member_url, {"role": "member"}, format="json")
    assert_error(denied, 403, "permission_denied")

    # owner can promote to owner
    ok = env.owner_client.patch(member_url, {"role": "owner"}, format="json")
    assert ok.status_code == 200


def test_last_owner_invariants(env):
    owner_url = ws_url(env.workspace.id, f"members/{env.owner.id}/")
    demote = env.owner_client.patch(owner_url, {"role": "member"}, format="json")
    assert_error(demote, 409, "conflict")
    remove = env.owner_client.delete(owner_url)
    assert_error(remove, 409, "conflict")
    leave = env.owner_client.post(ws_url(env.workspace.id, "members/leave/"))
    assert_error(leave, 409, "conflict")


def test_member_leave_and_removal(env):
    leave = env.member_client.post(ws_url(env.workspace.id, "members/leave/"))
    assert leave.status_code == 204
    # subsequent requests in the workspace are 404
    after = env.member_client.get(ws_url(env.workspace.id))
    assert_error(after, 404, "not_found")

    remove = env.admin_client.delete(ws_url(env.workspace.id, f"members/{env.guest.id}/"))
    assert remove.status_code == 204
    env.workspace.refresh_from_db()
    assert env.workspace.member_count == 2  # owner + admin remain


# ------------------------------------------------------------- invitations


def test_invitation_flow(env, api):
    url = ws_url(env.workspace.id, "invitations/")
    created = env.admin_client.post(
        url, {"email": "carlos@client.com", "role": "guest"}, format="json"
    )
    assert created.status_code == 201, created.content
    body = created.json()
    assert body["status"] == "pending"
    assert "token" not in body

    # duplicate pending -> 409
    dup = env.admin_client.post(url, {"email": "Carlos@client.com", "role": "member"}, format="json")
    assert_error(dup, 409, "conflict")

    # owner role is not invitable
    bad = env.admin_client.post(url, {"email": "x@y.io", "role": "owner"}, format="json")
    assert_error(bad, 400, "validation_error")

    # member cannot list invitations
    denied = env.member_client.get(url)
    assert_error(denied, 403, "permission_denied")

    token = Invitation.objects.get(pk=body["id"]).token

    # public lookup
    lookup = api.get(f"/api/v1/invitations/lookup/?token={token}")
    assert lookup.status_code == 200
    assert lookup.json()["workspace_name"] == "Acme Inc."
    assert lookup.json()["email"] == "carlos@client.com"

    missing = api.get("/api/v1/invitations/lookup/?token=nope")
    assert_error(missing, 404, "not_found")

    # accept must come from the invited email
    invited = make_user("carlos@client.com")
    wrong_user = env.member_client.post(
        "/api/v1/invitations/accept/", {"token": token}, format="json"
    )
    assert_error(wrong_user, 403, "permission_denied")

    accepted = client_for(invited).post(
        "/api/v1/invitations/accept/", {"token": token}, format="json"
    )
    assert accepted.status_code == 200, accepted.content
    assert accepted.json()["workspace_id"] == str(env.workspace.id)
    assert accepted.json()["member"]["role"] == "guest"
    assert WorkspaceMember.objects.filter(workspace=env.workspace, user=invited).exists()

    # replay of a consumed token -> 409
    replay = client_for(invited).post(
        "/api/v1/invitations/accept/", {"token": token}, format="json"
    )
    assert_error(replay, 409, "conflict")


def test_invite_existing_member_conflict_and_revoke(env):
    url = ws_url(env.workspace.id, "invitations/")
    conflict = env.owner_client.post(
        url, {"email": "member@test.dev", "role": "member"}, format="json"
    )
    assert_error(conflict, 409, "conflict")

    created = env.owner_client.post(url, {"email": "new@x.io", "role": "member"}, format="json")
    invitation_id = created.json()["id"]
    revoked = env.owner_client.delete(f"/api/v1/invitations/{invitation_id}/")
    assert revoked.status_code == 204
    again = env.owner_client.delete(f"/api/v1/invitations/{invitation_id}/")
    assert_error(again, 409, "conflict")


def test_invitation_decline(env):
    url = ws_url(env.workspace.id, "invitations/")
    created = env.owner_client.post(url, {"email": "dec@x.io", "role": "member"}, format="json")
    token = Invitation.objects.get(pk=created.json()["id"]).token
    declined = client_for(make_user("dec@x.io")).post(
        "/api/v1/invitations/decline/", {"token": token}, format="json"
    )
    assert declined.status_code == 204
    assert Invitation.objects.get(pk=created.json()["id"]).status == "revoked"


# ------------------------------------------------------------- spaces


def test_space_create_and_visibility(env):
    url = ws_url(env.workspace.id, "spaces/")
    denied = env.member_client.post(url, {"name": "Eng"}, format="json")
    assert_error(denied, 403, "permission_denied")

    created = env.admin_client.post(
        url, {"name": "Private Ops", "is_private": True}, format="json"
    )
    assert created.status_code == 201, created.content
    space_id = created.json()["id"]
    # default status set auto-created
    status_set = env.admin_client.get(f"/api/v1/spaces/{space_id}/status-set/")
    assert status_set.status_code == 200
    assert [s["name"] for s in status_set.json()["statuses"]] == [
        "BAJARILADI",
        "JARAYONDA",
        "BAJARILDI",
    ]

    # duplicate name (CI) -> 409
    dup = env.admin_client.post(url, {"name": "private ops"}, format="json")
    assert_error(dup, 409, "conflict")

    # guests never see private spaces
    listing = env.guest_client.get(url)
    names = [s["name"] for s in listing.json()["results"]]
    assert "Private Ops" not in names
    detail = env.guest_client.get(f"/api/v1/spaces/{space_id}/")
    assert_error(detail, 404, "not_found")


def test_space_delete_requires_confirm_name(env):
    bad = env.admin_client.delete(
        f"/api/v1/spaces/{env.space.id}/", {"confirm_name": "x"}, format="json"
    )
    assert_error(bad, 400, "validation_error")
    ok = env.admin_client.delete(
        f"/api/v1/spaces/{env.space.id}/", {"confirm_name": "Jamoa bo'limi"}, format="json"
    )
    assert ok.status_code == 204


# ------------------------------------------------------------- folders & lists


def test_folder_crud_and_detach(env):
    url = f"/api/v1/spaces/{env.space.id}/folders/"
    # 2026-08 siyosati: `folder.*` va `list.*` member'dan olib tashlandi —
    # struktura faqat admin+ (yoki o'z bo'limidagi PM) qo'lida.
    member_denied = env.member_client.post(url, {"name": "Nope"}, format="json")
    assert_error(member_denied, 403, "permission_denied")

    created = env.admin_client.post(url, {"name": "Q3"}, format="json")
    assert created.status_code == 201
    folder_id = created.json()["id"]

    dup = env.admin_client.post(url, {"name": "q3"}, format="json")
    assert_error(dup, 409, "conflict")

    # a list inside the folder
    inside = env.admin_client.post(
        f"/api/v1/spaces/{env.space.id}/lists/",
        {"name": "Sprint 24", "folder_id": folder_id},
        format="json",
    )
    assert inside.status_code == 201
    list_id = inside.json()["id"]

    # ikkala strategiya ham endi admin+ (`folder.delete` ham member'da yo'q)
    denied = env.member_client.delete(f"/api/v1/folders/{folder_id}/?strategy=cascade")
    assert_error(denied, 403, "permission_denied")
    denied_detach = env.member_client.delete(f"/api/v1/folders/{folder_id}/?strategy=detach")
    assert_error(denied_detach, 403, "permission_denied")

    # detach moves lists to the space root
    ok = env.admin_client.delete(f"/api/v1/folders/{folder_id}/?strategy=detach")
    assert ok.status_code == 204
    moved = TaskList.objects.get(pk=list_id)
    assert moved.folder_id is None
    assert moved.space_id == env.space.id


def test_list_create_validation_and_scope_conflict(env):
    url = f"/api/v1/spaces/{env.space.id}/lists/"
    # 403 tekshiruvi validatsiyadan oldin: member uchun `list.create` yo'q.
    member_denied = env.member_client.post(url, {"name": "Nope"}, format="json")
    assert_error(member_denied, 403, "permission_denied")

    dup = env.admin_client.post(url, {"name": "boshlash"}, format="json")
    assert_error(dup, 409, "conflict")

    other_space = env.admin_client.post(
        ws_url(env.workspace.id, "spaces/"), {"name": "Other"}, format="json"
    ).json()
    foreign_folder = env.admin_client.post(
        f"/api/v1/spaces/{other_space['id']}/folders/", {"name": "Elsewhere"}, format="json"
    ).json()
    bad = env.admin_client.post(
        url, {"name": "New List", "folder_id": foreign_folder["id"]}, format="json"
    )
    assert_error(bad, 400, "validation_error")

    patch_folder = env.admin_client.patch(
        f"/api/v1/lists/{env.list.id}/", {"folder_id": None}, format="json"
    )
    assert_error(patch_folder, 400, "validation_error")


def test_list_move_reorder_and_reparent(env):
    """`list.move` endi admin+ — setup va harakatlar `admin_client` bilan."""
    space_lists = f"/api/v1/spaces/{env.space.id}/lists/"
    b = env.admin_client.post(space_lists, {"name": "B"}, format="json").json()
    c = env.admin_client.post(space_lists, {"name": "C"}, format="json").json()
    a = env.list  # position "n"

    # move C between A and B
    moved = env.admin_client.patch(
        f"/api/v1/lists/{c['id']}/move/",
        {"folder_id": None, "before_id": str(a.id), "after_id": b["id"]},
        format="json",
    )
    assert moved.status_code == 200, moved.content
    listing = env.member_client.get(space_lists).json()["results"]
    assert [x["name"] for x in listing] == ["Boshlash", "C", "B"]

    # sending space_id is a validation error (OQ-2 ruling)
    bad = env.admin_client.patch(
        f"/api/v1/lists/{c['id']}/move/",
        {"folder_id": None, "space_id": str(env.space.id)},
        format="json",
    )
    assert_error(bad, 400, "validation_error")

    # stale neighbours -> 409 position_conflict
    folder = env.admin_client.post(
        f"/api/v1/spaces/{env.space.id}/folders/", {"name": "F"}, format="json"
    ).json()
    stale = env.admin_client.patch(
        f"/api/v1/lists/{c['id']}/move/",
        {"folder_id": folder["id"], "before_id": b["id"]},  # b is not in the folder
        format="json",
    )
    assert_error(stale, 409, "position_conflict")

    # re-parent into the folder
    reparented = env.admin_client.patch(
        f"/api/v1/lists/{c['id']}/move/", {"folder_id": folder["id"]}, format="json"
    )
    assert reparented.status_code == 200
    assert reparented.json()["folder_id"] == folder["id"]


# ------------------------------------------------------------- status sets


def test_space_status_set_put_with_mapping(env):
    from apps.tasks.models import Task

    url = f"/api/v1/spaces/{env.space.id}/status-set/"
    current = env.admin_client.get(url).json()
    keep = current["statuses"][0]
    in_progress = current["statuses"][1]
    complete = current["statuses"][2]

    # A bootstrapped workspace starts empty, so park a task on the status that
    # the payload below drops — that is what makes the mapping mandatory.
    Task.objects.create(
        list=env.list,
        status_id=in_progress["id"],
        title="Mapping uchun vazifa",
        position="n",
        created_by=env.admin,
        updated_by=env.admin,
    )

    payload = {
        "name": "Bug workflow",
        "statuses": [
            {
                "id": keep["id"],
                "name": "TO DO",
                "color": "#87909E",
                "type": "open",
                "is_default": True,
            },
            {"name": "IN REVIEW", "color": "#4194F6", "type": "active", "is_default": False},
            {"id": complete["id"], "name": "SHIPPED", "color": "#6BC950", "type": "closed",
             "is_default": False},
        ],
    }
    # IN PROGRESS is removed but still holds a task -> missing mapping = 409
    missing = env.admin_client.put(url, payload, format="json")
    error = assert_error(missing, 409, "conflict")
    assert "status_mapping" in error["details"]

    payload["status_mapping"] = {in_progress["id"]: keep["id"]}
    ok = env.admin_client.put(url, payload, format="json")
    assert ok.status_code == 200, ok.content
    body = ok.json()
    assert body["name"] == "Bug workflow"
    assert [s["name"] for s in body["statuses"]] == ["TO DO", "IN REVIEW", "SHIPPED"]
    assert [s["order"] for s in body["statuses"]] == [0, 1, 2]

    # member may read but not write
    denied = env.member_client.put(url, payload, format="json")
    assert_error(denied, 403, "permission_denied")


def test_status_set_invariants(env):
    url = f"/api/v1/spaces/{env.space.id}/status-set/"
    no_closed = {
        "statuses": [
            {"name": "A", "type": "open", "is_default": True},
            {"name": "B", "type": "active", "is_default": False},
        ]
    }
    assert_error(env.admin_client.put(url, no_closed, format="json"), 400, "validation_error")

    two_defaults = {
        "statuses": [
            {"name": "A", "type": "open", "is_default": True},
            {"name": "B", "type": "closed", "is_default": True},
        ]
    }
    assert_error(env.admin_client.put(url, two_defaults, format="json"), 400, "validation_error")


def test_list_status_set_override_and_delete(env):
    from apps.tasks.models import Task

    url = f"/api/v1/lists/{env.list.id}/tasks/"
    # hard-remove sample tasks so no status_mapping is needed (soft-deleted
    # tasks still count as "referenced" per contract section 9)
    Task.all_objects.filter(list=env.list).hard_delete()

    effective = env.member_client.get(f"/api/v1/lists/{env.list.id}/status-set/")
    assert effective.json()["space_id"] == str(env.space.id)  # inherited

    override = {
        "name": "List flow",
        "statuses": [
            {"name": "OPEN", "type": "open", "is_default": True},
            {"name": "DONE", "type": "closed", "is_default": False},
        ],
    }
    put = env.admin_client.put(
        f"/api/v1/lists/{env.list.id}/status-set/", override, format="json"
    )
    assert put.status_code == 200, put.content
    assert put.json()["list_id"] == str(env.list.id)
    assert [s["name"] for s in put.json()["statuses"]] == ["OPEN", "DONE"]

    # new tasks now use the override's default
    task = env.member_client.post(url, {"title": "T"}, format="json").json()
    open_status = put.json()["statuses"][0]
    assert task["status_id"] == open_status["id"]

    # deleting the override needs a mapping for referenced statuses
    space_default = env.member_client.get(
        f"/api/v1/spaces/{env.space.id}/status-set/"
    ).json()["statuses"][0]
    removed = env.admin_client.delete(
        f"/api/v1/lists/{env.list.id}/status-set/",
        {"status_mapping": {open_status["id"]: space_default["id"]}},
        format="json",
    )
    assert removed.status_code == 200, removed.content
    assert removed.json()["space_id"] == str(env.space.id)


# ------------------------------------------------------------- search


def test_search(env):
    url = ws_url(env.workspace.id, "search/")
    missing_q = env.member_client.get(url)
    assert_error(missing_q, 400, "validation_error")

    one_char = env.member_client.get(url + "?q=x")
    assert one_char.status_code == 200
    assert one_char.json()["count"] == 0

    found = env.member_client.get(url + "?q=Boshlash")
    assert found.status_code == 200
    types = {item["type"] for item in found.json()["results"]}
    assert "list" in types
