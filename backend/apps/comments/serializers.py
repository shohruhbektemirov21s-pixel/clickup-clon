from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.comments.models import Comment
from apps.core.sanitize import clean_html

MAX_BODY_CHARS = 20_000


class CommentSerializer(serializers.ModelSerializer):
    task_id = serializers.UUIDField(read_only=True)
    parent_id = serializers.UUIDField(read_only=True, allow_null=True)
    author = UserSummarySerializer(read_only=True)
    is_deleted = serializers.ReadOnlyField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "task_id",
            "parent_id",
            "author",
            "body_html",
            "body_json",
            "is_edited",
            "edited_at",
            "reply_count",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CommentInputSerializer(serializers.Serializer):
    body_html = serializers.CharField(allow_blank=True, required=False)
    body_json = serializers.JSONField(allow_null=True, required=False)
    parent_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        data = self.initial_data or {}
        if "body_html" not in data or "body_json" not in data:
            raise serializers.ValidationError(
                {"body_html": ["body_html and body_json are both required."]}
            )
        cleaned = clean_html(attrs.get("body_html", ""))
        if not cleaned.strip():
            raise serializers.ValidationError(
                {"body_html": ["Comment body must not be empty."]}
            )
        if len(cleaned) > MAX_BODY_CHARS:
            raise serializers.ValidationError(
                {"body_html": ["Comment body must be at most 20000 characters."]}
            )
        attrs["body_html"] = cleaned
        return attrs
