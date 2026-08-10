"""Autentifikatsiya hodisalarining audit jurnali — AppSec B.2.4.

Nega signal, nega `views.py` emas:

* `user_logged_in` / `user_login_failed` / `user_logged_out` — Django'ning
  `authenticate()` va `login()` ichidan chiqadi. Ya'ni bitta joyga ulanib,
  **barcha** kirish yo'llarini qamrab olamiz: DRF/simplejwt token endpoint,
  `/admin/` login formasi, management-command va kelajakdagi SSO backend.
  View'larga qo'lda `logger.info(...)` qo'shish esa har safar yangi yo'l
  qo'shilganda unutiladigan va jimgina audit teshigi ochadigan yondashuv.
* Muvaffaqiyatsiz urinishlar `WARNING` darajasida chiqadi — bitta email yoki
  bitta IP bo'yicha ketma-ket `auth.login_failed` brute-force / credential
  stuffing signali; log shipper'da shu daraja bo'yicha alert qo'yiladi.

Yozuv `apps.accounts.auth` logger'iga boradi (`LOGGING` da `apps` — JSON
formatter). Parol hech qachon logga tushmaydi: Django `user_login_failed`
ga uzatiladigan `credentials` ni allaqachon `sensitive_variables` bo'yicha
maskalaydi, biz esa faqat email/IP/User-Agent ni olamiz.
"""

import logging

from django.conf import settings
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

logger = logging.getLogger("apps.accounts.auth")

#: User-Agent'ni cheklaymiz — u foydalanuvchi boshqaradigan maydon va
#: cheklanmasa log qatorini xohlagancha shishirish mumkin (log injection/DoS).
_USER_AGENT_MAX = 200


def _client_ip(request):
    """Mijoz IP'si.

    `X-Forwarded-For` — mijoz yuboradigan, ya'ni SOXTALASHTIRISH mumkin bo'lgan
    sarlavha. Unga faqat oldinda ishonchli proxy turgani ma'lum bo'lganda
    (`SECURE_PROXY_SSL_HEADER` sozlangan) ishonamiz; aks holda faqat
    `REMOTE_ADDR`. Aks holda buzg'unchi audit jurnaliga istalgan IP'ni yozib,
    o'z izini boshqa manzilga o'tkazib yuborardi.
    """
    if request is None:
        return None
    meta = getattr(request, "META", None) or {}
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        forwarded = meta.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            # Eng chapdagi — asl mijoz; qolganlari proxy zanjiri.
            return forwarded.split(",")[0].strip()[:64] or None
    return meta.get("REMOTE_ADDR") or None


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
