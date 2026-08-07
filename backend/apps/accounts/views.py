import io

from django.db import transaction
from PIL import Image
from rest_framework import status
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
from apps.core.exceptions import ApiError

MAX_AVATAR_BYTES = 2 * 1024 * 1024
AVATAR_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = token_pair_for(user)
        return Response(
            {**tokens, "user": UserSerializer(user, context={"request": request}).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = token_pair_for(user)
        return Response(
            {**tokens, "user": UserSerializer(user, context={"request": request}).data}
        )


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
