"""Realtime layer tests — frame contract (§15.2), handshake auth (§15.1) and
the authorisation boundary the groups draw (private spaces, guest emails).

Every wait in here is **bounded**. A `layer.receive()` with no timeout turns a
regression into a hung suite instead of a red test, so all channel-layer reads
go through `receive_on()` / `drain()` / `nothing_on()`.
"""

import asyncio
import json
import uuid
from datetime import timedelta

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.serializers import token_pair_for
from apps.realtime import events
from apps.realtime.consumers import _PRESENCE

#: Har qanday kutish chegarali — regressiya osilib qolmasin, YIQILSIN.
RECEIVE_TIMEOUT = 5.0
#: "Hech narsa kelmasligi" ni tasdiqlash uchun qisqa deraza.
SILENCE_TIMEOUT = 0.4


async def access_token_for(user):
    return await sync_to_async(lambda: token_pair_for(user)["access"])()


# ---------------------------------------------------------------------------
# Chegaralangan channel-layer yordamchilari
# ---------------------------------------------------------------------------


def _receive(channel, timeout):
    async def _run():
        return await asyncio.wait_for(get_channel_layer().receive(channel), timeout)

    return async_to_sync(_run)()


def probe(group) -> str:
    """`group` ga bo'sh kanal qo'shadi va uning nomini qaytaradi."""
    channel = f"probe-{uuid.uuid4().hex[:12]}"
    async_to_sync(get_channel_layer().group_add)(group, channel)
    return channel


def receive_on(channel, timeout=RECEIVE_TIMEOUT):
    """Bitta freym — `timeout` ichida kelmasa AssertionError (osilmaydi)."""
    try:
        return _receive(channel, timeout)["event"]
    except (asyncio.TimeoutError, TimeoutError) as exc:  # pragma: no cover - regressiya
        raise AssertionError(f"{channel}: {timeout}s ichida freym kelmadi") from exc


def next_event(channel, event_type, *, limit=12):
    """`event_type` turidagi birinchi freym; oradagilar tashlab yuboriladi."""
    seen = []
    for _ in range(limit):
        event = receive_on(channel)
        if event["type"] == event_type:
            return event
        seen.append(event["type"])
    raise AssertionError(f"{event_type} kelmadi; ko'rilganlari: {seen}")


def drain(channel, timeout=SILENCE_TIMEOUT, limit=60):
    """Kanal jimib qolgunicha barcha freymlar."""
    frames = []
    while len(frames) < limit:
        try:
            frames.append(_receive(channel, timeout)["event"])
        except (asyncio.TimeoutError, TimeoutError):
            break
    return frames


def nothing_on(channel, timeout=SILENCE_TIMEOUT) -> bool:
    try:
        _receive(channel, timeout)
    except (asyncio.TimeoutError, TimeoutError):
        return True
    return False


def emails_in(value, found=None):
    """Strukturaning ichidagi HAR QANDAY `null` bo'lmagan `email` qiymati."""
    found = [] if found is None else found
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "email":
                if item is not None:
                    found.append(item)
            else:
                emails_in(item, found)
    elif isinstance(value, (list, tuple)):
        for item in value:
            emails_in(item, found)
    return found


@pytest.fixture(autouse=True)
def _reset_realtime_state():
    """`_PRESENCE` modul darajasidagi global — testlar orasida oqib ketmasin.

    Kanal qatlami ham jarayon bo'yicha yagona: oldingi testdan qolgan guruh
    a'zoligi yoki yetkazilmagan xabar keyingi testni "tasodifan yashil"
    qilishi mumkin.
    """
    layer = get_channel_layer()
    _PRESENCE.clear()
    if layer is not None and hasattr(layer, "flush"):
        async_to_sync(layer.flush)()
    yield
    _PRESENCE.clear()
    if layer is not None and hasattr(layer, "flush"):
        async_to_sync(layer.flush)()


# ---------------------------------------------------------------------------
# URL yordamchilari
# ---------------------------------------------------------------------------


def tasks_url(list_id):
    return f"/api/v1/lists/{list_id}/tasks/"


def task_url(task_id, suffix=""):
    return f"/api/v1/tasks/{task_id}/{suffix}"


def create_task(client, list_id, **body):
    response = client.post(tasks_url(list_id), body, format="json")
    assert response.status_code == 201, response.content
    return response.json()


def comment_body(text="Salom"):
    """`body_html` va `body_json` shartnoma bo'yicha birga yuboriladi."""
    return {
        "body_html": f"<p>{text}</p>",
        "body_json": {"type": "doc", "content": [{"type": "paragraph"}]},
    }


