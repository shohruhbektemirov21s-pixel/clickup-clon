import json

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from apps.accounts.serializers import token_pair_for


async def access_token_for(user):
    return await sync_to_async(lambda: token_pair_for(user)["access"])()


@pytest.mark.django_db
def test_task_created_event_frame(env):
    """Events are emitted from the service layer with the contract's frame shape."""
    layer = get_channel_layer()
    group = f"list.{env.list.id}"
    async_to_sync(layer.group_add)(group, "probe-channel")

    response = env.member_client.post(
        f"/api/v1/lists/{env.list.id}/tasks/",
        {"title": "Realtime task"},
        format="json",
        HTTP_X_CLIENT_ID="tab-42",
    )
    assert response.status_code == 201

    message = async_to_sync(layer.receive)("probe-channel")
    event = message["event"]
    assert event["type"] == "task.created"
    payload = event["payload"]
    assert payload["event_id"].startswith("evt_")
    assert payload["ts"].endswith("Z")
    assert payload["list_id"] == str(env.list.id)
    assert payload["workspace_id"] == str(env.workspace.id)
    assert payload["actor"] == {"id": str(env.member.id), "client_id": "tab-42"}
    assert payload["data"]["title"] == "Realtime task"  # REST-serializer shape


@pytest.mark.django_db
def test_task_deleted_event_payload(env):
    layer = get_channel_layer()
    group = f"list.{env.list.id}"
    # 2026-08 siyosati: `task.delete` faqat admin+ (va o'z bo'limidagi PM) da.
    task = env.admin_client.post(
        f"/api/v1/lists/{env.list.id}/tasks/", {"title": "Doomed"}, format="json"
    ).json()
    async_to_sync(layer.group_add)(group, "probe-del")

    assert env.admin_client.delete(f"/api/v1/tasks/{task['id']}/").status_code == 204
    message = async_to_sync(layer.receive)("probe-del")
    assert message["event"]["type"] == "task.deleted"
    assert message["event"]["payload"]["data"] == {
        "id": task["id"],
        "list_id": str(env.list.id),
    }


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
async def test_list_consumer_rejects_non_member(env):
    from config.asgi import application

    token = await access_token_for(env.outsider)
    communicator = WebsocketCommunicator(
        application, f"/ws/list/{env.list.id}/?token={token}"
    )
    connected, _ = await communicator.connect()
    if connected:
        frame = await communicator.receive_json_from()
        assert frame["type"] == "error"
        assert frame["payload"]["code"] == "permission_denied"
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
        message = await communicator.receive_output(timeout=5)
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
    from apps.realtime import events
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
async def test_space_scoped_revoke_leaves_the_workspace_socket_open(env):
    """Bo'limdan chiqarish workspace a'zoligini olib tashlamaydi."""
    from apps.realtime import events
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
    from apps.realtime.consumers import _PRESENCE
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
