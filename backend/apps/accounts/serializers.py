import zoneinfo

from django.contrib.auth import password_validation
from django.utils import timezone as dj_timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.core.models import HEX_COLOR


def token_pair_for(user):
    """Issue an access/refresh pair carrying the contract's claims."""
    refresh = RefreshToken.for_user(user)
    refresh["email"] = user.email
    access = refresh.access_token
    access["email"] = user.email
    return {"access": str(access), "refresh": str(refresh)}


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "avatar", "avatar_color"]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "avatar",
            "avatar_color",
            "timezone",
            "date_joined",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "email",
            "avatar",
            "date_joined",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"avatar_color": {"validators": [HEX_COLOR]}}

    def validate_timezone(self, value):
        if value not in zoneinfo.available_timezones():
            raise serializers.ValidationError("Not a valid IANA timezone name.")
        return value


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    workspace_name = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        user = User(email=attrs["email"], full_name=attrs.get("full_name", ""))
        password_validation.validate_password(attrs["password"], user=user)
        return attrs

    def create(self, validated):
        user = User.objects.create_user(
            email=validated["email"],
            password=validated["password"],
            full_name=validated.get("full_name", ""),
        )
        workspace_name = (validated.get("workspace_name") or "").strip()
        if workspace_name:
            from apps.workspaces.services import bootstrap_workspace

            bootstrap_workspace(user, name=workspace_name)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        user = User.objects.filter(email__iexact=attrs["email"].lower()).first()
        if user is None or not user.check_password(attrs["password"]) or not user.is_active:
            raise AuthenticationFailed("Invalid email or password.")
        user.last_login = dj_timezone.now()
        user.save(update_fields=["last_login"])
        attrs["user"] = user
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["user"].check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, user=self.context["user"])
        return value
