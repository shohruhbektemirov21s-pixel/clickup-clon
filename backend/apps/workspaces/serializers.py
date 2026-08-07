from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.core.enums import InvitationRole, InvitationStatus, StatusType
from apps.workspaces.models import (
    Folder,
    Invitation,
    Space,
    Status,
    StatusSet,
    TaskList,
    Workspace,
    WorkspaceMember,
)


class WorkspaceSerializer(serializers.ModelSerializer):
    owner_id = serializers.UUIDField(read_only=True)
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "color",
            "avatar",
            "owner_id",
            "member_count",
            "my_role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "avatar", "owner_id", "member_count", "created_at", "updated_at"]

    def get_my_role(self, obj):
        roles = self.context.get("roles")
        if roles is not None:
            return roles.get(str(obj.id))
        membership = self.context.get("membership")
        if membership is not None and membership.workspace_id == obj.id:
            return membership.role
        return None


class MemberSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    invited_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = [
            "id",
            "user",
            "role",
            "invited_by_id",
            "joined_at",
            "last_active_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class InvitationSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(read_only=True)
    invited_by = UserSummarySerializer(read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id",
            "workspace_id",
            "email",
            "role",
            "status",
            "invited_by",
            "expires_at",
            "accepted_at",
            "revoked_at",
            "sent_count",
            "last_sent_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        from django.utils import timezone

        if obj.status == InvitationStatus.PENDING and obj.expires_at < timezone.now():
            return InvitationStatus.EXPIRED.value
        return obj.status


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=InvitationRole.choices)


class SpaceSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(read_only=True)
    created_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Space
        fields = [
            "id",
            "workspace_id",
            "name",
            "description",
            "color",
            "icon",
            "is_private",
            "archived",
            "position",
            "created_by_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "workspace_id",
            "position",
            "created_by_id",
            "created_at",
            "updated_at",
        ]


class FolderSerializer(serializers.ModelSerializer):
    space_id = serializers.UUIDField(read_only=True)
    created_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Folder
        fields = [
            "id",
            "space_id",
            "name",
            "color",
            "archived",
            "position",
            "created_by_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "space_id", "position", "created_by_id", "created_at", "updated_at"]


class ListSerializer(serializers.ModelSerializer):
    space_id = serializers.UUIDField(read_only=True)
    folder_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = TaskList
        fields = [
            "id",
            "space_id",
            "folder_id",
            "name",
            "description",
            "color",
            "archived",
            "default_view",
            "task_count",
            "open_task_count",
            "position",
            "created_by_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "space_id",
            "folder_id",
            "task_count",
            "open_task_count",
            "position",
            "created_by_id",
            "created_at",
            "updated_at",
        ]


class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        fields = ["id", "name", "color", "type", "order", "is_default"]
        read_only_fields = fields


class StatusSetSerializer(serializers.ModelSerializer):
    space_id = serializers.UUIDField(read_only=True, allow_null=True)
    list_id = serializers.UUIDField(read_only=True, allow_null=True)
    statuses = StatusSerializer(many=True, read_only=True)

    class Meta:
        model = StatusSet
        fields = ["id", "name", "space_id", "list_id", "statuses", "created_at", "updated_at"]
        read_only_fields = fields


class StatusInputSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    name = serializers.CharField(max_length=60)
    color = serializers.RegexField(r"^#[0-9A-F]{6}$", required=False, default="#87909E")
    type = serializers.ChoiceField(choices=StatusType.choices)
    is_default = serializers.BooleanField(required=False, default=False)


class StatusSetInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80, required=False)
    statuses = StatusInputSerializer(many=True)
    status_mapping = serializers.DictField(
        child=serializers.UUIDField(), required=False, default=dict
    )

    def validate_statuses(self, statuses):
        if not 1 <= len(statuses) <= 30:
            raise serializers.ValidationError("A status set must have between 1 and 30 statuses.")
        defaults = [s for s in statuses if s.get("is_default")]
        if len(defaults) != 1:
            raise serializers.ValidationError("Exactly one status must be is_default.")
        if defaults[0]["type"] == StatusType.CLOSED:
            raise serializers.ValidationError("The default status must not be closed-type.")
        if not any(s["type"] == StatusType.CLOSED for s in statuses):
            raise serializers.ValidationError("At least one status must be closed-type.")
        names = [s["name"].strip().lower() for s in statuses]
        if len(set(names)) != len(names):
            raise serializers.ValidationError("Status names must be unique (case-insensitive).")
        ids = [str(s["id"]) for s in statuses if s.get("id")]
        if len(set(ids)) != len(ids):
            raise serializers.ValidationError("Duplicate status ids in payload.")
        return statuses
