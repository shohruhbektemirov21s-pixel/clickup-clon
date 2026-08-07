from django.contrib import admin

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


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "member_count", "created_at")
    search_fields = ("name", "slug")


@admin.register(WorkspaceMember)
class WorkspaceMemberAdmin(admin.ModelAdmin):
    list_display = ("workspace", "user", "role", "joined_at")
    list_filter = ("role",)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("workspace", "email", "role", "status", "expires_at")
    list_filter = ("status", "role")


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "is_private", "archived", "position")


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
