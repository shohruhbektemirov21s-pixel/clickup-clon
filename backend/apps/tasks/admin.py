from django.contrib import admin

from apps.tasks.models import Tag, Task, TaskActivity


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
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
    list_display = ("task", "verb", "actor", "from_value", "to_value", "created_at")
    list_filter = ("verb",)
    readonly_fields = ("task", "actor", "verb", "from_value", "to_value", "metadata")
