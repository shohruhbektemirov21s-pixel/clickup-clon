"""`apps.chat` testlari — kanallar, DM, ko'rinuvchanlik va real vaqt."""

from __future__ import annotations

import pytest

from apps.chat.models import Conversation, ConversationKind, ConversationMember, Message
from apps.chat.services import direct_key
from conftest import assert_error

pytestmark = pytest.mark.django_db


def channels_url(workspace_id):
    return f"/api/v1/workspaces/{workspace_id}/chat/channels/"


def direct_url(workspace_id):
    return f"/api/v1/workspaces/{workspace_id}/chat/direct/"


def messages_url(conversation_id):
    return f"/api/v1/chat/conversations/{conversation_id}/messages/"


def join_url(conversation_id):
    return f"/api/v1/chat/conversations/{conversation_id}/join/"


def make_channel(env, client=None, **body):
    payload = {"name": "umumiy", **body}
    response = (client or env.owner_client).post(
        channels_url(env.workspace.id), payload, format="json"
    )
    assert response.status_code == 201, response.content
    return response.json()


# ------------------------------------------------------------------ kanallar


def test_creating_a_channel_makes_the_creator_a_member(env):
    channel = make_channel(env)
    assert channel["kind"] == "channel"
    assert channel["title"] == "umumiy"
    assert channel["is_member"] is True


def test_channel_name_is_unique_per_workspace(env):
    make_channel(env)
    response = env.owner_client.post(
        channels_url(env.workspace.id), {"name": "umumiy"}, format="json"
    )
    assert_error(response, 400, "validation_error")


def test_the_same_channel_name_is_allowed_in_another_workspace(env):
    from apps.workspaces.services import bootstrap_workspace

    make_channel(env)
    other = bootstrap_workspace(env.owner, name="Boshqa")
    response = env.owner_client.post(channels_url(other.id), {"name": "umumiy"}, format="json")
    assert response.status_code == 201, response.content


def test_blank_channel_name_is_rejected(env):
    response = env.owner_client.post(channels_url(env.workspace.id), {"name": "   "}, format="json")
    assert_error(response, 400, "validation_error")


def test_open_channel_is_listed_for_every_member(env):
    make_channel(env)
    for client in (env.admin_client, env.member_client, env.guest_client):
        listing = client.get(channels_url(env.workspace.id)).json()
        assert [c["title"] for c in listing["results"]] == ["umumiy"]


def test_private_channel_is_hidden_from_non_members(env):
    make_channel(env, is_private=True, name="maxfiy")
    listing = env.member_client.get(channels_url(env.workspace.id)).json()
    assert listing["results"] == []
    # Egasi yaratgani uchun uni ko'radi.
    assert len(env.owner_client.get(channels_url(env.workspace.id)).json()["results"]) == 1


def test_outsider_cannot_list_channels(env):
    make_channel(env)
    response = env.outsider_client.get(channels_url(env.workspace.id))
    assert response.status_code == 404, response.content


def test_private_channel_is_404_not_403_for_a_stranger(env):
    """Mavjudligini oshkor qilmaymiz — §1.7 qoidasi."""
    channel = make_channel(env, is_private=True, name="maxfiy")
    response = env.member_client.get(messages_url(channel["id"]))
    assert response.status_code == 404, response.content


# ----------------------------------------------------------------- xabarlar


def test_member_must_join_before_posting(env):
    channel = make_channel(env)
    denied = env.member_client.post(messages_url(channel["id"]), {"body": "salom"}, format="json")
    assert_error(denied, 403, "permission_denied")

    assert env.member_client.post(join_url(channel["id"])).status_code == 204
    ok = env.member_client.post(messages_url(channel["id"]), {"body": "salom"}, format="json")
    assert ok.status_code == 201, ok.content


def test_posting_and_reading_a_message(env):
    channel = make_channel(env)
    posted = env.owner_client.post(
        messages_url(channel["id"]), {"body": "  Salom jamoa  "}, format="json"
    ).json()
    assert posted["body"] == "Salom jamoa", "atrofdagi bo'shliqlar kesilishi kerak"
    assert posted["author"]["id"] == str(env.owner.id)

    history = env.owner_client.get(messages_url(channel["id"])).json()
    assert history["count"] == 1


