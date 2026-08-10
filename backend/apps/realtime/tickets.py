"""Bir martalik, qisqa umrli WebSocket handshake chiptalari (AppSec O-3).

Nega kerak: brauzer WebSocket handshake'ida sarlavha qo'ya olmaydi, shuning
uchun hisob ma'lumoti so'rov satrida ketadi. Agar u **access token** bo'lsa,
to'liq, qayta ishlatiladigan token oradagi har bir vositaning (nginx/ALB access
log, APM tracing, brauzer tarixi, Referer) yozuvlarida qoladi va u yerdan
o'g'irlangan token butun REST API'ni ochadi.

Chipta buni sindiradi:
  * opaque, tasodifiy 32 bayt — hech qanday da'vo (claim) olib yurmaydi;
  * `TICKET_TTL_SECONDS` (30s) dan keyin o'zi o'ladi;
  * **bir marta** ishlatiladi — `consume_ticket` uni darhol o'chiradi, shuning
    uchun log'dan olingan chipta amalda hech qachon ishlamaydi.

Cache'da chiptaning o'zi emas, SHA-256 hash'i saqlanadi: Redis dump'i yoki
`CACHE` ga o'qish huquqi bo'lgan yordamchi jarayon tirik chiptalar ro'yxatini
qo'lga kirita olmaydi (parol hash'lari bilan bir xil mantiq).

JOYLASHTIRISH SHARTI: chipta HTTP jarayonida beriladi, ASGI jarayonida
yechiladi. Ular bitta jarayon bo'lmasa (prod'dagi har qanday ko'p-worker'li
tuzilma), `CACHES["default"]` **umumiy** backend bo'lishi shart — ya'ni
`REDIS_URL`. LocMem faqat bitta jarayonli dev (`runserver`) uchun yetarli;
umumiy bo'lmagan cache'da har bir handshake rad etiladi. Bu `settings.py` da
throttle hisoblagichlariga qo'yilgan talab bilan bir xil.
"""

import hashlib
import secrets

from django.core.cache import cache

# Chipta faqat handshake'ni bosib o'tishi kerak — soat farqi uchun 30 soniya
# yetarlidan ham ko'p, lekin o'g'irlangan chipta uchun deraza juda tor.
TICKET_TTL_SECONDS = 30

_CACHE_PREFIX = "rt-ticket:"
_TICKET_BYTES = 32
# Cheklov: cheksiz uzunlikdagi qatorni hash qilishga majburlab bo'lmasin.
_MAX_TICKET_LENGTH = 256


def _key(raw_ticket: str) -> str:
    digest = hashlib.sha256(raw_ticket.encode("utf-8")).hexdigest()
    return f"{_CACHE_PREFIX}{digest}"


def issue_ticket(user) -> str:
    """Yangi chipta yaratadi va uni `user` ga bog'lab cache'ga yozadi."""
    raw = secrets.token_urlsafe(_TICKET_BYTES)
    cache.set(_key(raw), str(user.pk), TICKET_TTL_SECONDS)
    return raw


def consume_ticket(raw_ticket):
    """Chiptani ishlatadi va `user_id` (str) yoki `None` qaytaradi.

    `get` + `delete` atomik emas, shuning uchun bir martalik bo'lishni aynan
    `delete` ning qaytgan qiymati kafolatlaydi: ikkita parallel handshake bir
    xil chiptani olsa ham, kalitni faqat bittasi haqiqatda o'chira oladi,
    qolgani `None` oladi. (LocMem ham, Redis ham `delete` dan bool qaytaradi.)
    """
    if not raw_ticket or len(raw_ticket) > _MAX_TICKET_LENGTH:
        return None
    key = _key(raw_ticket)
    user_id = cache.get(key)
    if user_id is None:
        return None
    if not cache.delete(key):
        return None
    return user_id
