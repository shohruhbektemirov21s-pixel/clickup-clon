"""WebSocket handshake autentifikatsiyasi (chipta yoki JWT).

Brauzer WebSocket handshake'ida sarlavha qo'ya olmaydi, shuning uchun hisob
ma'lumoti so'rov satrida keladi. Ikki shakl qabul qilinadi:

  ``?ticket=<opaque>``  — **AFZAL** (AppSec O-3). Bir martalik, 30 soniya
      yashaydigan chipta; `POST /api/v1/realtime/ticket/` beradi. Proxy/APM
      log'ida qolgan URL qayta ishlatib bo'lmaydigan qiymatni ko'rsatadi.

  ``?token=<access>``   — **DEPRECATED**, faqat orqaga moslik uchun. To'liq
      access token URL'da ketadi, ya'ni uni ko'rgan har bir vosita (access log,
      tracing, brauzer tarixi) butun REST API'ga yaroqli hisob ma'lumotini
      yozib oladi. Yangi klientlar chiptadan foydalanishi shart; bu yo'l
      keyingi shartnoma versiyasida olib tashlanadi.

Ikkalasi ham berilsa chipta ustun turadi va token umuman ko'rilmaydi.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from apps.realtime.tickets import consume_ticket


def _active_user(user_id):
    """`user_id` bo'yicha faol foydalanuvchi yoki `AnonymousUser`.

    `pk` UUID bo'lgani uchun buzuq qiymat `ValidationError`/`ValueError` beradi —
    ular ham yutiladi, aks holda soxta chipta handshake'ni 500 bilan yiqitadi.
    """
    User = get_user_model()
    try:
        return User.objects.get(pk=user_id, is_active=True)
    except (User.DoesNotExist, ValidationError, ValueError, TypeError):
        return AnonymousUser()


@database_sync_to_async
def _user_from_ticket(raw_ticket):
    """Chiptani ishlatadi (bir marta!) va foydalanuvchini qaytaradi."""
    user_id = consume_ticket(raw_ticket)
    if user_id is None:
        return AnonymousUser()
    return _active_user(user_id)


@database_sync_to_async
def _user_from_token(raw_token):
    try:
        token = AccessToken(raw_token)
    except (InvalidToken, TokenError):
        return AnonymousUser()
    return _active_user(token["user_id"])


class JWTAuthMiddleware:
    """Soketni autentifikatsiya qilishning yagona yo'li: chipta yoki JWT.

    Ataylab channels' AuthMiddlewareStack ustiga qo'yilmagan — sessiya cookie'si
    WebSocket'ni autentifikatsiya qila olmasligi kerak, aks holda saytlararo
    handshake qurbonning cookie'sida yurib ketadi.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        ticket = (query.get("ticket") or [None])[0]
        token = (query.get("token") or [None])[0]
        scope = dict(scope)
        if ticket:
            scope["user"] = await _user_from_ticket(ticket)
        elif token:
            # DEPRECATED yo'l — yuqoridagi modul izohiga qarang.
            scope["user"] = await _user_from_token(token)
        else:
            scope["user"] = AnonymousUser()
        return await self.inner(scope, receive, send)
