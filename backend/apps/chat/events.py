"""Chat broadcast'lari.

Guruh nomi — `chat.<conversation_id>`. Bu **avtorizatsiya chegarasi**:
freym bir marta serializatsiya qilinib butun guruhga tarqaladi, shuning
uchun guruhga faqat shu suhbatni o'qishga haqli soketlar qo'shiladi
(`consumers.ChatConsumer` handshake'da tekshiradi). Mavjud
`apps/realtime/events.py` dagi qoida bilan bir xil printsip.

Email maskalash ham o'sha yerdagi sababga ko'ra: bitta payload turli
huquqdagi odamlarga boradi, shuning uchun har bir qabul qiluvchi uchun
alohida maskalash mumkin emas — email umuman yuborilmaydi.
"""

from __future__ import annotations

import uuid

from apps.realtime.events import _mask, _send, _ts


def chat_group(conversation_id) -> str:
    return f"chat.{conversation_id}"


def _frame(data: dict, *, actor=None, client_id=None) -> dict:
    """`apps/realtime/events._payload()` bilan bir xil konvert (§15.2)."""
    return {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "ts": _ts(),
        "actor": {
            "id": str(actor.id) if actor is not None else None,
            "client_id": client_id or None,
        },
        "data": _mask(data),
    }


def emit_message_created(message, *, client_id=None) -> None:
    from apps.chat.serializers import MessageSerializer

    _send(
        chat_group(message.conversation_id),
        "chat.message.created",
        _frame(MessageSerializer(message).data, actor=message.author, client_id=client_id),
    )