def test_blank_message_is_rejected(env):
    channel = make_channel(env)
    response = env.owner_client.post(messages_url(channel["id"]), {"body": "   "}, format="json")
    assert_error(response, 400, "validation_error")


def test_posting_updates_last_message_at_for_ordering(env):
    first = make_channel(env, name="birinchi")
    second = make_channel(env, name="ikkinchi")
    env.owner_client.post(messages_url(first["id"]), {"body": "a"}, format="json")
    env.owner_client.post(messages_url(second["id"]), {"body": "b"}, format="json")
    env.owner_client.post(messages_url(first["id"]), {"body": "c"}, format="json")

    listing = env.owner_client.get(channels_url(env.workspace.id)).json()
    # Eng so'nggi faoliyat yuqorida.
    assert [c["title"] for c in listing["results"]] == ["birinchi", "ikkinchi"]


def test_last_message_is_embedded_in_the_listing(env):
    channel = make_channel(env)
    env.owner_client.post(messages_url(channel["id"]), {"body": "oxirgisi"}, format="json")
    listing = env.owner_client.get(channels_url(env.workspace.id)).json()
    assert listing["results"][0]["last_message"]["body"] == "oxirgisi"


def test_outsider_cannot_post(env):
    channel = make_channel(env)
    response = env.outsider_client.post(
        messages_url(channel["id"]), {"body": "salom"}, format="json"
    )
    assert response.status_code == 404, response.content


# ----------------------------------------------------------- o'qilmaganlar


def test_unread_counts_only_other_peoples_messages(env):
    channel = make_channel(env)
    env.member_client.post(join_url(channel["id"]))
    env.owner_client.post(messages_url(channel["id"]), {"body": "1"}, format="json")
    env.owner_client.post(messages_url(channel["id"]), {"body": "2"}, format="json")

    mine = env.owner_client.get(channels_url(env.workspace.id)).json()["results"][0]
    theirs = env.member_client.get(channels_url(env.workspace.id)).json()["results"][0]
    assert mine["unread"] == 0, "o'z xabaring o'qilmagan bo'lmaydi"
    assert theirs["unread"] == 2


def test_reading_the_history_clears_unread(env):
    channel = make_channel(env)
    env.member_client.post(join_url(channel["id"]))
    env.owner_client.post(messages_url(channel["id"]), {"body": "1"}, format="json")

    env.member_client.get(messages_url(channel["id"]))
    after = env.member_client.get(channels_url(env.workspace.id)).json()["results"][0]
    assert after["unread"] == 0


# ------------------------------------------------------------------- DM


def test_direct_key_is_order_independent(env):
    assert direct_key(env.owner.id, env.member.id) == direct_key(env.member.id, env.owner.id)


def test_opening_a_dm_twice_returns_the_same_conversation(env):
    first = env.owner_client.post(
        direct_url(env.workspace.id), {"user_id": str(env.member.id)}, format="json"
    ).json()
    second = env.member_client.post(
        direct_url(env.workspace.id), {"user_id": str(env.owner.id)}, format="json"
    ).json()
    assert first["id"] == second["id"], "A→B va B→A bitta yozishma bo'lishi kerak"
    assert Conversation.objects.filter(kind=ConversationKind.DIRECT).count() == 1


def test_dm_title_is_the_other_person(env):
    dm = env.owner_client.post(
        direct_url(env.workspace.id), {"user_id": str(env.member.id)}, format="json"
    ).json()
    assert dm["title"] == env.member.full_name
    assert dm["peer"]["id"] == str(env.member.id)

    from_other_side = env.member_client.get(channels_url(env.workspace.id)).json()["results"][0]
    assert from_other_side["title"] == env.owner.full_name


def test_dm_has_exactly_two_members(env):
    dm = env.owner_client.post(
        direct_url(env.workspace.id), {"user_id": str(env.member.id)}, format="json"
    ).json()
    assert ConversationMember.objects.filter(conversation_id=dm["id"]).count() == 2


