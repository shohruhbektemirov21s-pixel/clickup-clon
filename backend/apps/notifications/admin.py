from django.contrib import admin

from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("kind", "user", "workspace", "title", "read_at", "created_at")
    list_filter = ("kind", "read_at")
    search_fields = ("title", "body", "user__email")
    autocomplete_fields = ()
    raw_id_fields = ("user", "workspace", "actor")
    readonly_fields = ("created_at", "updated_at")