def post_comment(client, task_id, text="Salom", **extra):
    return client.post(
        f"/api/v1/tasks/{task_id}/comments/", comment_body(text), format="json", **extra
    )


# ---------------------------------------------------------------------------
# §15.2 — freym shakli (11 emitter)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_task_created_event_frame(env):
    """Events are emitted from the service layer with the contract's frame shape."""
    channel = probe(events.list_group(env.list.id))

    response = env.member_client.post(
        tasks_url(env.list.id),
        {"title": "Realtime task"},
        format="json",
        HTTP_X_CLIENT_ID="tab-42",
    )
    assert response.status_code == 201

    event = next_event(channel, "task.created")
    payload = event["payload"]
    assert payload["event_id"].startswith("evt_")
    assert payload["ts"].endswith("Z")
    assert payload["list_id"] == str(env.list.id)
    assert payload["workspace_id"] == str(env.workspace.id)
    assert payload["actor"] == {"id": str(env.member.id), "client_id": "tab-42"}
    assert payload["data"]["title"] == "Realtime task"  # REST-serializer shape


@pytest.mark.django_db
def test_task_updated_event_frame(env):
    task = create_task(env.admin_client, env.list.id, title="Avvalgi nom")
    channel = probe(events.list_group(env.list.id))

    response = env.admin_client.patch(
        task_url(task["id"]),
        {"title": "Yangi nom", "priority": "high"},
        format="json",
        HTTP_X_CLIENT_ID="tab-7",
    )
    assert response.status_code == 200, response.content

    payload = next_event(channel, "task.updated")["payload"]
    assert payload["list_id"] == str(env.list.id)
    assert payload["actor"] == {"id": str(env.admin.id), "client_id": "tab-7"}
    assert payload["data"]["id"] == task["id"]
    assert payload["data"]["title"] == "Yangi nom"
    assert payload["data"]["priority"] == "high"
    # `rebalanced` faqat task.moved da bo'ladi (§15.2).
    assert "rebalanced" not in payload


@pytest.mark.django_db
def test_task_moved_event_frame_carries_the_rebalanced_flag(env):
    first = create_task(env.admin_client, env.list.id, title="Birinchi")
    second = create_task(env.admin_client, env.list.id, title="Ikkinchi")
    channel = probe(events.list_group(env.list.id))

    response = env.admin_client.patch(
        task_url(second["id"], "move/"),
        {
            "list_id": str(env.list.id),
            "status_id": second["status_id"],
            "before_id": first["id"],
        },
        format="json",
    )
    assert response.status_code == 200, response.content

    payload = next_event(channel, "task.moved")["payload"]
    assert payload["data"]["id"] == second["id"]
    assert payload["rebalanced"] is False
    assert payload["actor"]["id"] == str(env.admin.id)
    assert payload["actor"]["client_id"] is None


@pytest.mark.django_db
def test_task_deleted_event_payload(env):
    # 2026-08 siyosati: `task.delete` faqat admin+ (va o'z bo'limidagi PM) da.
    task = create_task(env.admin_client, env.list.id, title="Doomed")
    channel = probe(events.list_group(env.list.id))

    assert env.admin_client.delete(task_url(task["id"])).status_code == 204
    event = next_event(channel, "task.deleted")
    assert event["payload"]["data"] == {"id": task["id"], "list_id": str(env.list.id)}


@pytest.mark.django_db
def test_comment_created_event_frame(env):
    task = create_task(env.admin_client, env.list.id, title="Muhokama")
    channel = probe(events.list_group(env.list.id))

    response = post_comment(env.member_client, task["id"], HTTP_X_CLIENT_ID="tab-9")
    assert response.status_code == 201, response.content

    payload = next_event(channel, "comment.created")["payload"]
    assert payload["list_id"] == str(env.list.id)
    assert payload["actor"] == {"id": str(env.member.id), "client_id": "tab-9"}
    assert payload["data"]["id"] == response.json()["id"]
    assert payload["data"]["task_id"] == task["id"]
    assert payload["data"]["body_html"] == "<p>Salom</p>"
    assert payload["data"]["author"]["id"] == str(env.member.id)


@pytest.mark.django_db
def test_comment_updated_event_frame(env):
    task = create_task(env.admin_client, env.list.id, title="Muhokama")
    comment = post_comment(env.member_client, task["id"], "a").json()
    channel = probe(events.list_group(env.list.id))

    response = env.member_client.patch(
        f"/api/v1/comments/{comment['id']}/", comment_body("b"), format="json"
    )
    assert response.status_code == 200, response.content

    payload = next_event(channel, "comment.updated")["payload"]
    assert payload["data"]["id"] == comment["id"]
    assert payload["data"]["body_html"] == "<p>b</p>"
    assert payload["data"]["is_edited"] is True


