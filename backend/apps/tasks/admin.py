from django.contrib import admin

from apps.accounts.admin import NoBulkDeleteMixin
from apps.tasks.models import Tag, Task, TaskActivity


@admin.register(Task)
class TaskAdmin(NoBulkDeleteMixin, admin.ModelAdmin):
    list_display = ("title", "list", "status", "priority", "position", "deleted_at")
    list_filter = ("priority", "archived")
    search_fields = ("title",)

    def get_queryset(self, request):
        return Task.all_objects.all()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "usage_count")


@admin.register(TaskActivity)
class TaskActivityAdmin(admin.ModelAdmin):
    """AppSec B.2 — audit izi: faqat o'qish uchun.

    Vazifa tarixi kim nimani o'zgartirganini isbotlaydi; admin orqali qo'lda
    yozish yoki tozalash imkoniyati bu isbotni qiymatsiz qiladi.
    """

    list_display = ("task", "verb", "actor", "from_value", "to_value", "created_at")
    list_filter = ("verb",)
    readonly_fields = ("task", "actor", "verb", "from_value", "to_value", "metadata")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
