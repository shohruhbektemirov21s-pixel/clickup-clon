import json

from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.core.enums import Priority
from apps.core.sanitize import clean_html
from apps.tasks.models import Tag, Task

MAX_DESCRIPTION_JSON_BYTES = 256 * 1024


class TagSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Tag
        fields = ["id", "workspace_id", "name", "color", "usage_count", "created_at", "updated_at"]
        read_only_fields = ["id", "workspace_id", "usage_count", "created_at", "updated_at"]


class TagSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]


class TaskSerializer(serializers.ModelSerializer):
    list_id = serializers.UUIDField(read_only=True)
    status_id = serializers.UUIDField(read_only=True)
    is_deleted = serializers.ReadOnlyField()
    assignees = serializers.SerializerMethodField()
    watchers = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    created_by = UserSummarySerializer(read_only=True)
    updated_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "list_id",
            "title",
            "description_html",
            "description_json",
            "status_id",
            "priority",
            "position",
            "due_date",
            "start_date",
            "time_estimate_minutes",
            "archived",
            "is_deleted",
            "completed_at",
            "comment_count",
            "assignees",
            "watchers",
            "tags",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_assignees(self, obj):
        rows = sorted(obj.task_assignees.all(), key=lambda r: r.assigned_at)
        return UserSummarySerializer(
            [r.user for r in rows], many=True, context=self.context
        ).data

    def get_watchers(self, obj):
        rows = sorted(obj.task_watchers.all(), key=lambda r: r.created_at)
        return UserSummarySerializer(
            [r.user for r in rows], many=True, context=self.context
        ).data

    def get_tags(self, obj):
        rows = sorted(obj.task_tags.all(), key=lambda r: r.created_at)
        return TagSummarySerializer(
            [r.tag for r in rows], many=True, context=self.context
        ).data


class TaskInputSerializer(serializers.Serializer):
    """Writable task fields for POST lists/{id}/tasks/ and PATCH tasks/{id}/."""

    title = serializers.CharField(max_length=500)
    description_html = serializers.CharField(required=False, allow_blank=True)
    description_json = serializers.JSONField(required=False, allow_null=True)
    status_id = serializers.UUIDField(required=False, allow_null=True)
    priority = serializers.ChoiceField(choices=Priority.choices, required=False)
    due_date = serializers.DateTimeField(required=False, allow_null=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    time_estimate_minutes = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=60 * 24 * 365
    )
    archived = serializers.BooleanField(required=False)
    assignee_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    tag_ids = serializers.ListField(child=serializers.UUIDField(), required=False)

    def __init__(self, *args, partial=False, **kwargs):
        super().__init__(*args, partial=partial, **kwargs)
        if partial:
            self.fields["title"].required = False

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title must not be empty.")
        return value

    def validate_description_html(self, value):
        return clean_html(value)

    def validate_description_json(self, value):
        if value is not None and len(json.dumps(value)) > MAX_DESCRIPTION_JSON_BYTES:
            raise serializers.ValidationError("description_json must be at most 256 KB.")
        return value

    def validate(self, attrs):
        data = self.initial_data or {}
        has_html = "description_html" in data
        has_json = "description_json" in data
        if has_html != has_json:
            raise serializers.ValidationError(
                {
                    "description_html": [
                        "description_html and description_json must be sent together."
                    ]
                }
            )
        start = attrs.get("start_date")
        due = attrs.get("due_date")
        if self.instance_dates_invalid(attrs, start, due):
            raise serializers.ValidationError(
                {"start_date": ["start_date must be on or before due_date."]}
            )
        return attrs

    def instance_dates_invalid(self, attrs, start, due):
        base = getattr(self, "task_instance", None)
        if base is not None:
            if "start_date" not in attrs:
                start = base.start_date
            if "due_date" not in attrs:
                due = base.due_date
        return start is not None and due is not None and start > due