@pytest.mark.django_db
def test_comment_deleted_event_frame(env):
    task = create_task(env.admin_client, env.list.id, title="Muhokama")
    comment = post_comment(env.member_client, task["id"], "a").json()
    channel = probe(events.list_group(env.list.id))

    assert env.member_client.delete(f"/api/v1/comments/{comment['id']}/").status_code == 204

    payload = next_event(channel, "comment.deleted")["payload"]
    assert payload["data"] == {"id": comment["id"], "task_id": task["id"]}


@pytest.mark.django_db
def test_attachment_added_event_frame(env, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    task = create_task(env.admin_client, env.list.id, title="Fayl kerak")
    channel = probe(events.list_group(env.list.id))

    response = env.member_client.post(
        f"/api/v1/tasks/{task['id']}/attachments/",
        {"file": SimpleUploadedFile("hisobot.pdf", b"%PDF-1.7 salom", "application/pdf")},
        format="multipart",
    )
    assert response.status_code == 201, response.content

    payload = next_event(channel, "attachment.added")["payload"]
    data = payload["data"]
    assert data["id"] == response.json()["id"]
    assert data["task_id"] == task["id"]
    assert data["original_name"] == "hisobot.pdf"
    assert data["uploaded_by"]["id"] == str(env.member.id)
    assert data["download_url"].endswith(f"/api/v1/attachments/{data['id']}/download/")


@pytest.mark.django_db
def test_attachment_broadcast_download_url_matches_rest(env, settings, tmp_path):
    """§15.2 — `payload.data` REST GET bilan bir xil shaklda bo'lishi shart.

    Broadcast'da `request` yo'q, shuning uchun REST mutlaq, broadcast esa
    nisbiy URL berardi. `PUBLIC_BASE_URL` sozlanganda ikkalasi bir xil bo'ladi.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    settings.PUBLIC_BASE_URL = "https://api.example.test"
    task = create_task(env.admin_client, env.list.id, title="Fayl kerak")
    channel = probe(events.list_group(env.list.id))

    response = env.member_client.post(
        f"/api/v1/tasks/{task['id']}/attachments/",
        {"file": SimpleUploadedFile("hisobot.pdf", b"%PDF-1.7 salom", "application/pdf")},
        format="multipart",
    )
    assert response.status_code == 201, response.content
    attachment_id = response.json()["id"]

    payload = next_event(channel, "attachment.added")["payload"]
    assert payload["data"]["download_url"] == (
        f"https://api.example.test/api/v1/attachments/{attachment_id}/download/"
    )


@pytest.mark.django_db
def test_attachment_removed_event_frame(env, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    task = create_task(env.admin_client, env.list.id, title="Fayl kerak")
    attachment = env.member_client.post(
        f"/api/v1/tasks/{task['id']}/attachments/",
        {"file": SimpleUploadedFile("hisobot.pdf", b"%PDF-1.7 salom", "application/pdf")},
        format="multipart",
    ).json()
    channel = probe(events.list_group(env.list.id))

    deleted = env.member_client.delete(f"/api/v1/attachments/{attachment['id']}/")
    assert deleted.status_code == 204, deleted.content

    payload = next_event(channel, "attachment.removed")["payload"]
    assert payload["data"] == {"id": attachment["id"], "task_id": task["id"]}


@pytest.mark.django_db
def test_list_updated_event_frame(env, django_capture_on_commit_callbacks):
    """`list.updated` yon panel uchun — endi bo'lim guruhida (workspace emas)."""
    space_channel = probe(events.space_group(env.space.id))
    workspace_channel = probe(events.workspace_group(env.workspace.id))

    # `update_list` freymni `on_commit` da e'lon qiladi.
    with django_capture_on_commit_callbacks(execute=True):
        response = env.admin_client.patch(
            f"/api/v1/lists/{env.list.id}/",
            {"name": "Qayta nomlangan"},
            format="json",
            HTTP_X_CLIENT_ID="tab-1",
        )
    assert response.status_code == 200, response.content

    payload = next_event(space_channel, "list.updated")["payload"]
    assert payload["list_id"] == str(env.list.id)
    assert payload["workspace_id"] == str(env.workspace.id)
    assert payload["actor"] == {"id": str(env.admin.id), "client_id": "tab-1"}
    assert payload["data"]["id"] == str(env.list.id)
    assert payload["data"]["name"] == "Qayta nomlangan"
    assert payload["data"]["space_id"] == str(env.space.id)
    # Xom workspace guruhi endi bo'lim mazmunini olib yurmaydi.
    assert nothing_on(workspace_channel)


@pytest.mark.django_db
def test_permission_updated_event_frame(env, django_capture_on_commit_callbacks):
    """`permission.updated` — mazmun olib yurmaydi, shuning uchun workspace guruhida."""
    from apps.core.access import bump_permissions_version

    channel = probe(events.workspace_group(env.workspace.id))
    with django_capture_on_commit_callbacks(execute=True):
        version = bump_permissions_version(env.workspace, actor=env.owner)

    payload = next_event(channel, "permission.updated")["payload"]
    assert payload["list_id"] is None
    assert payload["workspace_id"] == str(env.workspace.id)
    assert payload["actor"]["id"] == str(env.owner.id)
    assert payload["actor"]["client_id"] is None
    assert payload["data"] == {"workspace_id": str(env.workspace.id), "version": version}


@pytest.mark.django_db
def test_access_revoked_event_frame(env):
    channel = probe(events.user_group(env.guest.id))
    events.emit_access_revoked(
        env.guest.id, workspace_id=env.workspace.id, space_id=env.space.id
    )

    payload = next_event(channel, "access.revoked")["payload"]
    assert payload["actor"] == {"id": None, "client_id": None}
    assert payload["data"] == {
        "workspace_id": str(env.workspace.id),
        "space_id": str(env.space.id),
    }


# ---------------------------------------------------------------------------
# AppSec: broadcast HECH QACHON email olib yurmaydi (O-1, §1 BINDING)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_broadcast_frame_ever_carries_an_email(
    env, settings, tmp_path, django_capture_on_commit_callbacks
):
    """Bitta payload bir marta serializatsiya qilinib turli vakolatdagi
    odamlarga tarqaladi, ya'ni per-recipient maskalash mumkin emas — shuning
    uchun `email` freymga umuman chiqmaydi."""
    settings.MEDIA_ROOT = str(tmp_path)
    list_channel = probe(events.list_group(env.list.id))
    space_channel = probe(events.space_group(env.space.id))

    with django_capture_on_commit_callbacks(execute=True):
        task = create_task(
            env.admin_client,
            env.list.id,
            title="Email tekshiruvi",
            assignee_ids=[str(env.member.id), str(env.guest.id)],
        )
        assert post_comment(env.member_client, task["id"], "a").status_code == 201
        assert (
            env.member_client.post(
                f"/api/v1/tasks/{task['id']}/attachments/",
                {"file": SimpleUploadedFile("a.pdf", b"%PDF-1.7 x", "application/pdf")},
                format="multipart",
            ).status_code
            == 201
        )
        assert env.admin_client.patch(
            f"/api/v1/lists/{env.list.id}/", {"name": "Nomi"}, format="json"
        ).status_code == 200

    frames = drain(list_channel) + drain(space_channel)
    assert len(frames) >= 4, [f["type"] for f in frames]

    # (a) Hech bir freymda `null` bo'lmagan email yo'q.
    assert emails_in(frames) == []
    # (b) Hech bir haqiqiy pochta manzili matn sifatida ham uchramaydi.
    blob = json.dumps(frames)
    for user in (env.owner, env.admin, env.member, env.guest):
        assert user.email not in blob
    # (c) Kalit o'chirilmaydi — `email: null` REST'dagi mehmon shakli bilan bir xil.
    created = [f for f in frames if f["type"] == "task.created"]
    assert created and "email" in created[0]["payload"]["data"]["created_by"]
    assert created[0]["payload"]["data"]["created_by"]["email"] is None
    assert [a["email"] for a in created[0]["payload"]["data"]["assignees"]] == [None, None]


