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
    task = env.member_client.post(
        f"/api/v1/lists/{env.list.id}/tasks/", {"title": "Doomed"}, format="json"
    ).json()
    async_to_sync(layer.group_add)(group, "probe-del")

    assert env.member_client.delete(f"/api/v1/tasks/{task['id']}/").status_code == 204
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