def test_dm_is_invisible_to_everyone_else(env):
    env.owner_client.post(
        direct_url(env.workspace.id), {"user_id": str(env.member.id)}, format="json"
    )
    listing = env.admin_client.get(channels_url(env.workspace.id)).json()
    assert listing["results"] == [], "boshqa a'zo begona yozishmani ko'rmasligi kerak"


def test_cannot_dm_yourself(env):
    response = env.owner_client.post(
        direct_url(env.workspace.id), {"user_id": str(env.owner.id)}, format="json"
    )
    assert_error(response, 400, "validation_error")


def test_cannot_dm_someone_outside_the_workspace(env):
    response = env.owner_client.post(
        direct_url(env.workspace.id), {"user_id": str(env.outsider.id)}, format="json"
    )
    assert response.status_code == 404, response.content


def test_cannot_join_a_dm(env):
    dm = env.owner_client.post(
        direct_url(env.workspace.id), {"user_id": str(env.member.id)}, format="json"
    ).json()
    # Uchinchi odam uni umuman ko'rmaydi → 404, 403 emas.
    assert env.admin_client.post(join_url(dm["id"])).status_code == 404


# ------------------------------------------------------------- real vaqt


# `transaction=True` SHART: async test boshqa ulanishdan bazaga tegadi va
# oddiy `django_db` ning tranzaksiyaga o'ralgan rejimida SQLite jadvalni
# qulflab qo'yadi ("database table is locked"). Mavjud
# `apps/realtime/tests.py` dagi consumer testlari ham shu sababdan
# `transaction=True` ishlatadi.
@pytest.mark.django_db(transaction=True)
async def test_message_is_broadcast_to_the_conversation_group(env):
    """`post_message` `chat.<id>` guruhiga freym yuboradimi."""
    from channels.layers import get_channel_layer
    from asgiref.sync import sync_to_async

    from apps.chat import services

    channel = await sync_to_async(services.create_channel)(
        workspace_id=env.workspace.id, actor=env.owner, name="realtime"
    )
    layer = get_channel_layer()
    await layer.group_add(f"chat.{channel.id}", "test-channel")

    await sync_to_async(services.post_message)(
        conversation=channel, author=env.owner, body="salom"
    )

    frame = await layer.receive("test-channel")
    event = frame["event"]
    assert event["type"] == "chat.message.created"
    assert event["payload"]["data"]["body"] == "salom"
    # Broadcast'da email hech qachon bo'lmaydi (`_mask`).
    assert event["payload"]["data"]["author"]["email"] is None


@pytest.mark.django_db(transaction=True)
async def test_broadcast_frame_is_json_serialisable(env):
    """Freym `json.dumps()` dan o'tishi SHART.

    WebSocket qatlami `DjangoJSONEncoder` emas, oddiy `json.dumps()`
    ishlatadi: xom `UUID` qolib ketsa soket 1011 bilan uziladi va xabar
    hech kimga yetmaydi.
    """
    import json

    from channels.layers import get_channel_layer
    from asgiref.sync import sync_to_async

    from apps.chat import services

    channel = await sync_to_async(services.create_channel)(
        workspace_id=env.workspace.id, actor=env.owner, name="json"
    )
    layer = get_channel_layer()
    await layer.group_add(f"chat.{channel.id}", "json-channel")
    await sync_to_async(services.post_message)(
        conversation=channel, author=env.owner, body="x"
    )
    frame = await layer.receive("json-channel")
    json.dumps(frame["event"])  # istisno ko'tarmasligi kerak


# ---------------------------------------------------------------- modellar


def test_soft_deleted_message_disappears_from_the_default_manager(env):
    channel = make_channel(env)
    posted = env.owner_client.post(
        messages_url(channel["id"]), {"body": "o'chadi"}, format="json"
    ).json()
    message = Message.objects.get(pk=posted["id"])
    message.delete()
    assert not Message.objects.filter(pk=posted["id"]).exists()
    assert Message.all_objects.filter(pk=posted["id"]).exists()