# ---------------------------------------------------------------------------
# Handshake — list kanali
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
async def test_list_consumer_handshake(env):
    from config.asgi import application

    token = await access_token_for(env.member)
    communicator = WebsocketCommunicator(
        application, f"/ws/list/{env.list.id}/?token={token}"
    )
    connected, _ = await communicator.connect()
    assert connected

    ack = await communicator.receive_json_from()
    assert ack["type"] == "connection.ack"
    assert ack["payload"]["data"]["channel"] == f"list.{env.list.id}"
    assert ack["payload"]["data"]["user_id"] == str(env.member.id)

    # presence.join (own) and presence.sync arrive next, order-tolerant
    seen = {ack["type"]}
    for _ in range(2):
        frame = await communicator.receive_json_from()
        seen.add(frame["type"])
    assert "presence.sync" in seen
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_list_consumer_rejects_bad_token(env):
    from config.asgi import application

    communicator = WebsocketCommunicator(
        application, f"/ws/list/{env.list.id}/?token=garbage"
    )
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_list_consumer_rejects_an_expired_jwt(env):
    """Buzuq token emas — HAQIQIY, imzosi to'g'ri, lekin muddati o'tgan token."""
    from rest_framework_simplejwt.tokens import AccessToken

    from config.asgi import application

    def _stale():
        token = AccessToken.for_user(env.member)
        token.set_exp(lifetime=timedelta(seconds=-30))
        return str(token)

    token = await sync_to_async(_stale)()
    communicator = WebsocketCommunicator(
        application, f"/ws/list/{env.list.id}/?token={token}"
    )
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_list_consumer_rejects_a_token_without_a_user_claim(env):
    """Imzosi to'g'ri, `exp`/`jti` joyida, lekin `user_id` da'vosi yo'q token.

    `AccessToken.verify()` bunday tokenni o'tkazib yuboradi, ya'ni da'voni
    o'qish `KeyError` berardi va handshake 500 bilan yiqilardi.
    """
    from rest_framework_simplejwt.tokens import AccessToken

    from config.asgi import application

    token = await sync_to_async(lambda: str(AccessToken()))()
    communicator = WebsocketCommunicator(
        application, f"/ws/list/{env.list.id}/?token={token}"
    )
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_list_consumer_rejects_non_member(env):
    """§15.1 shartnomasi: accept -> bitta `error` freymi -> close, `ack` YO'Q.

    Ilgari bu test `if connected:` ostida edi, ya'ni consumer begonani qabul
    qilib qo'ysa ham nol assertion bilan yashil bo'lardi.
    """
    from config.asgi import application

    token = await access_token_for(env.outsider)
    communicator = WebsocketCommunicator(
        application, f"/ws/list/{env.list.id}/?token={token}"
    )
    connected, _ = await communicator.connect()
    assert connected  # accept + error + close (§15.1)

    frames, close_code = await frames_until_close(communicator)
    assert [f["type"] for f in frames] == ["error"]
    assert frames[0]["payload"]["code"] == "permission_denied"
    assert close_code in (None, 1000)
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_list_consumer_rejects_a_guest_in_a_private_space(env):
    from config.asgi import application

    private = await sync_to_async(make_private_space)(env)
    ticket = await ticket_for(env.guest)
    communicator = WebsocketCommunicator(
        application, f"/ws/list/{private['list_id']}/?ticket={ticket}"
    )
    connected, _ = await communicator.connect()
    assert connected
    frames, _ = await frames_until_close(communicator)
    assert [f["type"] for f in frames] == ["error"]
    assert frames[0]["payload"]["code"] == "permission_denied"
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_list_consumer_accepts_a_guest_who_is_a_space_member(env):
    """REST va WS bitta predikatga tayanadi (`space_is_visible`).

    Qo'lda yozilgan `role == GUEST and is_private -> rad` qoidasi `SpaceMember`
    qatorlarini ko'rmasdi: bo'limga aniq qo'shilgan mehmon REST'dan o'tib,
    soketdan rad etilardi.
    """
    from config.asgi import application

    private = await sync_to_async(make_private_space)(env, viewer=True)
    ticket = await ticket_for(env.guest)
    communicator = WebsocketCommunicator(
        application, f"/ws/list/{private['list_id']}/?ticket={ticket}"
    )
    connected, _ = await communicator.connect()
    assert connected
    ack = await communicator.receive_json_from()
    assert ack["type"] == "connection.ack"
    assert ack["payload"]["data"]["channel"] == f"list.{private['list_id']}"
    await communicator.disconnect()


