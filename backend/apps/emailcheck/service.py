"""Sinxron Django kodidan bitta manzilni tekshirish uchun ko'prik.

View qatlami sinxron (DRF), tekshiruv esa async. `asyncio.run()` shu yerda,
bitta joyda chaqiriladi va **qattiq umumiy timeout** bilan o'raladi: veb
so'rov SMTP suhbatining tugashini cheksiz kutib o'tira olmaydi.
"""

from __future__ import annotations

import asyncio

from django.conf import settings

from apps.emailcheck.resolver import MxResolver
from apps.emailcheck.throttle import DomainThrottle
from apps.emailcheck.verifiers import build_verifier
from apps.emailcheck.verifiers.base import (
    EmailStatus,
    VerificationResult,
    check_syntax,
    domain_of,
    normalise,
)

#: Bitta so'rov uchun eng ko'p kutish. Undan oshsa `unknown` qaytadi —
#: klient javobsiz osilib qolgandan ko'ra "noaniq" olgani yaxshi.
REQUEST_TIMEOUT = 12.0

#: Sinxron qatlamdan yaratiladigan verifier'lar orasida bo'lishiladigan kesh.
#: DNS natijalari domen bo'yicha keshlanadi, ya'ni bir xil domenli ketma-ket
#: so'rovlar DNS'ga chiqmaydi.
_resolver = MxResolver()
_throttle = DomainThrottle(interval=1.0, concurrency=1)


def _configured_verifier():
    """Sozlamaga qarab verifier yasaydi; sozlanmagan bo'lsa `None`.

    `None` — bu xato emas, ATAYLAB xavfsiz default: qo'shimcha sozlamasiz
    server hech kimning MX'iga SMTP so'rov yubormaydi. Bunday holda faqat
    sintaksis va MX bosqichlari ishlaydi.
    """
    kind = (getattr(settings, "EMAILCHECK_VERIFIER", "") or "").strip().lower()
    if not kind:
        return None
    if kind == "smtp":
        helo = getattr(settings, "EMAILCHECK_HELO_HOSTNAME", "")
        mail_from = getattr(settings, "EMAILCHECK_MAIL_FROM", "")
        if not helo or not mail_from:
            return None
        return build_verifier(
            "smtp",
            helo_hostname=helo,
            mail_from=mail_from,
            resolver=_resolver,
            throttle=_throttle,
            timeout=REQUEST_TIMEOUT / 2,
            retries=1,
        )
    api_key = getattr(settings, "EMAILCHECK_API_KEY", "")
    if not api_key:
        return None
    return build_verifier(kind, api_key=api_key, timeout=REQUEST_TIMEOUT / 2, retries=1)


async def _verify(email: str) -> VerificationResult:
    verifier = _configured_verifier()
    if verifier is None:
        return await _syntax_and_mx_only(email)
    async with verifier:
        return await verifier.verify(email)


async def _syntax_and_mx_only(email: str) -> VerificationResult:
    """To'liq verifier sozlanmagandagi zaxira yo'l.

    Bu bosqichlar ham foydali: buzuq format va pochta qabul qilmaydigan domen
    ro'yxatdagi yaroqsiz manzillarning katta qismini tashkil qiladi. Qolgani
    `unknown` — "tekshirilmadi" degani, "yaroqli" degani EMAS.
    """
    reason = check_syntax(email)
    if reason is not None:
        return VerificationResult(
            email=email,
            status=EmailStatus.INVALID,
            reason=f"sintaksis: {reason}",
            provider="local",
        )
    lookup = await _resolver.resolve(domain_of(email))
    if not lookup.ok:
        return VerificationResult(
            email=email,
            status=EmailStatus.INVALID,
            reason=f"MX: {lookup.error or 'topilmadi'}",
            provider="local",
        )
    return VerificationResult(
        email=email,
        status=EmailStatus.UNKNOWN,
        reason=(
            "domen pochta qabul qiladi, lekin manzil mavjudligi tekshirilmadi "
            "(EMAILCHECK_VERIFIER sozlanmagan)"
        ),
        mx_host=lookup.hosts[0],
        provider="local",
    )


def verify_one(raw_email: str) -> VerificationResult:
    """Bitta manzilni tekshiradi. Sinxron — view'dan to'g'ridan-to'g'ri chaqiriladi."""
    email = normalise(raw_email)

    async def run():
        return await asyncio.wait_for(_verify(email), timeout=REQUEST_TIMEOUT)

    try:
        return asyncio.run(run())
    except (asyncio.TimeoutError, TimeoutError):
        return VerificationResult(
            email=email,
            status=EmailStatus.UNKNOWN,
            reason=f"tekshiruv {REQUEST_TIMEOUT:.0f} soniyada tugamadi",
            provider="local",
        )
