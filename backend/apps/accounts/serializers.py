import re
import zoneinfo

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone as dj_timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.core.enums import InvitationRole, InvitationStatus, Profession, WorkspaceRole
from apps.core.exceptions import Conflict
from apps.core.models import HEX_COLOR

INVITE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Django parol validatorlarining kodlari → o'zbekcha xabar. UI matnlari
# o'zbekcha bo'lishi shart, Django esa inglizcha xabar beradi.
PASSWORD_ERROR_UZ = {
    "password_too_short": "Parol juda qisqa — kamida 8 ta belgi kiriting.",
    "password_too_common": "Bu parol juda oddiy, boshqasini tanlang.",
    "password_entirely_numeric": "Parol faqat raqamlardan iborat bo'lmasin.",
    "password_too_similar": "Parol shaxsiy ma'lumotlaringizga juda o'xshash.",
}


def validate_password_uz(password, user):
    """Django validatorlari, lekin xatolar `password` maydoniga o'zbekcha tushadi."""
    try:
        password_validation.validate_password(password, user=user)
    except DjangoValidationError as exc:
        messages = [
            PASSWORD_ERROR_UZ.get(getattr(error, "code", ""), message)
            for error, message in zip(exc.error_list, exc.messages, strict=False)
        ]
        raise serializers.ValidationError({"password": messages or list(exc.messages)})


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
        # `profession` — profil yorlig'i, ruxsatga ta'sir qilmaydi (§1).
        fields = ["id", "email", "full_name", "avatar", "avatar_color", "profession"]
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
            # Yoziladigan profil maydoni — PATCH /me/ orqali o'zgartiriladi.
            # Ruxsat tizimiga hech qanday aloqasi yo'q.
            "profession",
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
    """`POST auth/register/` — ixtiyoriy `invite_token` bilan (DESIGN_PERMISSIONS §D.8).

    XAVFSIZLIK (MUST-1/MUST-2):
      * Yangi a'zoning workspace roli **faqat** `Invitation.role` dan olinadi.
        Mijozning `role` maydoni serializerda umuman e'lon qilinmagan → DRF uni
        jimgina tashlab yuboradi va u hech qayerda ishlatilmaydi.
      * Mijozning `email` maydoni faqat taklif emailiga tengligini tekshirish
        uchun kerak; a'zolik `Invitation.email` bo'yicha quriladi.
      * `profession` — profil yorlig'i; ruxsatga umuman ta'sir qilmaydi.
    """

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    workspace_name = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )
    profession = serializers.ChoiceField(
        choices=Profession.choices, required=False, allow_blank=True, default=""
    )
    invite_token = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default="", trim_whitespace=True
    )

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Bu email bilan foydalanuvchi allaqachon mavjud.")
        return value

    def validate_invite_token(self, value):
        value = (value or "").strip()
        if value and not INVITE_TOKEN_RE.match(value):
            # Format buzilgan token = mavjud bo'lmagan token (§D.8 qoida 2 bilan
            # bir xil natija beradi, lekin 404 `validate()` da beriladi).
            raise serializers.ValidationError("Taklif havolasi yaroqsiz.")
        return value

    def validate(self, attrs):
        user = User(email=attrs["email"], full_name=attrs.get("full_name", ""))
        validate_password_uz(attrs["password"], user)

        token = attrs.get("invite_token") or ""
        self._invitation = None
        if not token:
            return attrs

        # 1. invite_token + workspace_name birga kelmaydi.
        if (attrs.get("workspace_name") or "").strip():
            raise serializers.ValidationError(
                {
                    "workspace_name": [
                        "Taklif bo'yicha qo'shilayotganda yangi ish maydoni yaratilmaydi."
                    ]
                }
            )

        # 6. full_name majburiy (min 2 belgi).
        if len((attrs.get("full_name") or "").strip()) < 2:
            raise serializers.ValidationError(
                {"full_name": ["To'liq ismni kiriting (kamida 2 ta belgi)."]}
            )

        invitation = self._lookup_invitation(token)

        # 3. Email taklif emailiga case-insensitive teng bo'lishi shart.
        if attrs["email"].lower() != invitation.email.lower():
            raise serializers.ValidationError(
                {"email": ["Bu email taklif qilingan manzilga mos kelmaydi."]}
            )

        self._invitation = invitation
        return attrs

    @staticmethod
    def _lookup_invitation(token):
        """2. Noma'lum / muddati o'tgan token → 404, terminal holat → 409.

        Ataylab 403 EMAS: aks holda javob token mavjudligini oshkor qilardi (§F-6).
        Terminal holat (`accepted`/`revoked`) uchun 409 — bu `invitations/accept/`
        dagi `_resolve_invitation_for_token()` bilan bir xil semantika va
        vazifadagi test ro'yxati ("bekor qilingan token → 409") talabi.
        """
        from apps.workspaces.models import Invitation

        invitation = (
            Invitation.objects.select_related("workspace").filter(token=token).first()
        )
        if invitation is None:
            raise NotFound("Taklif topilmadi yoki muddati tugagan.")
        if invitation.status in (InvitationStatus.ACCEPTED, InvitationStatus.REVOKED):
            raise Conflict("Bu taklif allaqachon ishlatilgan yoki bekor qilingan.")
        if (
            invitation.status != InvitationStatus.PENDING
            or invitation.expires_at <= dj_timezone.now()
        ):
            raise NotFound("Taklif topilmadi yoki muddati tugagan.")
        # Ikkilamchi mudofaa: `InvitationRole` da `owner` yo'q, shuning uchun
        # taklif orqali hech qachon owner tug'ilmasligi kerak. Ma'lumot buzilgan
        # bo'lsa ham eskalatsiya bo'lmasin.
        assert WorkspaceRole.OWNER not in InvitationRole.values
        if invitation.role not in InvitationRole.values:
            raise NotFound("Taklif topilmadi yoki muddati tugagan.")
        return invitation

    def create(self, validated):
        invitation = getattr(self, "_invitation", None)
        if invitation is not None:
            return self._create_from_invitation(validated, invitation)

        user = User.objects.create_user(
            email=validated["email"],
            password=validated["password"],
            full_name=validated.get("full_name", ""),
            profession=validated.get("profession", ""),
        )
        workspace_name = (validated.get("workspace_name") or "").strip()
        if workspace_name:
            from apps.workspaces.services import bootstrap_workspace

            workspace = bootstrap_workspace(user, name=workspace_name)
            self.workspace_id = str(workspace.id)
        return user

    def _create_from_invitation(self, validated, invitation):
        """4./5. Bitta tranzaksiya + status-shartli UPDATE (race'ga qarshi)."""
        from apps.workspaces.models import Invitation, WorkspaceMember
        from apps.workspaces.services import refresh_member_count

        with transaction.atomic():
            user = User.objects.create_user(
                # A'zolik taklif emaili bo'yicha quriladi (validate() CI tenglikni
                # allaqachon kafolatlagan).
                email=invitation.email.lower(),
                password=validated["password"],
                full_name=validated["full_name"].strip(),
                profession=validated.get("profession", ""),
            )

            # Lock (PostgreSQL). SQLite'da `select_for_update` no-op — shuning
            # uchun quyidagi shartli UPDATE yagona haqiqiy himoya.
            Invitation.objects.select_for_update().filter(pk=invitation.pk).first()
            claimed = Invitation.objects.filter(
                pk=invitation.pk, status=InvitationStatus.PENDING
            ).update(
                status=InvitationStatus.ACCEPTED,
                accepted_at=dj_timezone.now(),
                accepted_by=user,
                updated_at=dj_timezone.now(),
            )
            if not claimed:
                # Boshqa so'rov bizdan oldin ulgurdi → butun tranzaksiya bekor
                # bo'ladi, foydalanuvchi ham yaratilmaydi.
                raise Conflict("Bu taklif allaqachon ishlatilgan yoki bekor qilingan.")

            WorkspaceMember.objects.create(
                workspace_id=invitation.workspace_id,
                user=user,
                # ROL FAQAT TAKLIFDAN. Mijoz kiritmasi bu yerga yetib kelmaydi.
                role=invitation.role,
                invited_by=invitation.invited_by,
            )
            refresh_member_count(invitation.workspace)

        self.workspace_id = str(invitation.workspace_id)
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
