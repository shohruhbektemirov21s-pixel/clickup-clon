"""Workspace hierarchy models.

Per API_CONTRACT.md ruling R1, ALL hierarchy models (Workspace, WorkspaceMember,
Invitation, Space, Folder, TaskList, StatusSet, Status) live in apps.workspaces.
The Django model is TaskList (table "lists"); every API path/field says "list".
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from apps.core.enums import (
    AssignableRole,
    InvitationRole,
    InvitationStatus,
    SpaceAccess,
    SpaceMemberSource,
    StatusType,
    WorkspaceRole,
)
from apps.core.models import HEX_COLOR, PositionedModel, TimeStampedModel, UUIDModel


class Workspace(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, db_index=True, allow_unicode=False)
    description = models.TextField(blank=True, default="")
    color = models.CharField(max_length=7, default="#7B68EE", validators=[HEX_COLOR])
    avatar = models.ImageField(
        upload_to="workspaces/%Y/%m/", max_length=500, null=True, blank=True
    )

    owner = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="owned_workspaces"
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_workspaces",
    )

    member_count = models.PositiveIntegerField(default=0)  # denormalised

    # docs/DESIGN_PERMISSIONS.md AD-4/§B.2 — ruxsat keshi kalitining bir qismi.
    # Matritsa har o'zgarganda `bump_permissions_version()` uni F()+1 qiladi.
    permissions_version = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        db_table = "workspaces"
        ordering = ["name"]
        indexes = [models.Index(fields=["owner"], name="idx_ws_owner")]

    def __str__(self):
        return self.name


class WorkspaceMember(UUIDModel, TimeStampedModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="workspace_memberships"
    )
    role = models.CharField(
        max_length=10,
        choices=WorkspaceRole.choices,
        default=WorkspaceRole.MEMBER,
        db_index=True,
    )
    invited_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invited_members",
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workspace_members"
        ordering = ["role", "user__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"], name="uniq_member_per_workspace"
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "role"], name="idx_member_ws_role"),
            models.Index(fields=["user", "workspace"], name="idx_member_user_ws"),
        ]

    def __str__(self):
        return f"{self.user} in {self.workspace} ({self.role})"


class RolePermission(UUIDModel, TimeStampedModel):
    """Bir workspace uchun rol → ruxsat granti (docs/DESIGN_PERMISSIONS.md §B.3).

    AD-1: `permission` — katalog kodi, FK EMAS (katalog kodda yashaydi).
    AD-2: qator yo'q bo'lsa `DEFAULT_MATRIX` ga qaytadi, shuning uchun yangi
    katalog kodlari backfillsiz ishlaydi.
    AD-3: `owner` bu jadvalga hech qachon tushmaydi — DB constraint bilan.
    """

    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="role_permissions"
    )
    role = models.CharField(max_length=10, choices=AssignableRole.choices, db_index=True)
    permission = models.CharField(max_length=64, db_index=True)  # katalog kodi
    allowed = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "workspace_role_permissions"
        ordering = ["role", "permission"]
        verbose_name = "rol ruxsati"
        verbose_name_plural = "rol ruxsatlari"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "role", "permission"],
                name="uniq_role_permission_per_workspace",
            ),
            models.CheckConstraint(
                condition=~models.Q(role="owner"), name="role_permission_never_owner"
            ),
        ]
        indexes = [models.Index(fields=["workspace", "role"], name="idx_roleperm_ws_role")]

    def __str__(self):
        return f"{self.role}:{self.permission}={'✔' if self.allowed else '✕'}"

    def clean(self):
        from apps.core.permissions import PERMISSION_BY_CODE

        definition = PERMISSION_BY_CODE.get(self.permission)
        if definition is None:
            raise ValidationError({"permission": "Noma'lum ruxsat kodi."})
        if definition.owner_only and self.allowed:
            raise ValidationError({"permission": "Bu ruxsat faqat owner uchun."})


class Invitation(UUIDModel, TimeStampedModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField(max_length=254, db_index=True)
    role = models.CharField(
        max_length=10, choices=InvitationRole.choices, default=InvitationRole.MEMBER
    )
    token = models.CharField(max_length=64, unique=True, db_index=True, editable=False)
    status = models.CharField(
        max_length=10,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
    )

    invited_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )
    accepted_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_invitations",
    )

    expires_at = models.DateTimeField(db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    sent_count = models.PositiveSmallIntegerField(default=1)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "invitations"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                "workspace",
                Lower("email"),
                condition=models.Q(status="pending"),
                name="uniq_pending_invite_per_email_per_ws",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status"], name="idx_invite_ws_status"),
            models.Index(Lower("email"), name="idx_invite_email_ci"),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").lower()
        super().save(*args, **kwargs)


class Space(UUIDModel, TimeStampedModel, PositionedModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="spaces")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    color = models.CharField(max_length=7, default="#7B68EE", validators=[HEX_COLOR])
    icon = models.CharField(max_length=40, blank=True, default="")  # lucide icon name
    is_private = models.BooleanField(default=False)
    archived = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_spaces",
    )

    class Meta:
        db_table = "spaces"
        ordering = ["position", "name"]
        constraints = [
            models.UniqueConstraint(
                "workspace", Lower("name"), name="uniq_space_name_per_workspace"
            ),
            models.UniqueConstraint(
                fields=["workspace", "position"], name="uniq_space_position_per_workspace"
            ),
        ]
        indexes = [
            models.Index(
                fields=["workspace", "archived", "position"], name="idx_space_ws_arch_pos"
            ),
        ]

    def __str__(self):
        return self.name


class SpaceMember(UUIDModel, TimeStampedModel):
    """Bo'limga biriktirilgan foydalanuvchi (docs/DESIGN_PERMISSIONS.md §B.4).

    AD-6: PM/loyiha biriktiruvi shu jadval orqali (DATA_MODEL D8 bekor).

    Invariant: `user` shu space'ning workspace'ida `WorkspaceMember` bo'lishi
    shart — servis qatlamida tekshiriladi; `_remove_member()` workspace'dan
    chiqarishda space qatorlarini ham o'chiradi.
    """

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="space_members")
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="space_memberships"
    )
    access = models.CharField(
        max_length=12,
        choices=SpaceAccess.choices,
        default=SpaceAccess.CONTRIBUTOR,
        db_index=True,
    )
    source = models.CharField(
        max_length=14, choices=SpaceMemberSource.choices, default=SpaceMemberSource.MANUAL
    )
    added_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "space_members"
        ordering = ["access", "user__email"]
        verbose_name = "bo'lim a'zosi"
        verbose_name_plural = "bo'lim a'zolari"
        constraints = [
            models.UniqueConstraint(fields=["space", "user"], name="uniq_space_member")
        ]
        indexes = [
            models.Index(fields=["user", "space"], name="idx_spacemember_user_space"),
            models.Index(fields=["space", "access"], name="idx_spacemember_space_access"),
        ]

    def __str__(self):
        return f"{self.user} in {self.space} ({self.access})"


class Folder(UUIDModel, TimeStampedModel, PositionedModel):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="folders")
    name = models.CharField(max_length=120)
    color = models.CharField(max_length=7, default="#7B68EE", validators=[HEX_COLOR])
    archived = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_folders",
    )

    class Meta:
        db_table = "folders"
        ordering = ["position", "name"]
        constraints = [
            models.UniqueConstraint("space", Lower("name"), name="uniq_folder_name_per_space"),
            models.UniqueConstraint(
                fields=["space", "position"], name="uniq_folder_position_per_space"
            ),
        ]
        indexes = [
            models.Index(
                fields=["space", "archived", "position"], name="idx_folder_space_arch_pos"
            ),
        ]

    def __str__(self):
        return self.name


class TaskList(UUIDModel, TimeStampedModel, PositionedModel):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="lists")
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, null=True, blank=True, related_name="lists"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    color = models.CharField(max_length=7, default="#7B68EE", validators=[HEX_COLOR])
    archived = models.BooleanField(default=False, db_index=True)

    default_view = models.CharField(
        max_length=8, default="list", choices=[("list", "List"), ("board", "Board")]
    )
    task_count = models.PositiveIntegerField(default=0)  # denormalised, live tasks
    open_task_count = models.PositiveIntegerField(default=0)  # denormalised, not closed

    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_lists",
    )

    class Meta:
        db_table = "lists"
        verbose_name = "list"
        verbose_name_plural = "lists"
        ordering = ["position", "name"]
        constraints = [
            models.UniqueConstraint(
                "folder",
                Lower("name"),
                condition=models.Q(folder__isnull=False),
                name="uniq_list_name_per_folder",
            ),
            models.UniqueConstraint(
                "space",
                Lower("name"),
                condition=models.Q(folder__isnull=True),
                name="uniq_list_name_per_space_root",
            ),
            models.UniqueConstraint(
                fields=["folder", "position"],
                condition=models.Q(folder__isnull=False),
                name="uniq_list_position_per_folder",
            ),
            models.UniqueConstraint(
                fields=["space", "position"],
                condition=models.Q(folder__isnull=True),
                name="uniq_list_position_per_space_root",
            ),
        ]
        indexes = [
            models.Index(fields=["space", "folder", "position"], name="idx_list_space_folder_pos"),
            models.Index(fields=["space", "archived"], name="idx_list_space_arch"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.folder_id and self.folder.space_id != self.space_id:
            raise ValidationError(
                {"folder_id": "Folder must belong to the same space as the list."}
            )

    @property
    def effective_status_set(self):
        return getattr(self, "status_set", None) or self.space.status_set


class StatusSet(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=80, default="Default")

    space = models.OneToOneField(
        Space, on_delete=models.CASCADE, null=True, blank=True, related_name="status_set"
    )
    list = models.OneToOneField(
        TaskList, on_delete=models.CASCADE, null=True, blank=True, related_name="status_set"
    )

    class Meta:
        db_table = "status_sets"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(space__isnull=False, list__isnull=True)
                | models.Q(space__isnull=True, list__isnull=False),
                name="statusset_exactly_one_owner",
            ),
        ]

    def __str__(self):
        return self.name


class Status(UUIDModel, TimeStampedModel):
    status_set = models.ForeignKey(StatusSet, on_delete=models.CASCADE, related_name="statuses")
    name = models.CharField(max_length=60)
    color = models.CharField(max_length=7, default="#87909E", validators=[HEX_COLOR])
    type = models.CharField(
        max_length=8, choices=StatusType.choices, default=StatusType.OPEN, db_index=True
    )
    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "statuses"
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint("status_set", Lower("name"), name="uniq_status_name_per_set"),
            # NOTE: DATA_MODEL.md specifies deferrable=DEFERRED here, which is
            # PostgreSQL-only and raises system-check warnings on SQLite. The
            # status-set rewrite service instead uses a two-pass write through
            # a high temporary offset, which is correct on both backends.
            models.UniqueConstraint(
                fields=["status_set", "order"], name="uniq_status_order_per_set"
            ),
            models.UniqueConstraint(
                fields=["status_set"],
                condition=models.Q(is_default=True),
                name="uniq_default_status_per_set",
            ),
        ]
        indexes = [
            models.Index(fields=["status_set", "order"], name="idx_status_set_order"),
        ]

    def __str__(self):
        return self.name
