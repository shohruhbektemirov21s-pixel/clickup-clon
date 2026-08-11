"""Chat modellari — kanallar va shaxsiy yozishmalar (DM).

Ikkalasi ham BITTA `Conversation` modelida yashaydi. Alohida `Channel` va
`DirectMessage` jadvallari xabar, o'qilganlik va real vaqt qatlamlarini ikki
nusxada yozishga majbur qilardi; farq esa faqat ikkita qoidada:

* `kind == CHANNEL` → `name` bor, a'zolik ochiq (ish maydonining har bir
  a'zosi kira oladi, agar `is_private` bo'lmasa);
* `kind == DIRECT`  → `name` bo'sh, aynan ikkita a'zo, va `dm_key` ular
  juftligini yagona qiladi.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import SoftDeleteModel, TimeStampedModel, UUIDModel


class ConversationKind(models.TextChoices):
    CHANNEL = "channel", "Kanal"
    DIRECT = "direct", "Shaxsiy"


def direct_key(user_a_id, user_b_id) -> str:
    """Ikki foydalanuvchi uchun TARTIBDAN QAT'I NAZAR bir xil kalit.

    Shu kalit `unique_together` bilan birga "A→B va B→A ikkita alohida
    yozishma yaratib yubordi" xatosini DB darajasida imkonsiz qiladi.
    """
    return "|".join(sorted([str(user_a_id), str(user_b_id)]))


class Conversation(UUIDModel, TimeStampedModel):
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="conversations"
    )
    kind = models.CharField(
        max_length=10, choices=ConversationKind.choices, default=ConversationKind.CHANNEL
    )
    #: Kanal nomi. DM uchun bo'sh — sarlavha suhbatdoshdan olinadi.
    name = models.CharField(max_length=80, blank=True, default="")
    topic = models.CharField(max_length=200, blank=True, default="")
    #: Yopiq kanal faqat a'zolariga ko'rinadi.
    is_private = models.BooleanField(default=False)
    #: DM juftligining tartibsiz kaliti; kanallarda bo'sh.
    dm_key = models.CharField(max_length=80, blank=True, default="", db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_conversations",
    )
    #: Ro'yxatni "oxirgi faoliyat" bo'yicha saralash uchun denormallashtirilgan.
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-last_message_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                condition=Q(kind="channel"),
                name="uniq_channel_name_per_workspace",
            ),
            models.UniqueConstraint(
                fields=["workspace", "dm_key"],
                condition=Q(kind="direct"),
                name="uniq_dm_pair_per_workspace",
            ),
            # Kanalning nomi bor, DM ning yo'q — noto'g'ri shakldagi qator
            # umuman yozilmasin.
            models.CheckConstraint(
                condition=(
                    Q(kind="channel", name__gt="") | Q(kind="direct", name="", dm_key__gt="")
                ),
                name="conversation_shape_matches_kind",
            ),
        ]
        indexes = [models.Index(fields=["workspace", "kind"])]

    def __str__(self) -> str:
        return self.name or f"DM {self.dm_key}"


class ConversationMember(UUIDModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_memberships"
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    #: Shu paytgacha o'qilgan — o'qilmaganlar soni shundan hisoblanadi.
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"], name="uniq_conversation_member"
            )
        ]
        indexes = [models.Index(fields=["user", "conversation"])]


class Message(UUIDModel, TimeStampedModel, SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="chat_messages",
    )
    #: Oddiy matn. HTML ATAYLAB emas: chat kiritishi eng ko'p ishlatiladigan
    #: yuza, va u yerda boy matnni qabul qilish saqlangan-XSS uchun eng katta
    #: darvoza. Ko'rsatishda klient matnni matn sifatida chizadi.
    body = models.TextField(max_length=4000)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "-created_at"])]

    def __str__(self) -> str:
        return self.body[:40]
