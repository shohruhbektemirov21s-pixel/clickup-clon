from django.contrib import admin

from apps.tasks.models import Tag, Task


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
