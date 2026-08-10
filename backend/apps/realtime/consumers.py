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

# Soket ruxsat o'zgarishidan UZOQ yashaydi, shuning uchun handshake'dagi bir
# martalik tekshiruv yetarli emas: quyidagi freymlar kelganda soket o'z
# doirasini (guruh a'zoligini) qaytadan hisoblaydi va kerak bo'lsa yopiladi.
SCOPE_CHANGING_EVENTS = frozenset({"access.revoked", "permission.updated"})

REVOKED_MESSAGE = "Ushbu resursga kirish huquqi bekor qilindi."


def _presence_summary(user_summary: dict) -> dict:
    return {field: user_summary.get(field) for field in PRESENCE_FIELDS}


@database_sync_to_async
def _list_access(user, list_id):
    """(allowed, presence_summary, workspace_id, space_id).

    Ko'rinuvchanlik REST bilan **bitta** manbadan keladi —
    `apps.core.access.space_is_visible`. Ilgari bu yerda qo'lda yozilgan
    `role == GUEST and space.is_private -> rad` qoidasi turardi va u
    `SpaceMember` qatorlarini ko'rmasdi: bo'limga aniq qo'shilgan mehmon REST
    (`get_list()` -> `check_space_visible`) dan o'tib, soketdan rad etilardi.
    Endi ikkalasi ham bir xil predikatga tayanadi, ya'ni ular hech qachon
    ajralib keta olmaydi.
    """
    from apps.accounts.serializers import UserSummarySerializer
    from apps.core.access import get_membership, space_is_visible
    from apps.workspaces.models import TaskList

    task_list = (
        TaskList.objects.select_related("space", "space__workspace")
        .filter(pk=list_id)
        .first()
    )
    if task_list is None:
        return False, None, None, None
    membership = get_membership(user, task_list.space.workspace_id)
    if membership is None or not space_is_visible(membership, task_list.space):
        return False, None, None, None
    return (
        True,
        _presence_summary(UserSummarySerializer(user).data),
        str(task_list.space.workspace_id),
        str(task_list.space_id),
    )


@database_sync_to_async
def _workspace_scope(user, workspace_id):
    """(a'zomi, ko'rinadigan bo'lim id'lari to'plami) — fail closed.

    `visible_spaces_q` — bo'lim ro'yxatlari uchun REST ishlatadigan aynan o'sha
    filtr (C.5), shuning uchun soket REST 404 beradigan bo'lim haqidagi
    freymga hech qachon obuna bo'lmaydi. A'zolik topilmasa bo'sh to'plam
    qaytadi va chaqiruvchi handshake'ni rad etadi.
    """
    from apps.core.access import get_membership, visible_spaces_q
    from apps.workspaces.models import Space

    membership = get_membership(user, workspace_id)
    if membership is None:
        return False, frozenset()
    space_ids = (
        Space.objects.filter(workspace_id=workspace_id)
        .filter(visible_spaces_q(membership))
        .values_list("id", flat=True)
        .distinct()
    )
    return True, frozenset(str(space_id) for space_id in space_ids)


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
        event_type = event.get("type")
        await self.send_json(event)
        data = (event.get("payload") or {}).get("data") or {}
        # Y-2 - `access.revoked` shaxsiy `user.<id>` kanalidan keladi. Klient
        # cache'ini tozalashi uchun freymning o'zi avval yuboriladi, so'ng
        # bekor qilish haqiqatan shu soketni qamrasa, soket majburan yopiladi.
        # Aks holda REST allaqachon 404 qaytarayotgan bo'lsa-da, ochiq soket
        # bekor qilingan a'zolikka voqealar oqizishda davom etardi.
        if event_type == "access.revoked" and self.revocation_applies(data):
            await self.error_and_close(
                "permission_denied", REVOKED_MESSAGE, CLOSE_ACCESS_REVOKED
            )
            return
        # Soketni yopmaydigan ruxsat o'zgarishi ham guruh a'zoligini
        # eskirtiradi (masalan bo'limdan chiqarilgan a'zoning yon panel
        # soketi hali ham o'sha `space.<id>` guruhida turadi).
        if event_type in SCOPE_CHANGING_EVENTS:
            await self.resync_scope()

    async def resync_scope(self):
        """Ruxsat o'zgargandan keyin doirani qayta baholaydi (standarti: yo'q)."""
        return

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

    async def resync_scope(self):
        """Ruxsat o'zgardi — shu ro'yxatni hali ham o'qiy olamizmi?

        `revocation_applies` qamramagan holatlar uchun (masalan matritsa
        o'zgarib rol `space.read_private` ni yo'qotdi) yagona haqiqat manbai
        `_list_access` qayta so'raladi. Fail-closed: o'qiy olmasak — 4403.
        """
        if not getattr(self, "joined", False):
            return
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            return
        allowed, *_ = await _list_access(user, self.list_id)
        if not allowed:
            await self.error_and_close(
                "permission_denied", REVOKED_MESSAGE, CLOSE_ACCESS_REVOKED
            )

    async def handle_json(self, content):
        # Closed client vocabulary: presence.ping / presence.typing; ignore the rest.
        if content.get("type") not in ("presence.ping", "presence.typing"):
            return


