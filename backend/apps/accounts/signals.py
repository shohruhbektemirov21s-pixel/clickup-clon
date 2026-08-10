"""Autentifikatsiya hodisalarining audit jurnali — AppSec B.2.4.

Nega signal, nega `views.py` emas:

* `user_logged_in` / `user_login_failed` / `user_logged_out` — Django'ning
  `authenticate()` va `login()` ichidan chiqadi. Ya'ni bitta joyga ulanib,
  **barcha** kirish yo'llarini qamrab olamiz: `/admin/` login formasi,
  management-command va kelajakdagi SSO backend. View'larga qo'lda
  `logger.info(...)` qo'shish esa har safar yangi yo'l qo'shilganda
  unutiladigan va jimgina audit teshigi ochadigan yondashuv.
* API kirish yo'li (`POST /api/v1/auth/login/`) endi ayni shu signallarni
  chiqaradi: `LoginSerializer` `django.contrib.auth.authenticate()` ni
  chaqiradi (muvaffaqiyatsizlikda `user_login_failed` o'zi chiqadi) va
  muvaffaqiyatda `user_logged_in` ni **aniq** `request` bilan yuboradi.
  `login()` ataylab chaqirilmaydi: JWT API sessiya cookie'siga muhtoj emas,
  bir dona `user_logged_in` esa audit uchun yetarli. Xuddi shunday
  `auth/demo/` va `auth/logout/` ham signal chiqaradi — aks holda jurnalda
  faqat `/admin/` ko'rinardi, ya'ni asosiy kirish nuqtasi auditdan tashqarida
  qolardi (2026-08 AppSec topilmasi).
* Muvaffaqiyatsiz urinishlar `WARNING` darajasida chiqadi — bitta email yoki
  bitta IP bo'yicha ketma-ket `auth.login_failed` brute-force / credential
  stuffing signali; log shipper'da shu daraja bo'yicha alert qo'yiladi.

Yozuv `apps.accounts.auth` logger'iga boradi (`LOGGING` da `apps` — JSON
formatter). Parol hech qachon logga tushmaydi: Django `user_login_failed`
ga uzatiladigan `credentials` ni allaqachon `sensitive_variables` bo'yicha
maskalaydi, biz esa faqat email/IP/User-Agent ni olamiz.
"""

import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver
from rest_framework.settings import api_settings

logger = logging.getLogger("apps.accounts.auth")

#: User-Agent'ni cheklaymiz — u foydalanuvchi boshqaradigan maydon va
#: cheklanmasa log qatorini xohlagancha shishirish mumkin (log injection/DoS).
_USER_AGENT_MAX = 200


#: Ishonchli proxy soni aniqlanmagan bo'lsa **hech biriga** ishonmaymiz.
#: DRF'ning o'z sukut qiymati `None` = "butun `X-Forwarded-For` zanjirini ol",
#: ya'ni aynan shu funksiya bartaraf qilmoqchi bo'lgan soxtalashtirish.
_DEFAULT_NUM_PROXIES = 0

#: IP maydonining maksimal uzunligi (log injection/DoS'ga qarshi).
_IP_MAX = 64


def _num_proxies() -> int:
    """Oldimizda turgan **ishonchli** proxy soni.

    Qiymat DRF sozlamasidan (`REST_FRAMEWORK["NUM_PROXIES"]`) o'qiladi —
    throttling ham aynan shundan foydalanadi, ya'ni "mijoz kim" degan savolga
    audit jurnali va rate-limit **bir xil** javob beradi. Sozlanmagan bo'lsa
    fail-closed: faqat `REMOTE_ADDR`.
    """
    value = getattr(api_settings, "NUM_PROXIES", None)
    if value is None:
        return _DEFAULT_NUM_PROXIES
    try:
        value = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_NUM_PROXIES
    return max(value, 0)


def _client_ip(request):
    """Mijoz IP'si — `X-Forwarded-For` zanjirining O'NGDAN `NUM_PROXIES`-chisi.

    `X-Forwarded-For` — mijoz yuboradigan sarlavha. Har bir proxy o'zi ko'rgan
    manzilni zanjirning **oxiriga** qo'shadi, shuning uchun ishonchli hop faqat
    o'ngdan sanaganda topiladi. Ilgari bu yerda eng chapdagi element olinardi:
    buzg'unchi `X-Forwarded-For: 8.8.8.8` yuborib, `auth.login_failed`
    yozuvlarini istalgan manzilga yozdirib yuborardi va per-IP brute-force
    alerti (bu modul aynan shuning uchun yozilgan) butunlay ko'r bo'lardi.

    Indeksatsiya DRF `BaseThrottle.get_ident()` bilan bir xil:
    `addrs[-min(NUM_PROXIES, len(addrs))]`.
    """
    if request is None:
        return None
    meta = getattr(request, "META", None) or {}
    remote_addr = (meta.get("REMOTE_ADDR") or "")[:_IP_MAX] or None

    num_proxies = _num_proxies()
    forwarded = meta.get("HTTP_X_FORWARDED_FOR")
    if num_proxies == 0 or not forwarded:
        return remote_addr

    addrs = [part.strip() for part in forwarded.split(",")]
    client = addrs[-min(num_proxies, len(addrs))][:_IP_MAX]
    return client or remote_addr


def _user_agent(request):
    if request is None:
        return None
    meta = getattr(request, "META", None) or {}
    agent = meta.get("HTTP_USER_AGENT")
    return agent[:_USER_AGENT_MAX] if agent else None


def _log(event, *, request=None, email=None, level=logging.INFO):
    ip = _client_ip(request)
    agent = _user_agent(request)
    logger.log(
        level,
        "auth.%s email=%s ip=%s user_agent=%s",
        event,
        email or "-",
        ip or "-",
        agent or "-",
        extra={
            "event": f"auth.{event}",
            "email": email,
            "ip": ip,
            "user_agent": agent,
        },
    )


@receiver(user_logged_in, dispatch_uid="accounts.audit.user_logged_in")
def log_user_logged_in(sender, request=None, user=None, **kwargs):
    _log("login_succeeded", request=request, email=getattr(user, "email", None))


@receiver(user_login_failed, dispatch_uid="accounts.audit.user_login_failed")
def log_user_login_failed(sender, credentials=None, request=None, **kwargs):
    credentials = credentials or {}
    # `USERNAME_FIELD` = email, lekin ba'zi backend'lar `username` kaliti bilan
    # keladi — ikkalasini ham qaraymiz.
    email = credentials.get("email") or credentials.get("username")
    _log("login_failed", request=request, email=email, level=logging.WARNING)


@receiver(user_logged_out, dispatch_uid="accounts.audit.user_logged_out")
def log_user_logged_out(sender, request=None, user=None, **kwargs):
    _log("logout", request=request, email=getattr(user, "email", None))
