"""Django admin — docs/DESIGN_PERMISSIONS.md §G.3.

F-7: `/admin/` ruxsat matritsasini chetlab o'tish yo'li bo'lmasligi kerak.
Shuning uchun `RolePermission` add/change/delete faqat `is_superuser` uchun,
har bir yozish esa `bump_permissions_version()` ni chaqiradi (aks holda kesh
eskirib qoladi va jimgina xavfsizlik teshigi paydo bo'ladi — R3).
"""

from django.contrib import admin

from apps.accounts.admin import NoBulkDeleteMixin
from apps.core.access import bump_permissions_version
from apps.core.enums import SpaceAccess, SpaceMemberSource
from apps.core.permissions import PERMISSION_GROUPS
from apps.workspaces import services
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

admin.site.site_header = "Clickish boshqaruvi"
admin.site.site_title = "Clickish admin"
admin.site.index_title = "Boshqaruv paneli"


class PermissionGroupFilter(admin.SimpleListFilter):
    """`permission` kodining prefiksi bo'yicha filtr (katalog guruhi)."""

    title = "ruxsat guruhi"
    parameter_name = "perm_group"

    def lookups(self, request, model_admin):
        return tuple(PERMISSION_GROUPS.items())

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        return queryset.filter(permission__startswith=f"{value}.")


# ----------------------------------------------------------------- inlines


class WorkspaceMemberInline(admin.TabularInline):
    model = WorkspaceMember
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "role", "invited_by", "joined_at")
    readonly_fields = ("joined_at",)
    verbose_name = "a'zo"
    verbose_name_plural = "a'zolar"


class RolePermissionInline(admin.TabularInline):
    """3 rol × butun katalog (v5: 147 qator) — default yopiq; faqat `allowed` tahrirlanadi."""

    model = RolePermission
    extra = 0
    can_delete = False
    classes = ["collapse"]
    fields = ("role", "permission", "allowed", "updated_by")
    readonly_fields = ("role", "permission", "updated_by")
    verbose_name = "rol ruxsati"
    verbose_name_plural = "rol ruxsatlari"

    def has_add_permission(self, request, obj=None):
        return False

    # F-7: inline `RolePermissionAdmin` ning superuser qulfini MEROS OLMAYDI —
    # Django bu yerda oddiy `workspaces.change_rolepermission` ruxsatini
    # tekshiradi. Ya'ni `is_staff` xodim workspace sahifasi orqali matritsani
    # tahrirlab, o'ziga `space.read_private` yoki `task.delete` bera olardi.
    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return False


class SpaceMemberInline(admin.TabularInline):
    model = SpaceMember
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "access", "source", "added_by")
    verbose_name = "bo'lim a'zosi"
    verbose_name_plural = "bo'lim a'zolari"


# ------------------------------------------------------------- model admins


@admin.register(Workspace)
class WorkspaceAdmin(NoBulkDeleteMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "owner",
        "member_count",
        "permissions_version",
        "created_at",
    )
    list_select_related = ("owner",)
    search_fields = ("name", "slug", "owner__email")
    readonly_fields = (
        "slug",
        "member_count",
        "permissions_version",
        "created_at",
        "updated_at",
    )
    inlines = [WorkspaceMemberInline, RolePermissionInline]
    actions = ["reset_permission_matrix", "ensure_permission_rows"]

    @admin.action(description="Ruxsat matritsasini defaultga qaytarish")
    def reset_permission_matrix(self, request, queryset):
        for workspace in queryset:
            RolePermission.objects.filter(workspace=workspace).delete()
            services.ensure_role_permissions(workspace)
            bump_permissions_version(workspace, actor=request.user)
        self.message_user(request, f"{queryset.count()} ta ish maydoni tiklandi.")

    @admin.action(description="Yetishmayotgan ruxsat qatorlarini yaratish")
    def ensure_permission_rows(self, request, queryset):
        created = sum(services.ensure_role_permissions(w) for w in queryset)
        self.message_user(request, f"{created} ta qator yaratildi.")

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if formset.model is RolePermission and formset.has_changed():
            bump_permissions_version(form.instance, actor=request.user)


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("workspace", "role", "permission", "allowed", "updated_by", "updated_at")
    list_filter = ("role", "allowed", PermissionGroupFilter)
    list_editable = ("allowed",)
    list_select_related = ("workspace", "updated_by")
    search_fields = ("workspace__name", "permission")
    autocomplete_fields = ("workspace",)
    ordering = ("workspace__name", "role", "permission")
    actions = ["grant_selected", "revoke_selected", "reset_to_default"]

    # F-7: matritsani faqat superuser o'zgartira oladi.
    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def _bump(self, workspaces, actor):
        for workspace in workspaces:
            bump_permissions_version(workspace, actor=actor)

    def save_model(self, request, obj, form, change):
        # ModelForm._post_clean already ran `RolePermission.clean()`, which
        # rejects unknown codes and owner-only grants (F-9).
        super().save_model(request, obj, form, change)
        self._bump([obj.workspace], request.user)

    def delete_model(self, request, obj):
        workspace = obj.workspace
        super().delete_model(request, obj)
        self._bump([workspace], request.user)

    def delete_queryset(self, request, queryset):
        workspaces = list({row.workspace for row in queryset.select_related("workspace")})
        super().delete_queryset(request, queryset)
        self._bump(workspaces, request.user)

    @admin.action(description="Tanlanganlarni yoqish")
    def grant_selected(self, request, queryset):
        from apps.core.permissions import PERMISSION_BY_CODE

        blocked = [
            row.permission
            for row in queryset
            if PERMISSION_BY_CODE.get(row.permission)
            and PERMISSION_BY_CODE[row.permission].owner_only
        ]
        if blocked:
            self.message_user(
                request, f"Owner-only kodlar o'tkazib yuborildi: {sorted(set(blocked))}"
            )
        allowed_qs = queryset.exclude(
            permission__in=[
                code for code, p in PERMISSION_BY_CODE.items() if p.owner_only
            ]
        )
        workspaces = list({row.workspace for row in allowed_qs.select_related("workspace")})
        allowed_qs.update(allowed=True, updated_by=request.user)
        self._bump(workspaces, request.user)

    @admin.action(description="Tanlanganlarni o'chirish")
    def revoke_selected(self, request, queryset):
        workspaces = list({row.workspace for row in queryset.select_related("workspace")})
        queryset.update(allowed=False, updated_by=request.user)
        self._bump(workspaces, request.user)

    @admin.action(description="Tanlanganlarni defaultga qaytarish")
    def reset_to_default(self, request, queryset):
        from apps.core.permissions import PERMISSION_BY_CODE

        workspaces = set()
        for row in queryset.select_related("workspace"):
            definition = PERMISSION_BY_CODE.get(row.permission)
            if definition is None:
                continue
            row.allowed = row.role in definition.defaults
            row.updated_by = request.user
            row.save(update_fields=["allowed", "updated_by", "updated_at"])
            workspaces.add(row.workspace)
        self._bump(workspaces, request.user)


