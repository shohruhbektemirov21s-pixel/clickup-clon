"""Chat servis qatlami — yozish AMALLARINING yagona joyi.

Real vaqt hodisalari SHU YERDAN chiqadi, view'lardan emas (loyiha
kelishuvi): shunda REST javobi va WebSocket freymi bir xil serializerdan
o'tadi va bir-biridan ajralib ketmaydi.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.chat.models import (
    Conversation,
    ConversationKind,
    ConversationMember,
    Message,
    direct_key,
)
from apps.core.access import require_membership
from apps.workspaces.models import WorkspaceMember


def visible_conversations(user, workspace_id):
    """Foydalanuvchi ko'ra oladigan suhbatlar.

    * ochiq kanallar — ish maydonining har bir a'zosiga;
    * yopiq kanal va DM — faqat a'zosiga.

    DM hech qachon "ochiq" bo'lmaydi, shuning uchun u ikkinchi shartga
    tushadi va begona odam uni ro'yxatda ham ko'rmaydi.
    """
    from django.db.models import Q

    return (
        Conversation.objects.filter(workspace_id=workspace_id)
        .filter(Q(kind=ConversationKind.CHANNEL, is_private=False) | Q(members__user=user))
        .distinct()
    )


def _require_conversation(user, conversation_id) -> Conversation:
    """Suhbatni oladi va ko'rish huquqini tekshiradi.

    Ko'rinmasa `404` — `403` emas. Ish maydonidan tashqaridagi resurs
    mavjudligini oshkor qilmaslik loyihaning umumiy qoidasi
    (`API_CONTRACT` §1.7), va yopiq kanal ham xuddi shunday.
    """
    conversation = (
        Conversation.objects.filter(pk=conversation_id).select_related("workspace").first()
    )
    if conversation is None:
        raise NotFound()
    require_membership(user, conversation.workspace_id)
    if not visible_conversations(user, conversation.workspace_id).filter(pk=conversation_id).exists():
        raise NotFound()
    return conversation


def require_participant(user, conversation_id) -> Conversation:
    """Ko'rish EMAS, yozish uchun: a'zolik shart."""
    conversation = _require_conversation(user, conversation_id)
    if not ConversationMember.objects.filter(conversation=conversation, user=user).exists():
        # Ochiq kanalga yozish uchun avval qo'shilish kerak — bu ataylab
        # aniq qadam, chunki a'zolik "o'qilmagan" hisobini va bildirishnomani
        # ham yoqadi.
        raise PermissionDenied("Avval kanalga qo'shiling.")
    return conversation


@transaction.atomic
def create_channel(*, workspace_id, actor, name, topic="", is_private=False) -> Conversation:
    name = (name or "").strip()
    if not name:
        raise ValidationError({"name": ["Kanal nomi bo'sh bo'lishi mumkin emas."]})

    require_membership(actor, workspace_id)
    try:
        conversation = Conversation.objects.create(
            workspace_id=workspace_id,
            kind=ConversationKind.CHANNEL,
            name=name,
            topic=(topic or "").strip(),
            is_private=is_private,
            created_by=actor,
        )
    except IntegrityError:
        raise ValidationError({"name": ["Bu nomli kanal allaqachon bor."]}) from None

    ConversationMember.objects.create(conversation=conversation, user=actor)
    return conversation


@transaction.atomic
def get_or_create_dm(*, workspace_id, actor, other_user_id) -> Conversation:
    """Ikki a'zo o'rtasidagi yozishmani qaytaradi, kerak bo'lsa yaratadi."""
    if str(actor.id) == str(other_user_id):
        raise ValidationError({"user_id": ["O'zingiz bilan yozisha olmaysiz."]})

    require_membership(actor, workspace_id)
    # Suhbatdosh ham SHU ish maydonining a'zosi bo'lishi shart — aks holda
    # DM ish maydoni chegarasini kesib o'tadigan yo'lga aylanardi.
    other = (
        WorkspaceMember.objects.filter(workspace_id=workspace_id, user_id=other_user_id)
        .select_related("user")
        .first()
    )
    if other is None:
        raise NotFound()

    key = direct_key(actor.id, other_user_id)
    existing = Conversation.objects.filter(
        workspace_id=workspace_id, kind=ConversationKind.DIRECT, dm_key=key
    ).first()
    if existing is not None:
        return existing

    conversation = Conversation.objects.create(
        workspace_id=workspace_id,
        kind=ConversationKind.DIRECT,
        name="",
        dm_key=key,
        created_by=actor,
    )
    ConversationMember.objects.bulk_create(
        [
            ConversationMember(conversation=conversation, user=actor),
            ConversationMember(conversation=conversation, user=other.user),
        ]
    )
    return conversation


@transaction.atomic
def join_channel(*, conversation, user) -> ConversationMember:
    if conversation.kind != ConversationKind.CHANNEL:
        raise PermissionDenied("Shaxsiy yozishmaga qo'shilib bo'lmaydi.")
    if conversation.is_private:
        raise PermissionDenied("Bu yopiq kanal — sizni a'zo qo'shishi kerak.")
    member, _ = ConversationMember.objects.get_or_create(conversation=conversation, user=user)
    return member


@transaction.atomic
def post_message(*, conversation, author, body: str) -> Message:
    body = (body or "").strip()
    if not body:
        raise ValidationError({"body": ["Xabar bo'sh bo'lishi mumkin emas."]})

    message = Message.objects.create(conversation=conversation, author=author, body=body)

    # `last_message_at` — ro'yxatni saralash uchun; xabar bilan bitta
    # tranzaksiyada yangilanadi, aks holda ro'yxat tartibi xabardan orqada
    # qolardi.
    Conversation.objects.filter(pk=conversation.pk).update(
        last_message_at=message.created_at, updated_at=timezone.now()
    )
    # Yozgan odam o'z xabarini o'qigan hisoblanadi.
    ConversationMember.objects.filter(conversation=conversation, user=author).update(
        last_read_at=message.created_at
    )

    from apps.chat import events

    transaction.on_commit(lambda: events.emit_message_created(message))
    return message


def mark_read(*, conversation, user) -> None:
    ConversationMember.objects.filter(conversation=conversation, user=user).update(
        last_read_at=timezone.now()
    )


def unread_count(conversation, user) -> int:
    membership = ConversationMember.objects.filter(
        conversation=conversation, user=user
    ).first()
    if membership is None:
        return 0
    queryset = Message.objects.filter(conversation=conversation).exclude(author=user)
    if membership.last_read_at is not None:
        queryset = queryset.filter(created_at__gt=membership.last_read_at)
    return queryset.count()