# ---------------------------------------------------------------------------
# Handshake — workspace kanali (ilgari umuman qamralmagan edi)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
async def test_workspace_consumer_handshake(env):
    from config.asgi import application

    ticket = await ticket_for(env.member)
    communicator = WebsocketCommunicator(
        application, f"/ws/workspaces/{env.workspace.id}/?ticket={ticket}"
    )
    connected, _ = await communicator.connect()
    assert connected
    ack = await communicator.receive_json_from()
    assert ack["type"] == "connection.ack"
    assert ack["payload"]["data"]["channel"] == f"workspace.{env.workspace.id}"
    assert ack["payload"]["data"]["user_id"] == str(env.member.id)
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_workspace_consumer_rejects_bad_token(env):
    from config.asgi import application

    communicator = WebsocketCommunicator(
        application, f"/ws/workspaces/{env.workspace.id}/?token=garbage"
    )
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_workspace_consumer_rejects_non_member(env):
    from config.asgi import application

    ticket = await ticket_for(env.outsider)
    communicator = WebsocketCommunicator(
        application, f"/ws/workspaces/{env.workspace.id}/?ticket={ticket}"
    )
    connected, _ = await communicator.connect()
    assert connected  # accept + error + close (§15.1)
    frames, _ = await frames_until_close(communicator)
    assert [f["type"] for f in frames] == ["error"]
    assert frames[0]["payload"]["code"] == "permission_denied"
    await communicator.disconnect()


