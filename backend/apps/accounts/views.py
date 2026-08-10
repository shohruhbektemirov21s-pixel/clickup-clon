import io

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    RegisterSerializer,
    UserSerializer,
    token_pair_for,
)
from apps.accounts.throttling import LoginEmailThrottle
from apps.core.exceptions import ApiError

MAX_AVATAR_BYTES = 2 * 1024 * 1024
AVATAR_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = token_pair_for(user)
        body = {**tokens, "user": UserSerializer(user, context={"request": request}).data}
        # R21 / §D.8 — `workspace_id` faqat workspace haqiqatan paydo bo'lganda
        # qaytariladi (invite qabul qilindi yoki `workspace_name` bootstrap).
        workspace_id = getattr(serializer, "workspace_id", None)
        if workspace_id:
            body["workspace_id"] = workspace_id
        return Response(body, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    # Two buckets: per source address (auth) and per account (auth_burst).
    throttle_classes = [ScopedRateThrottle, LoginEmailThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = token_pair_for(user)
        return Response(
            {**tokens, "user": UserSerializer(user, context={"request": request}).data}
        )


class DemoLoginView(APIView):
    """`POST auth/demo/` — parolsiz demo hisobga kirish.

    XAVFSIZLIK:
      * Parol hech qachon klientga ketmaydi — tugma faqat shu endpointni
        chaqiradi, demo parol backend'da qoladi (frontend bundle'ida yo'q).
      * `DEMO_MODE=False`, hisob yo'q yoki nofaol → `404` (`403` EMAS, endpoint
        borligini oshkor qilmaydi).
      * Demo hisob `is_staff`/`is_superuser` bo'lsa → `404`. Shu tufayli bu
        tugma orqali Django `/admin/` ga hech qachon kirib bo'lmaydi.
      * `demo` throttle scope IP bo'yicha cheklaydi.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "demo"

    def post(self, request):
        from apps.accounts.models import User
        from apps.workspaces.models import WorkspaceMember

        if not getattr(settings, "DEMO_MODE", False):
            raise NotFound()

        email = (getattr(settings, "DEMO_USER_EMAIL", "") or "").strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
        if user is None or user.is_staff or user.is_superuser:
            # Eskalatsiya bloki: staff hisob demo tugmasi orqali berilmaydi.
            raise NotFound()
        if not user.is_readonly:
            # Demo tugmasi faqat yozish huquqisiz hisobga kirita oladi. Agar
            # DEMO_USER_EMAIL oddiy hisobga qaratilgan bo'lsa, endpoint umuman
            # javob bermaydi — noto'g'ri sozlama ochiq eshikka aylanmaydi.
            raise NotFound()

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        membership = (
            WorkspaceMember.objects.filter(user=user).order_by("joined_at").first()
        )
        body = {
            **token_pair_for(user),
            "user": UserSerializer(user, context={"request": request}).data,
        }
        if membership is not None:
            body["workspace_id"] = str(membership.workspace_id)
        return Response(body)


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)  # rotates + blacklists (settings)
        except TokenError as exc:
            raise InvalidToken(str(exc)) from exc  # -> 401 token_not_valid
        return Response(serializer.validated_data)


class LogoutView(APIView):
    def post(self, request):
        raw = request.data.get("refresh")
        if not raw:
            raise ApiError(
                "Request payload is invalid.",
                details={"refresh": ["This field is required."]},
                code="validation_error",
            )
        try:
            RefreshToken(raw).blacklist()
        except TokenError:
            raise ApiError(
                "Token is invalid or expired.",
                code="token_not_valid",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_change"

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        # Blacklist every outstanding refresh token, then hand back a fresh pair.
        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)
        return Response(token_pair_for(user))


class RealtimeTicketView(APIView):
    """`POST realtime/ticket/` — bir martalik WebSocket handshake chiptasi (§15.1).

    Brauzer WS handshake'ida `Authorization` sarlavhasini qo'ya olmaydi, shuning
    uchun ilgari access token to'g'ridan-to'g'ri URL'da (`?token=`) ketardi va
    proxy/APM access log'larida qolardi. Bu endpoint uning o'rniga hech qanday
    da'vo olib yurmaydigan, 30 soniya yashaydigan va **bir marta** ishlatiladigan
    opaque chipta beradi: log'dan olingan URL bilan endi soket ochib bo'lmaydi.

    Autentifikatsiya talab qilinadi (chipta faqat so'rovchining o'ziga tegishli),
    `realtime_ticket` throttle scope'i esa chipta zavodiga aylanishiga yo'l
    qo'ymaydi.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "realtime_ticket"

    def post(self, request):
        from apps.realtime.tickets import TICKET_TTL_SECONDS, issue_ticket

        return Response(
            {"ticket": issue_ticket(request.user), "expires_in": TICKET_TTL_SECONDS}
        )


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)

    def patch(self, request):
        serializer = UserSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MeAvatarView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    # Decoding + resizing an uploaded image is the most expensive thing an
    # authenticated user can trigger, so it gets its own budget.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "avatar"

    def post(self, request):
        upload = request.FILES.get("avatar")
        if upload is None:
            raise ApiError(
                "Request payload is invalid.",
                details={"avatar": ["This field is required."]},
                code="validation_error",
            )
        if upload.size > MAX_AVATAR_BYTES:
            raise ApiError(
                "Request payload is invalid.",
                details={"avatar": ["Avatar must be at most 2 MB."]},
                code="validation_error",
            )
        try:
            image = Image.open(upload)
            image_format = image.format
            image.load()
        except Exception:
            image_format = None
        if image_format not in AVATAR_FORMATS:
            raise ApiError(
                "Request payload is invalid.",
                details={"avatar": ["Avatar must be a jpeg, png or webp image."]},
                code="validation_error",
            )

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if image_format in ("PNG", "WEBP") else "RGB")
        image = image.resize((256, 256))
        buffer = io.BytesIO()
        image.save(buffer, format=image_format)
        buffer.seek(0)

        from django.core.files.base import ContentFile

        ext = AVATAR_FORMATS[image_format]
        request.user.avatar.save(
            f"{request.user.id}.{ext}", ContentFile(buffer.read()), save=True
        )
        return Response(UserSerializer(request.user, context={"request": request}).data)
