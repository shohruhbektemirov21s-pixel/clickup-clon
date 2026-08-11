"""Tashqi tekshiruv API'lari — SMTP o'rniga qo'yiladigan variant.

Nega kerak: SMTP `RCPT TO` yirik provayderlarda ishlamaydi (`smtp.py` ning
izohiga qarang). Tijorat xizmatlari buni o'z reputatsiyali IP havzasi,
provayder bilan tuzilgan kelishuvlar va tarixiy ma'lumot bazasi bilan hal
qiladi.

Bu yerda uchta xizmat uchun adapter bor. Ular faqat ikki narsada farq
qiladi — so'rov URL'i va javobdagi status maydonini bizning
`EmailStatus` ga o'girish — shuning uchun umumiy qismi `ExternalApiVerifier`
da, farqi esa `ProviderSpec` da.

Yangi xizmat qo'shish = bitta `ProviderSpec` yozish, boshqa hech narsa.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from apps.emailcheck.verifiers.base import (
    EmailStatus,
    VerificationResult,
    Verifier,
    check_syntax,
)


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Bitta tashqi xizmatning "shakli"."""

    name: str
    #: `(api_key, email) -> to'liq URL`
    build_url: Callable[[str, str], str]
    #: `javob_json -> (status, sabab)`
    parse: Callable[[dict], tuple[EmailStatus, str]]


def _zerobounce_parse(payload: dict) -> tuple[EmailStatus, str]:
    status = str(payload.get("status", "")).lower()
    sub = str(payload.get("sub_status", "") or "")
    mapping = {
        "valid": EmailStatus.VALID,
        "invalid": EmailStatus.INVALID,
        "catch-all": EmailStatus.RISKY,
        "spamtrap": EmailStatus.RISKY,
        "abuse": EmailStatus.RISKY,
        "do_not_mail": EmailStatus.RISKY,
        "unknown": EmailStatus.UNKNOWN,
    }
    resolved = mapping.get(status, EmailStatus.UNKNOWN)
    reason = f"ZeroBounce: {status}" + (f" / {sub}" if sub else "")
    return resolved, reason


def _abstract_parse(payload: dict) -> tuple[EmailStatus, str]:
    deliverability = str(payload.get("deliverability", "")).upper()
    # AbstractAPI ba'zan `{"value": ...}` shaklida qaytaradi.
    def flag(key: str) -> bool:
        raw = payload.get(key)
        if isinstance(raw, dict):
            return bool(raw.get("value"))
        return bool(raw)

    if flag("is_catchall_email"):
        return EmailStatus.RISKY, "AbstractAPI: catch-all domen"
    if flag("is_disposable_email"):
        return EmailStatus.RISKY, "AbstractAPI: bir martalik manzil"
    mapping = {
        "DELIVERABLE": EmailStatus.VALID,
        "UNDELIVERABLE": EmailStatus.INVALID,
        "RISKY": EmailStatus.RISKY,
        "UNKNOWN": EmailStatus.UNKNOWN,
    }
    resolved = mapping.get(deliverability, EmailStatus.UNKNOWN)
    return resolved, f"AbstractAPI: {deliverability or 'javob tushunarsiz'}"


def _hunter_parse(payload: dict) -> tuple[EmailStatus, str]:
    data = payload.get("data") or {}
    result = str(data.get("result", "")).lower()
    status = str(data.get("status", "") or "")
    if data.get("accept_all"):
        return EmailStatus.RISKY, "Hunter: accept-all domen"
    mapping = {
        "deliverable": EmailStatus.VALID,
        "undeliverable": EmailStatus.INVALID,
        "risky": EmailStatus.RISKY,
        "unknown": EmailStatus.UNKNOWN,
    }
    resolved = mapping.get(result, EmailStatus.UNKNOWN)
    return resolved, f"Hunter: {result or status or 'javob tushunarsiz'}"


PROVIDERS: dict[str, ProviderSpec] = {
    "zerobounce": ProviderSpec(
        name="zerobounce",
        build_url=lambda key, email: (
            "https://api.zerobounce.net/v2/validate?"
            + urllib.parse.urlencode({"api_key": key, "email": email})
        ),
        parse=_zerobounce_parse,
    ),
    "abstractapi": ProviderSpec(
        name="abstractapi",
        build_url=lambda key, email: (
            "https://emailvalidation.abstractapi.com/v1/?"
            + urllib.parse.urlencode({"api_key": key, "email": email})
        ),
        parse=_abstract_parse,
    ),
    "hunter": ProviderSpec(
        name="hunter",
        build_url=lambda key, email: (
            "https://api.hunter.io/v2/email-verifier?"
            + urllib.parse.urlencode({"api_key": key, "email": email})
        ),
        parse=_hunter_parse,
    ),
}


class ExternalApiVerifier(Verifier):
    """Tashqi HTTP xizmati orqali tekshiradi.

    Sintaksis MAHALLIY tekshiriladi: aniq buzuq qator uchun pullik so'rov
    yuborish ma'nosiz.

    HTTP `urllib` bilan, `asyncio.to_thread()` ichida bajariladi. Sabab —
    loyihaga yana bitta bog'liqlik (`httpx`/`aiohttp`) qo'shmaslik; barobar
    ishlar soni runner'dagi semaphore bilan chegaralangani uchun oqim soni
    ham cheklangan bo'ladi.
    """

    def __init__(
        self,
        *,
        provider: str,
        api_key: str,
        timeout: float = 15.0,
        retries: int = 2,
    ) -> None:
        try:
            self.spec = PROVIDERS[provider]
        except KeyError:
            known = ", ".join(sorted(PROVIDERS))
            raise ValueError(f"noma'lum provayder {provider!r}; mavjudlari: {known}") from None
        if not api_key:
            raise ValueError(f"{provider} uchun API kalit berilmagan")
        self.name = self.spec.name
        self.api_key = api_key
        self.timeout = timeout
        self.retries = max(0, retries)

    async def verify(self, email: str) -> VerificationResult:
        reason = check_syntax(email)
        if reason is not None:
            return self._result(email, EmailStatus.INVALID, f"sintaksis: {reason}")

        attempts = self.retries + 1
        last_error = "urinish bo'lmadi"
        for attempt in range(attempts):
            try:
                payload = await asyncio.to_thread(self._fetch, email)
            except urllib.error.HTTPError as exc:
                # 4xx — bizning xatomiz (kalit, kvota): takrorlash foydasiz.
                if 400 <= exc.code < 500 and exc.code != 429:
                    return self._result(
                        email, EmailStatus.UNKNOWN, f"API rad etdi ({exc.code})"
                    )
                last_error = f"API xatosi ({exc.code})"
            except (urllib.error.URLError, TimeoutError, asyncio.TimeoutError) as exc:
                last_error = f"tarmoq xatosi: {exc.__class__.__name__}"
            except json.JSONDecodeError:
                last_error = "API javobi JSON emas"
            else:
                status, why = self.spec.parse(payload)
                return self._result(email, status, why)

            if attempt < attempts - 1:
                await asyncio.sleep(2**attempt)

        return self._result(email, EmailStatus.UNKNOWN, last_error)

    def _fetch(self, email: str) -> dict:
        url = self.spec.build_url(self.api_key, email)
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8", "replace"))
