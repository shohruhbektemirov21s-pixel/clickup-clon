"""`ws/chat/{conversation_id}/` — bitta suhbatning real vaqtli kanali.

Handshake'da ko'rish huquqi tekshiriladi va soket faqat shundan keyin
`chat.<id>` guruhiga qo'shiladi. Guruh — avtorizatsiya chegarasi
(`apps/chat/events.py` izohiga qarang), shuning uchun bu tekshiruvni
o'tkazib yuborish yopiq kanal mazmunini begonaga ochib berardi.

Soket **faqat o'qiydi**: xabar yuborish `POST .../messages/` orqali. Sabab —
yozish yo'li bitta bo'lsa validatsiya, throttle va broadcast ham bitta
joyda qoladi; ikkinchi yozish yo'li ularni takrorlashga majbur qilardi va
ertami-kechmi ajralib ketardi.
"""

from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.chat.events import chat_group


@database_sync_to_async
def _can_read(user, conversation_id) -> bool:
    from apps.chat.services import visible_conversations
    from apps.chat.models import Conversation
    from apps.workspaces.models import WorkspaceMember

    conversation = Conversation.objects.filter(pk=conversation_id).first()
    if conversation is None:
        return False
    if not WorkspaceMember.objects.filter(
        workspace_id=conversation.workspace_id, user=user
    ).exists():
        return False
    return (
        visible_conversations(user, conversation.workspace_id)
        .filter(pk=conversation_id)
        .exists()
    )


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        if not await _can_read(user, self.conversation_id):
            # Mavjud emas va ruxsat yo'q bir xil javob beradi — suhbat
            # borligini oshkor qilmaymiz.
            await self.close(code=4404)
            return

        self.group = chat_group(self.conversation_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "type": "connection.ack",
                "payload": {"data": {"channel": self.group, "user_id": str(user.id)}},
            }
        )

    async def disconnect(self, code):
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """Kiruvchi freymlar e'tiborsiz qoldiriladi — soket faqat o'qish uchun.

        `ping` ga javob beramiz: klient ulanish tirikligini shu bilan
        tekshiradi.
        """
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def broadcast(self, message):
        await self.send_json(message["event"])
