from __future__ import annotations

from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.chat.models import Conversation, ConversationKind, Message


class MessageSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)
    # E'lon qilinmasa DRF `ReadOnlyField` yasab XOM `UUID` obyektini beradi.
    # REST'da bu `DjangoJSONEncoder` bilan o'tib ketadi, lekin WebSocket
    # freymi oddiy `json.dumps()` dan o'tadi va u yerda `TypeError` bo'ladi
    # (loyiha kelishuvi: har `*_id` — `UUIDField(read_only=True)`).
    conversation_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "conversation_id", "author", "body", "edited_at", "created_at"]
        read_only_fields = fields


class MessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000, allow_blank=False, trim_whitespace=True)


class ConversationSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(read_only=True)
    #: DM uchun suhbatdosh; kanal uchun `null`.
    peer = serializers.SerializerMethodField()
    #: Ro'yxatni chizishda so'nggi xabar ko'rinib tursin — alohida so'rov
    #: kerak bo'lmasin.
    last_message = serializers.SerializerMethodField()
    unread = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "workspace_id",
            "kind",
            "name",
            "title",
            "topic",
            "is_private",
            "peer",
            "last_message",
            "last_message_at",
            "unread",
            "is_member",
            "created_at",
        ]
        read_only_fields = fields

    def _me(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_title(self, obj) -> str:
        """Ro'yxatda ko'rinadigan nom — DM uchun suhbatdoshning ismi."""
        if obj.kind == ConversationKind.CHANNEL:
            return obj.name
        peer = self.get_peer(obj)
        if peer:
            return peer.get("full_name") or "Shaxsiy yozishma"
        return "Shaxsiy yozishma"

    def get_peer(self, obj):
        if obj.kind != ConversationKind.DIRECT:
            return None
        me = self._me()
        for member in obj.members.all():
            if me is None or member.user_id != me.id:
                return UserSummarySerializer(member.user, context=self.context).data
        return None

    def get_last_message(self, obj):
        # `prefetch_related` bilan oldindan yuklangan bo'lsa qo'shimcha
        # so'rov ketmaydi (`views.py` dagi `Prefetch` ga qarang).
        messages = getattr(obj, "recent_messages", None)
        if messages:
            return MessageSerializer(messages[0], context=self.context).data
        return None

    def get_unread(self, obj) -> int:
        me = self._me()
        if me is None or not me.is_authenticated:
            return 0
        from apps.chat.services import unread_count

        return unread_count(obj, me)

    def get_is_member(self, obj) -> bool:
        me = self._me()
        if me is None or not me.is_authenticated:
            return False
        return any(member.user_id == me.id for member in obj.members.all())


class ChannelCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80, trim_whitespace=True)
    topic = serializers.CharField(max_length=200, allow_blank=True, required=False, default="")
    is_private = serializers.BooleanField(required=False, default=False)


class DirectCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