# ---------------------------------------------------------------------------
# AppSec: yopiq bo'lim mazmuni workspace soketiga OQMAYDI
# ---------------------------------------------------------------------------


def make_private_space(env, *, viewer=False, name="Yopiq loyiha"):
    """Owner yaratgan yopiq bo'lim + bitta ro'yxat. `viewer` -> guest bo'lim a'zosi.

    Ataylab REST orqali: sozlash yo'li mahsulot yo'li bilan bir xil bo'lsin.
    """
    space = env.owner_client.post(
        f"/api/v1/workspaces/{env.workspace.id}/spaces/",
        {"name": name, "is_private": True},
        format="json",
    )
    assert space.status_code == 201, space.content
    space_id = space.json()["id"]
    created = env.owner_client.post(
        f"/api/v1/spaces/{space_id}/lists/", {"name": "Maxfiy ro'yxat"}, format="json"
    )
    assert created.status_code == 201, created.content
    if viewer:
        added = env.owner_client.post(
            f"/api/v1/spaces/{space_id}/members/",
            {"user_id": str(env.guest.id), "access": "viewer"},
            format="json",
        )
        assert added.status_code == 201, added.content
    return {"space_id": space_id, "list_id": created.json()["id"]}


def remove_space_member_via_rest(env, space_id, user):
    response = env.owner_client.delete(f"/api/v1/spaces/{space_id}/members/{user.id}/")
    assert response.status_code == 204, response.content


def create_task_as_owner(env, list_id, **body):
    return create_task(env.owner_client, list_id, **body)


@pytest.mark.django_db(transaction=True)
async def test_workspace_socket_never_leaks_a_private_space(env):
    """Regression — mehmon workspace a'zosi, lekin yopiq bo'limga kira olmaydi.

    REST bu ro'yxat uchun 404 qaytaradi; soket ham u haqida BIRON freym
    bermasligi kerak. Ilgari `task.created` yopiq vazifaning sarlavhasini,
    `description_html` ini va biriktirilganlarning emailini yetkazardi.
    """
    from config.asgi import application

    private = await sync_to_async(make_private_space)(env)
    ticket = await ticket_for(env.guest)
    communicator = WebsocketCommunicator(
        application, f"/ws/workspaces/{env.workspace.id}/?ticket={ticket}"
    )
    connected, _ = await communicator.connect()
    assert connected
    assert (await communicator.receive_json_from())["type"] == "connection.ack"

    await sync_to_async(create_task_as_owner)(
        env,
        private["list_id"],
        title="Maxfiy sotib olish",
        description_html="<p>Narx: 1 000 000</p>",
        description_json={"type": "doc", "content": [{"type": "paragraph"}]},
    )
    assert await communicator.receive_nothing(timeout=0.6)

    # Ochiq bo'lim esa avvalgidek yetib keladi — soket "o'chib qolgani" uchun
    # emas, aynan doirasi torayganligi uchun jim.
    await sync_to_async(create_task_as_owner)(env, env.list.id, title="Ochiq ish")
    created = None
    for _ in range(2):  # task.created + list.updated, tartibi muhim emas
        frame = await communicator.receive_json_from(timeout=RECEIVE_TIMEOUT)
        if frame["type"] == "task.created":
            created = frame
    assert created is not None
    assert created["payload"]["data"]["title"] == "Ochiq ish"
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_workspace_socket_delivers_a_private_space_to_its_members(env):
    """Teskari tomoni: bo'lim a'zosi bo'lgan mehmon freymni OLADI."""
    from config.asgi import application

    private = await sync_to_async(make_private_space)(env, viewer=True)
    ticket = await ticket_for(env.guest)
    communicator = WebsocketCommunicator(
        application, f"/ws/workspaces/{env.workspace.id}/?ticket={ticket}"
    )
    connected, _ = await communicator.connect()
    assert connected
    assert (await communicator.receive_json_from())["type"] == "connection.ack"

    await sync_to_async(create_task_as_owner)(env, private["list_id"], title="Ko'rinadi")
    types = set()
    for _ in range(2):
        types.add((await communicator.receive_json_from(timeout=RECEIVE_TIMEOUT))["type"])
    assert "task.created" in types
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_losing_space_access_stops_the_frames_on_a_live_socket(env):
    """Soket ruxsat o'zgarishidan uzoq yashaydi — guruh a'zoligi qayta baholanadi."""
    from config.asgi import application

    private = await sync_to_async(make_private_space)(env, viewer=True)
    ticket = await ticket_for(env.guest)
    communicator = WebsocketCommunicator(
        application, f"/ws/workspaces/{env.workspace.id}/?ticket={ticket}"
    )
    connected, _ = await communicator.connect()
    assert connected
    assert (await communicator.receive_json_from())["type"] == "connection.ack"

    await sync_to_async(remove_space_member_via_rest)(env, private["space_id"], env.guest)
    revoked = await communicator.receive_json_from(timeout=RECEIVE_TIMEOUT)
    assert revoked["type"] == "access.revoked"
    assert revoked["payload"]["data"]["space_id"] == private["space_id"]

    # Bo'lim darajasidagi bekor qilish yon panel soketini YOPMAYDI, lekin
    # o'sha bo'lim guruhidan chiqarib yuboradi.
    await sync_to_async(create_task_as_owner)(env, private["list_id"], title="Endi ko'rinmaydi")
    assert await communicator.receive_nothing(timeout=0.6)
    await communicator.disconnect()


