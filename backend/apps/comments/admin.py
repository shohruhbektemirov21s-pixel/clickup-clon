from django.contrib import admin

from apps.comments.models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("task", "author", "parent", "is_edited", "deleted_at", "created_at")

    def get_queryset(self, request):
        return Comment.all_objects.all()