@admin.register(WorkspaceMember)
class WorkspaceMemberAdmin(NoBulkDeleteMixin, admin.ModelAdmin):
    list_display = ("workspace", "user", "role", "joined_at")
    list_filter = ("role",)
    list_select_related = ("workspace", "user")
    search_fields = ("workspace__name", "user__email")
    autocomplete_fields = ("workspace", "user")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "workspace",
        "email",
        "role",
        "status",
        "invited_by",
        "sent_count",
        "last_sent_at",
        "expires_at",
        "is_expired_display",
    )
    list_filter = ("status", "role")
    list_select_related = ("workspace", "invited_by")
    search_fields = ("workspace__name", "email")
    readonly_fields = ("token",)
    actions = ["revoke_selected", "extend_expiry_7d"]

    def has_add_permission(self, request):
        return False

    @admin.display(boolean=True, description="muddati o'tgan")
    def is_expired_display(self, obj):
        from django.utils import timezone

        return obj.expires_at < timezone.now()

    @admin.action(description="Tanlangan takliflarni bekor qilish")
    def revoke_selected(self, request, queryset):
        from django.utils import timezone

        queryset.filter(status="pending").update(
            status="revoked", revoked_at=timezone.now()
        )

    @admin.action(description="Muddatni 7 kunga uzaytirish")
    def extend_expiry_7d(self, request, queryset):
        from datetime import timedelta

        from django.utils import timezone

        for invitation in queryset:
            invitation.expires_at = timezone.now() + timedelta(days=7)
            invitation.save(update_fields=["expires_at", "updated_at"])


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "is_private", "archived", "position")
    list_filter = ("is_private", "archived", "workspace")
    list_select_related = ("workspace",)
    search_fields = ("name", "workspace__name")
    inlines = [SpaceMemberInline]
    actions = ["make_private", "make_public", "sync_creator_as_manager"]

    def _set_visibility(self, request, queryset, *, is_private):
        """`queryset.update()` EMAS — servis qatlami orqali.

        Bo'limning `is_private` bayrog'i oddiy ustun emas: uni o'zgartirish
        (a) yopiq bo'limga menejer biriktirishni, (b) `permissions_version`
        ni oshirishni va (c) ko'rinishni yo'qotganlarga `access.revoked`
        yuborishni talab qiladi. To'g'ridan-to'g'ri `UPDATE` uchalasini ham
        o'tkazib yuborardi va mehmon ochiq soket bilan endi yopiq bo'lgan
        bo'limning freymlarini olishda davom etardi (§G.3 / Y-1).
        """
        changed = 0
        for space in queryset.select_related("workspace"):
            if space.is_private == is_private:
                continue
            services.set_space_visibility(space, is_private=is_private, actor=request.user)
            changed += 1
        self.message_user(request, f"{changed} ta bo'lim yangilandi.")

    @admin.action(description="Yopiq qilish")
    def make_private(self, request, queryset):
        self._set_visibility(request, queryset, is_private=True)

    @admin.action(description="Ochiq qilish")
    def make_public(self, request, queryset):
        self._set_visibility(request, queryset, is_private=False)

    @admin.action(description="Yaratuvchini menejer qilib biriktirish")
    def sync_creator_as_manager(self, request, queryset):
        count = 0
        for space in queryset.exclude(created_by__isnull=True):
            services.ensure_space_member(
                space,
                space.created_by,
                access=SpaceAccess.MANAGER,
                source=SpaceMemberSource.AUTO_CREATOR,
                added_by=request.user,
            )
            count += 1
        self.message_user(request, f"{count} ta bo'lim yangilandi.")


@admin.register(SpaceMember)
class SpaceMemberAdmin(admin.ModelAdmin):
    list_display = ("space", "user", "access", "source", "created_at")
    list_filter = ("access", "source")
    list_select_related = ("space", "user")
    search_fields = ("space__name", "user__email")
    autocomplete_fields = ("space", "user")


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("name", "space", "archived", "position")


@admin.register(TaskList)
class TaskListAdmin(admin.ModelAdmin):
    list_display = ("name", "space", "folder", "archived", "task_count", "position")


@admin.register(StatusSet)
class StatusSetAdmin(admin.ModelAdmin):
    list_display = ("name", "space", "list")


@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ("name", "status_set", "type", "order", "is_default")
    list_filter = ("type",)
