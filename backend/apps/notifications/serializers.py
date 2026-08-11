from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(read_only=True, allow_null=True)
    actor = UserSummarySerializer(read_only=True)
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "workspace_id",
            "actor",
            "kind",
            "title",
            "body",
            "url",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields
