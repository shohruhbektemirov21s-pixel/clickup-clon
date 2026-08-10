import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Build the HTTP application first: importing anything that touches models
# before this point would hit an app registry that is not ready yet.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import OriginValidator  # noqa: E402
from django.conf import settings  # noqa: E402

from apps.realtime.middleware import JWTAuthMiddleware  # noqa: E402
from apps.realtime.routing import websocket_urlpatterns  # noqa: E402


class AllowedHostsOriginValidator(OriginValidator):
    """ALLOWED_HOSTS-based origin check for the WebSocket handshake.

    Blocks cross-site WebSocket hijacking: a page on evil.example cannot open a
    socket against us, because browsers always send an Origin header on the
    handshake and it cannot be forged from script.

    Handshakes with *no* Origin header are allowed through. Only browsers are
    forced to send one; any other client can put whatever it likes there, so
    rejecting header-less handshakes would block legitimate server-to-server and
    native clients without denying an attacker anything. Authentication is still
    enforced by JWTAuthMiddleware and the consumers' membership checks.
    """

    def __init__(self, application, extra_origins=()):
        origins = [*settings.ALLOWED_HOSTS, *extra_origins]
        if not origins and settings.DEBUG:
            origins = ["localhost", "127.0.0.1", "[::1]"]
        super().__init__(application, origins)

    async def __call__(self, scope, receive, send):
        has_origin = any(name == b"origin" for name, _ in scope.get("headers", []))
        if not has_origin:
            return await self.application(scope, receive, send)
        return await super().__call__(scope, receive, send)


# The SPA is normally served from a different host than the API, so its origin
# has to be listed explicitly via WS_ALLOWED_ORIGINS when that is the case.
websocket_application = AllowedHostsOriginValidator(
    # No AuthMiddlewareStack: WebSocket auth is the JWT in the query string, and
    # keeping session/cookie auth out of the stack means a cookie alone can never
    # authenticate a socket.
    JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
    extra_origins=settings.WS_ALLOWED_ORIGINS,
)

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": websocket_application,
    }
)
