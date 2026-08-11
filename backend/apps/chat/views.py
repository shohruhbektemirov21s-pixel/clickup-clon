from __future__ import annotations

from django.db.models import Prefetch
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.chat import services
from apps.chat.models import ConversationMember, Message
from apps.chat.serializers import (
    ChannelCreateSerializer,
    ConversationSerializer,
    DirectCreateSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)
from apps.core.access import require_membership
from apps.core.api import paginate


def _with_related(queryset):
    """Ro'yxat uchun N+1 ni yopadi.

    `members__user` — DM sarlavhasi va `is_member` uchun; `recent_messages`
    — ro'yxatdagi so'nggi xabar uchun. Ularsiz 30 ta suhbatlik ro'yxat 90 dan
    ortiq so'rov qilardi.
    """
    return queryset.select_related("workspace").prefetch_related(
        "members__user",
        Prefetch(
            "messages",
            queryset=Message.objects.select_related("author").order_by("-created_at")[:1],
            to_attr="recent_messages",
        ),
    )


class ConversationListView(APIView):
    """`GET/POST workspaces/{id}/chat/channels/` — kanallar."""

    def get(self, request, workspace_id):
        require_membership(request.user, workspace_id)
        conversations = _with_related(
            services.visible_conversations(request.user, workspace_id)
        )
        return paginate(request, conversations, ConversationSerializer)

    def post(self, request, workspace_id):
        serializer = ChannelCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = services.create_channel(
            workspace_id=workspace_id, actor=request.user, **serializer.validated_data
        )
        return Response(
            ConversationSerializer(
                _with_related(type(conversation).objects.filter(pk=conversation.pk)).first(),
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class DirectConversationView(APIView):
    """`POST workspaces/{id}/chat/direct/` — DM ochadi yoki mavjudini qaytaradi."""

    def post(self, request, workspace_id):
        serializer = DirectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = services.get_or_create_dm(
            workspace_id=workspace_id,
            actor=request.user,
            other_user_id=serializer.validated_data["user_id"],
        )
        return Response(
            ConversationSerializer(
                _with_related(type(conversation).objects.filter(pk=conversation.pk)).first(),
                context={"request": request},
            ).data
        )


class JoinConversationView(APIView):
    def post(self, request, conversation_id):
        conversation = services._require_conversation(request.user, conversation_id)
        services.join_channel(conversation=conversation, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageListView(APIView):
    """`GET/POST chat/conversations/{id}/messages/`."""

    throttle_scope = "chat"

    def get_throttles(self):
        # O'qish bo'g'ilmaydi: chat ochilganda tarix bir marta yuklanadi.
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def get(self, request, conversation_id):
        conversation = services._require_conversation(request.user, conversation_id)
        messages = (
            Message.objects.filter(conversation=conversation)
            .select_related("author")
            .order_by("-created_at")
        )
        # O'qilgan deb belgilash: ro'yxatni ochish = o'qish.
        if ConversationMember.objects.filter(conversation=conversation, user=request.user).exists():
            services.mark_read(conversation=conversation, user=request.user)
        return paginate(request, messages, MessageSerializer)

    def post(self, request, conversation_id):
        conversation = services.require_participant(request.user, conversation_id)
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = services.post_message(
            conversation=conversation,
            author=request.user,
            body=serializer.validated_data["body"],
        )
        return Response(
            MessageSerializer(message, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
