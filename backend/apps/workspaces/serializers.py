from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.core.enums import (
    AssignableRole,
    InvitationRole,
    InvitationStatus,
    SpaceAccess,
    StatusType,
)
from apps.workspaces.models import (
    Folder,
    Invitation,
    RolePermission,
    Space,
    SpaceMember,
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
            "permissions_version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "avatar",
            "owner_id",
            "member_count",
            "permissions_version",
            "created_at",
            "updated_at",
        ]

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


class MemberProfileSpaceSerializer(serializers.Serializer):
    """Bir bo'lim + shu a'zoning undagi ochiq vazifalari (§4.1).

    Faqat CHAQIRUVCHIGA ko'rinadigan bo'limlar keladi (`visible_spaces_q`).
    """

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    color = serializers.CharField(read_only=True)
    open_tasks = serializers.IntegerField(read_only=True)


class MemberProfileStatsSerializer(serializers.Serializer):
    """§4.1 statistikalari — hammasi chaqiruvchining ko'rish doirasida."""

    open_tasks = serializers.IntegerField(read_only=True)
    overdue_tasks = serializers.IntegerField(read_only=True)
    due_today = serializers.IntegerField(read_only=True)
    completed_tasks = serializers.IntegerField(read_only=True)
    created_tasks = serializers.IntegerField(read_only=True)
    comments = serializers.IntegerField(read_only=True)


class MemberProfileSerializer(serializers.Serializer):
    """`GET workspaces/{id}/members/{user_id}/profile/` — docs/API_CONTRACT.md §4.1."""

    user = UserSummarySerializer(read_only=True)
    role = serializers.CharField(read_only=True)
    joined_at = serializers.DateTimeField(read_only=True)
    last_active_at = serializers.DateTimeField(read_only=True)
    stats = MemberProfileStatsSerializer(read_only=True)
    spaces = MemberProfileSpaceSerializer(many=True, read_only=True)


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


# ------------------------------------------------------------------ permissions
# docs/DESIGN_PERMISSIONS.md §D.1–D.5


class RolePermissionRowSerializer(serializers.ModelSerializer):
    updated_by_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = RolePermission
        fields = ["role", "permission", "allowed", "updated_by_id", "updated_at"]
        read_only_fields = fields


class RolePermissionUpdateSerializer(serializers.Serializer):
    """`PUT workspaces/{id}/role-permissions/` payload (D.3).

    `expected_version` majburiy (optimistic concurrency). `roles` F-8 bo'yicha
    qat'iy whitelist — noma'lum kalit silent ignore EMAS, 400.
    """

    expected_version = serializers.IntegerField(min_value=0)
    roles = serializers.DictField(required=True)

    def validate_roles(self, roles):
        if not isinstance(roles, dict) or not roles:
            raise serializers.ValidationError("Kamida bitta rol berilishi shart.")
        return roles


class ResetRolePermissionsSerializer(serializers.Serializer):
    """`POST .../role-permissions/reset/` — `null` = barcha rollar (D.4)."""

    role = serializers.ChoiceField(
        choices=AssignableRole.choices, required=False, allow_null=True, default=None
    )


class SpaceMemberSerializer(serializers.ModelSerializer):
    space_id = serializers.UUIDField(read_only=True)
    user = UserSummarySerializer(read_only=True)
    added_by_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = SpaceMember
        fields = [
            "id",
            "space_id",
            "user",
            "access",
            "source",
            "added_by_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AddSpaceMemberSerializer(serializers.Serializer):
    """`POST spaces/{id}/members/` va bulk `add[]` elementi (§D.6).

    `access` berilmasa `contributor` — ya'ni odam bo'lim ichida o'z workspace
    roli bo'yicha ishlaydi, na ko'proq na kamroq.
    """

    user_id = serializers.UUIDField()
    access = serializers.ChoiceField(
        choices=SpaceAccess.choices, required=False, default=SpaceAccess.CONTRIBUTOR
    )


class UpdateSpaceMemberSerializer(serializers.Serializer):
    """`PATCH spaces/{id}/members/{user_id}/` — faqat `access` o'zgaradi."""

    access = serializers.ChoiceField(choices=SpaceAccess.choices)


class BulkSpaceMembersSerializer(serializers.Serializer):
    """`POST spaces/{id}/members/bulk/` — bitta tranzaksiya, qisman muvaffaqiyat yo'q.

    `add` upsert semantikasi bilan ishlaydi (PM panelidagi "saqlash" tugmasi
    bir vaqtda yangi odam qo'shadi va mavjudlarining darajasini o'zgartiradi),
    `remove` esa faqat `user_id` ro'yxati.
    """

    add = AddSpaceMemberSerializer(many=True, required=False, default=list)
    remove = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)

    def validate(self, attrs):
        add_ids = [str(row["user_id"]) for row in attrs.get("add") or []]
        remove_ids = [str(uid) for uid in attrs.get("remove") or []]
        if len(set(add_ids)) != len(add_ids):
            raise serializers.ValidationError({"add": ["Takroriy `user_id` yuborildi."]})
        if len(set(remove_ids)) != len(remove_ids):
            raise serializers.ValidationError({"remove": ["Takroriy `user_id` yuborildi."]})
        overlap = set(add_ids) & set(remove_ids)
        if overlap:
            raise serializers.ValidationError(
                {"remove": [f"Bir foydalanuvchi ham qo'shilib ham olib tashlanmaydi: {', '.join(sorted(overlap))}."]}
            )
        if not add_ids and not remove_ids:
            raise serializers.ValidationError("`add` yoki `remove` dan biri bo'sh bo'lmasligi kerak.")
        return attrs