# ---------------------------------------------------------------------------
# AppSec: handshake chiptalari (O-3)
# ---------------------------------------------------------------------------


async def ticket_for(user):
    from apps.realtime.tickets import issue_ticket

    return await sync_to_async(issue_ticket)(user)


async def frames_until_close(communicator, limit=60):
    """Soket yopilgunicha barcha freymlarni yig'adi -> (frames, close_code)."""
    frames = []
    while limit > 0:
        limit -= 1
        message = await communicator.receive_output(timeout=RECEIVE_TIMEOUT)
        if message["type"] == "websocket.close":
            return frames, message.get("code")
        if message["type"] == "websocket.send":
            frames.append(json.loads(message["text"]))
    raise AssertionError("soket yopilmadi")


@pytest.mark.django_db
def test_realtime_ticket_endpoint_issues_single_use_ticket(env):
    from apps.realtime.tickets import consume_ticket

    response = env.member_client.post("/api/v1/realtime/ticket/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["expires_in"] == 30
    assert isinstance(body["ticket"], str) and len(body["ticket"]) >= 32
    # Chipta so'rovchining o'ziga bog'langan va faqat bir marta yechiladi.
    assert consume_ticket(body["ticket"]) == str(env.member.id)
    assert consume_ticket(body["ticket"]) is None


@pytest.mark.django_db
def test_realtime_ticket_endpoint_requires_authentication(api):
    assert api.post("/api/v1/realtime/ticket/").status_code == 401


@pytest.mark.django_db(transaction=True)
async def test_list_consumer_accepts_a_ticket_once(env):
    from config.asgi import application

    ticket = await ticket_for(env.member)
    first = WebsocketCommunicator(application, f"/ws/list/{env.list.id}/?ticket={ticket}")
    connected, _ = await first.connect()
    assert connected
    ack = await first.receive_json_from()
    assert ack["type"] == "connection.ack"
    assert ack["payload"]["data"]["user_id"] == str(env.member.id)
    await first.disconnect()

    # Log'dan olingan chipta qayta ishlatilmaydi.
    replay = WebsocketCommunicator(application, f"/ws/list/{env.list.id}/?ticket={ticket}")
    connected, _ = await replay.connect()
    assert not connected
    await replay.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_list_consumer_rejects_bogus_and_expired_tickets(env, monkeypatch):
    from apps.realtime import tickets
    from config.asgi import application

    bogus = WebsocketCommunicator(application, f"/ws/list/{env.list.id}/?ticket=not-a-ticket")
    connected, _ = await bogus.connect()
    assert not connected
    await bogus.disconnect()

    monkeypatch.setattr(tickets, "TICKET_TTL_SECONDS", 0)
    stale = await ticket_for(env.member)
    expired = WebsocketCommunicator(application, f"/ws/list/{env.list.id}/?ticket={stale}")
    connected, _ = await expired.connect()
    assert not connected
    await expired.disconnect()


# ---------------------------------------------------------------------------
# AppSec: a'zolik bekor qilinganda soket yopiladi (Y-2)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
async def test_access_revoked_closes_the_list_socket(env):
    from config.asgi import application

    ticket = await ticket_for(env.member)
    communicator = WebsocketCommunicator(application, f"/ws/list/{env.list.id}/?ticket={ticket}")
    connected, _ = await communicator.connect()
    assert connected

    await sync_to_async(events.emit_access_revoked)(
        env.member.id, workspace_id=env.workspace.id
    )
    frames, close_code = await frames_until_close(communicator)
    assert close_code == 4403
    assert any(f["type"] == "access.revoked" for f in frames)
    error = [f for f in frames if f["type"] == "error"]
    assert error and error[-1]["payload"]["code"] == "permission_denied"
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_a_foreign_workspace_revocation_leaves_the_socket_open(env):
    """`_same_workspace` filtri — boshqa ish maydonidagi bekor qilish tegmaydi."""
    from config.asgi import application

    ticket = await ticket_for(env.member)
    communicator = WebsocketCommunicator(application, f"/ws/list/{env.list.id}/?ticket={ticket}")
    connected, _ = await communicator.connect()
    assert connected
    for _ in range(3):  # ack + presence.join + presence.sync
        await communicator.receive_json_from()

    other_workspace_id = uuid.uuid4()
    await sync_to_async(events.emit_access_revoked)(
        env.member.id, workspace_id=other_workspace_id
    )
    frame = await communicator.receive_json_from(timeout=RECEIVE_TIMEOUT)
    assert frame["type"] == "access.revoked"
    assert frame["payload"]["data"]["workspace_id"] == str(other_workspace_id)
    # Soket ochiq qoladi va ishlashda davom etadi.
    assert await communicator.receive_nothing(timeout=0.5)
    await sync_to_async(create_task_as_owner)(env, env.list.id, title="Hali ham tirik")
    alive = await communicator.receive_json_from(timeout=RECEIVE_TIMEOUT)
    assert alive["type"] == "task.created"
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_space_scoped_revoke_leaves_the_workspace_socket_open(env):
    """Bo'limdan chiqarish workspace a'zoligini olib tashlamaydi."""
    from config.asgi import application

    ticket = await ticket_for(env.member)
    communicator = WebsocketCommunicator(
        application, f"/ws/workspaces/{env.workspace.id}/?ticket={ticket}"
    )
    connected, _ = await communicator.connect()
    assert connected
    assert (await communicator.receive_json_from())["type"] == "connection.ack"

    await sync_to_async(events.emit_access_revoked)(
        env.member.id, workspace_id=env.workspace.id, space_id=env.space.id
    )
    frame = await communicator.receive_json_from()
    assert frame["type"] == "access.revoked"
    assert await communicator.receive_nothing(timeout=0.5)
    await communicator.disconnect()


# ---------------------------------------------------------------------------
# AppSec: presence gigiyenasi va kiruvchi rate-limit (O-9)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
async def test_presence_frames_never_carry_an_email(env):
    from config.asgi import application

    ticket = await ticket_for(env.member)
    communicator = WebsocketCommunicator(application, f"/ws/list/{env.list.id}/?ticket={ticket}")
    connected, _ = await communicator.connect()
    assert connected

    frames = [await communicator.receive_json_from() for _ in range(3)]
    by_type = {f["type"]: f for f in frames}
    assert "presence.sync" in by_type and "presence.join" in by_type

    users = by_type["presence.sync"]["payload"]["data"]["users"]
    assert users
    for summary in [*users, by_type["presence.join"]["payload"]["data"]["user"]]:
        assert set(summary) == {"id", "full_name", "avatar", "avatar_color"}
    # Email hech qaysi freymda umuman uchramaydi.
    assert env.member.email not in json.dumps(frames)
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_inbound_flood_closes_the_socket(env):
    from apps.realtime.consumers import INBOUND_BURST
    from config.asgi import application

    ticket = await ticket_for(env.member)
    communicator = WebsocketCommunicator(application, f"/ws/list/{env.list.id}/?ticket={ticket}")
    connected, _ = await communicator.connect()
    assert connected

    for _ in range(INBOUND_BURST + 5):
        await communicator.send_json_to({"type": "presence.ping"})

    frames, close_code = await frames_until_close(communicator)
    assert close_code == 4029
    assert frames[-1]["type"] == "error"
    assert frames[-1]["payload"]["code"] == "throttled"
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_presence_registry_forgets_the_list_when_the_last_user_leaves(env):
    from config.asgi import application

    list_id = str(env.list.id)
    ticket = await ticket_for(env.member)
    communicator = WebsocketCommunicator(application, f"/ws/list/{list_id}/?ticket={ticket}")
    connected, _ = await communicator.connect()
    assert connected
    for _ in range(3):
        await communicator.receive_json_from()
    assert list_id in _PRESENCE

    await communicator.disconnect()
    # O-9a: bo'sh bucket ham qolmasin - aks holda bu cheksiz xotira sizishi.
    assert list_id not in _PRESENCE
