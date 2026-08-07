"""JWT authentication for WebSocket connections.

Browsers cannot set headers on a WebSocket handshake, so the access token is
passed as a query param: ws://host/ws/list/<id>/?token=<access>
"""

from urllib.parse import parse_qs

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _user_from_token(raw_token):
    User = get_user_model()
    try:
        token = AccessToken(raw_token)
    except (InvalidToken, TokenError):
        return AnonymousUser()
    try:
        return User.objects.get(pk=token["user_id"], is_active=True)
    except User.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = (query.get("token") or [None])[0]
        scope = dict(scope)
        scope["user"] = await _user_from_token(token) if token else AnonymousUser()
        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))
