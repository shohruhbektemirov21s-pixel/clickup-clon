"""Bildirishnoma yaratish — YAGONA kirish nuqtasi.

Har bir chaqiruv `transaction.on_commit` orqali WS freymini chiqaradi, ya'ni
rollback bo'lgan yozuv hech qachon e'lon qilinmaydi (CLAUDE.md konvensiyasi:
real vaqt hodisalari servis qatlamidan chiqadi, view'dan emas).
"""

from __future__ import annotations

from django.db import transaction

from apps.notifications import events
from apps.notifications.models import Notification, NotificationKind


def notify(
    *,
    user,
    kind: str,
    title: str,
    body: str = "",
    url: str = "",
    workspace=None,
    actor=None,
) -> Notification | None:
    """Bitta odamga bitta bildirishnoma.

    O'z harakati uchun xabar yozilmaydi (`actor is user`) — "siz o'zingizni
    qo'shdingiz" turidagi shovqin qo'ng'iroqchani foydasiz qiladi.
    """
    if user is None:
        return None
    if actor is not None and str(getattr(actor, "id", "")) == str(user.id):
        return None

    notification = Notification.objects.create(
        user=user,
        workspace=workspace,
        actor=actor,
        kind=kind,
        title=title[:200],
        body=body[:400],
        url=url[:300],
    )
    transaction.on_commit(lambda: events.emit_notification_created(notification))
    return notification


def notify_many(users, **kwargs) -> list[Notification]:
    """`notify()` ni bir nechta qabul qiluvchiga — takrorlanuvchi id'lar tashlanadi."""
    seen: set[str] = set()
    created = []
    for user in users:
        if user is None or str(user.id) in seen:
            continue
        seen.add(str(user.id))
        notification = notify(user=user, **kwargs)
        if notification is not None:
            created.append(notification)
    return created


def unread_count(user, workspace_id=None) -> int:
    rows = Notification.objects.filter(user=user, read_at__isnull=True)
    if workspace_id:
        rows = rows.filter(workspace_id=workspace_id)
    return rows.count()


__all__ = ["NotificationKind", "notify", "notify_many", "unread_count"]
