"""Channels consumers for the list and workspace channels (contract §15)."""

import time
from collections import defaultdict

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.realtime import events

# In-process presence registry: {list_id: {user_id: {"count": n, "user": summary}}}
#
# O-9a: `list_id` kaliti oxirgi foydalanuvchi chiqishi bilan **o'chiriladi**.
# Aks holda har ochilgan ro'yxat jarayon xotirasida abadiy bo'sh dict qoldirar
# edi - uzoq ishlaydigan worker uchun sekin, lekin cheksiz sizish.
_PRESENCE: dict[str, dict[str, dict]] = defaultdict(dict)

# Ilova darajasidagi yopish kodlari (4000-4999 diapazoni).
CLOSE_ACCESS_REVOKED = 4403
CLOSE_RATE_LIMITED = 4029

# O-9b: kiruvchi freymlar uchun token-bucket - 10 soniyada 30 xabar.
# Sig'im 30 (qisqa portlash o'tadi), to'ldirish 3 token/soniya.
INBOUND_BURST = 30
INBOUND_WINDOW_SECONDS = 10.0

# O-9c: presence freymlari HECH QACHON email olib yurmaydi. Ro'yxatni o'qiy
# oladigan har qanday odam (jumladan mehmon) presence orqali butun jamoaning
# ish pochtasini yig'ib ololmasligi kerak.
PRESENCE_FIELDS = ("id", "full_name", "avatar", "avatar_color")


def _presence_summary(user_summary: dict) -> dict:
    return {field: user_summary.get(field) for field in PRESENCE_FIELDS}


@database_sync_to_async
def _list_access(user, list_id):
    """(allowed, presence_summary, workspace_id, space_id) - mehmon yopiq bo'limni o'qiy olmaydi."""
    from apps.accounts.serializers import UserSummarySerializer
    from apps.core.enums import WorkspaceRole
    from apps.workspaces.models import TaskList, WorkspaceMember

    task_list = (
        TaskList.objects.select_related("space").filter(pk=list_id).first()
    )
    if task_list is None:
        return False, None, None, None
    membership = WorkspaceMember.objects.filter(
        workspace_id=task_list.space.workspace_id, user=user
    ).first()
    if membership is None:
        return False, None, None, None
    if membership.role == WorkspaceRole.GUEST and task_list.space.is_private:
        return False, None, None, None
    return (
        True,
        _presence_summary(UserSummarySerializer(user).data),
        str(task_list.space.workspace_id),
        str(task_list.space_id),
    )


@database_sync_to_async
def _workspace_access(user, workspace_id):
    from apps.workspaces.models import WorkspaceMember

    return WorkspaceMember.objects.filter(workspace_id=workspace_id, user=user).exists()


class BaseConsumer(AsyncJsonWebsocketConsumer):
    #: Shu soket qaysi doiraga tegishli - `access.revoked` ni baholash uchun.
    workspace_id = None
    space_id = None

    # ----------------------------------------------------------------- error

    async def send_error_and_close(self, code, message, close_code=None):
        """Handshake rad etildi: accept -> bitta `error` freymi -> close."""
        await self.accept()
        await self.error_and_close(code, message, close_code)

    async def error_and_close(self, code, message, close_code=None):
        """Ochiq soketni §15.3 bo'yicha `error` freymi bilan yopadi."""
        await self.send_json(
            {"type": "error", "payload": {"code": code, "message": message}}
        )
        if close_code is None:
            await self.close()
        else:
            await self.close(code=close_code)

    # ------------------------------------------------------------- broadcast

    async def broadcast(self, message):
        event = message["event"]
        await self.send_json(event)
        # Y-2 - `access.revoked` shaxsiy `user.<id>` kanalidan keladi. Klient
        # cache'ini tozalashi uchun freymning o'zi avval yuboriladi, so'ng
        # bekor qilish haqiqatan shu soketni qamrasa, soket majburan yopiladi.
        # Aks holda REST allaqachon 404 qaytarayotgan bo'lsa-da, ochiq soket
        # bekor qilingan a'zolikka voqealar oqizishda davom etardi.
        if event.get("type") == "access.revoked":
            data = (event.get("payload") or {}).get("data") or {}
            if self.revocation_applies(data):
                await self.error_and_close(
                    "permission_denied",
                    "Ushbu resursga kirish huquqi bekor qilindi.",
                    CLOSE_ACCESS_REVOKED,
                )

    def revocation_applies(self, data) -> bool:  # pragma: no cover - abstract
        raise NotImplementedError

    def _same_workspace(self, data) -> bool:
        revoked = data.get("workspace_id")
        return bool(revoked) and str(revoked) == str(self.workspace_id)

    # ------------------------------------------------------------ rate limit

    def _inbound_allowed(self) -> bool:
        """Soket bo'yicha token-bucket (O-9b)."""
        now = time.monotonic()
        tokens = getattr(self, "_inbound_tokens", None)
        if tokens is None:
            tokens = float(INBOUND_BURST)
        else:
            elapsed = now - self._inbound_checked_at
            tokens = min(
                float(INBOUND_BURST),
                tokens + elapsed * (INBOUND_BURST / INBOUND_WINDOW_SECONDS),
            )
        self._inbound_checked_at = now
        if tokens < 1.0:
            self._inbound_tokens = tokens
            return False
        self._inbound_tokens = tokens - 1.0
        return True

    async def receive_json(self, content, **kwargs):
        if not self._inbound_allowed():
            await self.error_and_close(
                "throttled",
                "Juda ko'p xabar yuborildi.",
                CLOSE_RATE_LIMITED,
            )
            return
        await self.handle_json(content)

    async def handle_json(self, content):
        """Klient lug'ati - sinflarda qayta aniqlanadi. Standarti: e'tiborsiz."""
        return


