from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from apps.accounts.models import User


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
class UserAdmin(BaseUserAdmin):
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
