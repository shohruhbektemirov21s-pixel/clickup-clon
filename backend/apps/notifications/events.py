"""Bildirishnoma broadcast'lari — `user.<id>` shaxsiy guruhiga.

Guruh avtorizatsiya chegarasi (`apps/realtime/events.py` dagi qoida):
`user.<id>` da faqat o'sha odamning soketlari turadi, shuning uchun
bildirishnoma boshqa hech kimga ketmaydi.

Freym `apps/chat/events.py` bilan bir xil konvertda (§15.2) — `actor` bor,
`data` esa REST'dagi `Notification` obyektining o'zi.
"""

from __future__ import annotations

import uuid

from apps.realtime.events import _mask, _send, _ts, user_group


def _frame(data: dict, *, actor=None) -> dict:
    return {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "ts": _ts(),
        "actor": {"id": str(actor.id) if actor is not None else None, "client_id": None},
        "data": _mask(data),
    }


def emit_notification_created(notification) -> None:
    from apps.notifications.serializers import NotificationSerializer

    _send(
        user_group(notification.user_id),
        "notification.created",
        _frame(NotificationSerializer(notification).data, actor=notification.actor),
    )