class ListConsumer(BaseConsumer):
    channel = "list"

    async def connect(self):
        self.list_id = self.scope["url_route"]["kwargs"]["list_id"]
        self.group = events.list_group(self.list_id)
        self.joined = False
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close()
            return
        allowed, summary, workspace_id, space_id = await _list_access(user, self.list_id)
        if not allowed:
            await self.send_error_and_close("permission_denied", "No access to this list.")
            return

        self.user_summary = summary
        self.workspace_id = workspace_id
        self.space_id = space_id
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.channel_layer.group_add(events.user_group(user.id), self.channel_name)
        await self.accept()
        self.joined = True
        await self.send_json(
            {
                "type": "connection.ack",
                "payload": {
                    "data": {"channel": f"list.{self.list_id}", "user_id": str(user.id)}
                },
            }
        )

        # presence
        entry = _PRESENCE[self.list_id].setdefault(str(user.id), {"count": 0, "user": summary})
        entry["count"] += 1
        if entry["count"] == 1:
            await self.channel_layer.group_send(
                self.group,
                {
                    "type": "broadcast",
                    "event": {"type": "presence.join", "payload": {"data": {"user": summary}}},
                },
            )
        users = [e["user"] for e in _PRESENCE[self.list_id].values()]
        await self.send_json({"type": "presence.sync", "payload": {"data": {"users": users}}})

    async def disconnect(self, code):
        if not getattr(self, "joined", False):
            return
        user = self.scope.get("user")
        await self.channel_layer.group_discard(self.group, self.channel_name)
        if user is not None and not user.is_anonymous:
            await self.channel_layer.group_discard(
                events.user_group(user.id), self.channel_name
            )
            # `.get()` ataylab: `_PRESENCE` defaultdict bo'lgani uchun oddiy
            # o'qish ham yangi kalit yaratib yuborardi.
            bucket = _PRESENCE.get(self.list_id)
            entry = bucket.get(str(user.id)) if bucket else None
            if entry:
                entry["count"] -= 1
                if entry["count"] <= 0:
                    bucket.pop(str(user.id), None)
                    if not bucket:
                        # O-9a: oxirgi kuzatuvchi ketdi -> kalit ham ketsin.
                        _PRESENCE.pop(self.list_id, None)
                    await self.channel_layer.group_send(
                        self.group,
                        {
                            "type": "broadcast",
                            "event": {
                                "type": "presence.leave",
                                "payload": {"data": {"user": self.user_summary}},
                            },
                        },
                    )

    def revocation_applies(self, data) -> bool:
        """Workspace darajasidagi bekor qilish har doim tegadi; bo'lim
        darajasidagisi faqat shu ro'yxat o'sha bo'limda bo'lsa."""
        if not self._same_workspace(data):
            return False
        space_id = data.get("space_id")
        return space_id is None or str(space_id) == str(self.space_id)

    async def handle_json(self, content):
        # Closed client vocabulary: presence.ping / presence.typing; ignore the rest.
        if content.get("type") not in ("presence.ping", "presence.typing"):
            return


class WorkspaceConsumer(BaseConsumer):
    channel = "workspace"

    async def connect(self):
        self.workspace_id = self.scope["url_route"]["kwargs"]["workspace_id"]
        self.group = events.workspace_group(self.workspace_id)
        self.joined = False
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close()
            return
        if not await _workspace_access(user, self.workspace_id):
            await self.send_error_and_close("permission_denied", "Not a workspace member.")
            return
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.channel_layer.group_add(events.user_group(user.id), self.channel_name)
        await self.accept()
        self.joined = True
        await self.send_json(
            {
                "type": "connection.ack",
                "payload": {
                    "data": {
                        "channel": f"workspace.{self.workspace_id}",
                        "user_id": str(user.id),
                    }
                },
            }
        )

    async def disconnect(self, code):
        if not getattr(self, "joined", False):
            return
        user = self.scope.get("user")
        await self.channel_layer.group_discard(self.group, self.channel_name)
        if user is not None and not user.is_anonymous:
            await self.channel_layer.group_discard(
                events.user_group(user.id), self.channel_name
            )

    def revocation_applies(self, data) -> bool:
        """Bo'limdan chiqarish workspace a'zoligini olib tashlamaydi, shuning
        uchun yon panel soketi faqat workspace darajasidagi bekor qilishda
        (`space_id is None`) yopiladi."""
        return data.get("space_id") is None and self._same_workspace(data)