class WorkspaceConsumer(BaseConsumer):
    """Yon panel soketi — `list.updated` va ierarxiya o'zgarishlari.

    Ilgari bu soket faqat `workspace.<id>` guruhiga qo'shilardi va o'sha guruh
    butun ish maydonining `task.*` / `list.updated` freymlarini olib yurardi:
    yopiq bo'limga kirish huquqi bo'lmagan mehmon REST'da 404 oladigan
    ro'yxatning nomini, vazifa sarlavhasini va tavsifini soket orqali o'qib
    olardi. Endi soket faqat **o'ziga ko'rinadigan** `space.<id>` guruhlariga
    qo'shiladi (`visible_spaces_q`), `workspace.<id>` esa faqat mazmun olib
    yurmaydigan `permission.updated` uchun qoladi.
    """

    channel = "workspace"

    async def connect(self):
        self.workspace_id = self.scope["url_route"]["kwargs"]["workspace_id"]
        self.group = events.workspace_group(self.workspace_id)
        self.space_groups: set[str] = set()
        self.joined = False
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close()
            return
        allowed, space_ids = await _workspace_scope(user, self.workspace_id)
        if not allowed:
            await self.send_error_and_close("permission_denied", "Not a workspace member.")
            return
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.channel_layer.group_add(events.user_group(user.id), self.channel_name)
        await self._sync_space_groups(space_ids)
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

    async def _sync_space_groups(self, space_ids):
        """Guruh a'zoligini ko'rinadigan bo'limlar to'plamiga tenglashtiradi."""
        wanted = {events.space_group(space_id) for space_id in space_ids}
        for group in wanted - self.space_groups:
            await self.channel_layer.group_add(group, self.channel_name)
        for group in self.space_groups - wanted:
            await self.channel_layer.group_discard(group, self.channel_name)
        self.space_groups = wanted

    async def disconnect(self, code):
        if not getattr(self, "joined", False):
            return
        user = self.scope.get("user")
        await self.channel_layer.group_discard(self.group, self.channel_name)
        for group in getattr(self, "space_groups", set()):
            await self.channel_layer.group_discard(group, self.channel_name)
        self.space_groups = set()
        if user is not None and not user.is_anonymous:
            await self.channel_layer.group_discard(
                events.user_group(user.id), self.channel_name
            )

    def revocation_applies(self, data) -> bool:
        """Bo'limdan chiqarish workspace a'zoligini olib tashlamaydi, shuning
        uchun yon panel soketi faqat workspace darajasidagi bekor qilishda
        (`space_id is None`) yopiladi. Bo'lim darajasidagisi soketni yopmaydi —
        u `resync_scope()` orqali o'sha bo'lim guruhidan chiqib ketadi."""
        return data.get("space_id") is None and self._same_workspace(data)

    async def resync_scope(self):
        if not getattr(self, "joined", False):
            return
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            return
        allowed, space_ids = await _workspace_scope(user, self.workspace_id)
        if not allowed:
            await self.error_and_close(
                "permission_denied", REVOKED_MESSAGE, CLOSE_ACCESS_REVOKED
            )
            return
        await self._sync_space_groups(space_ids)
