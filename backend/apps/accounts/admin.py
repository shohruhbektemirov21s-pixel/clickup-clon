from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from apps.accounts.models import User


class NoBulkDeleteMixin:
    """AppSec B.2 — admin'dagi ommaviy o'chirishni butunlay yopadi.

    Sabab: `TaskAdmin.get_queryset` / `CommentAdmin.get_queryset` `all_objects`
    qaytaradi, ya'ni changelist'da soft-delete qilingan yozuvlar ham ko'rinadi.
    `delete_selected` ularni **qaytarib bo'lmaydigan** tarzda, bitta klik bilan
    bazadan uchirib yuborardi (signal ham, tasdiq ham, audit izi ham yo'q).

    - `get_actions()` -> `delete_selected` hech kimga (superuser'ga ham) ko'rinmaydi;
      bitta obyektni o'chirish sahifasi esa joyida qoladi.
    - `has_delete_permission()` -> faqat `is_superuser`; Django gruppa ruxsati
      (`delete_*`) berilgan oddiy staff endi o'chira olmaydi.
    """

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def has_delete_permission(self, request, obj=None):
        return bool(getattr(request.user, "is_superuser", False))


class UserCreateForm(UserCreationForm):
    """Email is the username field, so drop the username-based validation."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "full_name")


class UserEditForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(NoBulkDeleteMixin, BaseUserAdmin):
    """django.contrib.auth's UserAdmin, not a bare ModelAdmin.

    A bare ModelAdmin renders `password` as a plain text input and writes it
    to the column verbatim, storing credentials unhashed. BaseUserAdmin uses
    the hashed ReadOnlyPasswordHashField plus the set-password form instead.
    """

    add_form = UserCreateForm
    form = UserEditForm
    change_password_form = AdminPasswordChangeForm

    list_display = ("email", "full_name", "is_active", "is_staff", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")
    ordering = ("email",)
    readonly_fields = ("date_joined", "last_login", "last_seen_at", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        # `profession` — kasb yorlig'i, "Ruxsatlar" bo'limida EMAS: u hech qanday
        # vakolat bermaydi.
        (
            "Profil",
            {"fields": ("full_name", "profession", "avatar", "avatar_color", "timezone")},
        ),
        (
            "Ruxsatlar",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (
            "Sanalar",
            {"fields": ("date_joined", "last_login", "last_seen_at", "created_at", "updated_at")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "usable_password", "password1", "password2"),
            },
        ),
    )


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """AppSec B.2 — admin harakatlari jurnali: ko'rinadigan, lekin o'zgarmas.

    Django har bir admin qo'shish/o'zgartirish/o'chirishini `LogEntry` ga
    yozadi, ammo uni hech qayerda ko'rsatmaydi. Ro'yxatdan o'tkazmasak — audit
    izi bor, lekin unga qarash mumkin emas; ro'yxatdan yozish huquqi bilan
    o'tkazsak — buzg'unchi o'z izini o'chirib ketadi. Shuning uchun barcha
    maydon `readonly`, add/change/delete esa hech kimga (superuser'ga ham) yopiq.

    `has_view_permission` ataylab override qilinmagan: jurnalni ko'rish uchun
    Django'ning odatdagi `admin.view_logentry` ruxsati talab qilinaveradi.
    """

    list_display = (
        "action_time",
        "user",
        "content_type",
        "object_repr",
        "action_flag",
        "change_message",
    )
    list_filter = ("action_flag", "content_type", "action_time")
    list_select_related = ("user", "content_type")
    search_fields = ("object_repr", "change_message", "user__email")
    date_hierarchy = "action_time"
    ordering = ("-action_time",)
    readonly_fields = (
        "action_time",
        "user",
        "content_type",
        "object_id",
        "object_repr",
        "action_flag",
        "change_message",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
