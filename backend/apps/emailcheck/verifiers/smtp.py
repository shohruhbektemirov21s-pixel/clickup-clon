"""SMTP `RCPT TO` orqali tekshirish.

Oqim: sintaksis → MX → SMTP suhbat. Xat HECH QACHON yuborilmaydi: suhbat
`RCPT TO` dan keyin `QUIT` bilan uziladi, `DATA` bosqichiga o'tilmaydi.

**Bu usulning chegarasi — dizayn nuqsoni emas, protokolning holati.** Yirik
provayderlar (Gmail, Outlook, Yahoo) manzil bor-yo'qligini ataylab oshkor
qilmaydi: ular mavjud bo'lmagan qutiga ham `250` beradi va xatni keyinroq
qaytaradi, yoki noma'lum IP'dan kelgan so'rovni umuman rad etadi. Shuning
uchun bu verifier ularni ko'pincha `unknown` deb belgilaydi va bu TO'G'RI
javob — "valid" deb yolg'on ishonch berishdan yaxshiroq. Ishonchlilik kerak
bo'lsa `verifiers.external.ExternalApiVerifier` ni qo'ying.
"""

from __future__ import annotations

import asyncio
import secrets
import ssl

import aiosmtplib

from apps.emailcheck.resolver import MxResolver
from apps.emailcheck.throttle import DomainThrottle
from apps.emailcheck.verifiers.base import (
    EmailStatus,
    VerificationResult,
    Verifier,
    check_syntax,
    domain_of,
)

#: Vaqtinchalik xatolar — qayta urinishga arziydi.
TRANSIENT_PREFIXES = (4,)


def _probe_tls_context() -> ssl.SSLContext:
    """STARTTLS uchun sertifikatni TEKSHIRMAYDIGAN kontekst.

    Bu ataylab va faqat SHU modul uchun to'g'ri qaror. Sabablari:

    * SMTP'da TLS **opportunistik** (RFC 7435): MX serverlarning katta qismi
      o'z-o'zidan imzolangan yoki xost nomiga mos kelmaydigan sertifikat
      ishlatadi, chunki muqobil — umuman shifrsiz uzatish.
    * Biz bu ulanish orqali HECH QANDAY maxfiy narsa yubormaymiz: suhbat
      `MAIL FROM` va `RCPT TO` dan iborat, `DATA` bosqichiga o'tilmaydi.
    * Qat'iy tekshiruv bilan Gmail kabi yirik MX'larda ulanish uziladi va
      har bir manzil `unknown` bo'lib qoladi — ya'ni tekshiruv umuman
      ishlamaydi.

    Bu qoidani xat YUBORADIGAN kodga ko'chirmang: u yerda sertifikat
    tekshiruvi shart.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class SmtpVerifier(Verifier):
    """MX serverga ulanib `RCPT TO` so'raydigan verifier.

    `helo_hostname` va `mail_from` — server ko'radigan kimlik. Ikkalasi ham
    HAQIQIY va sizga tegishli bo'lishi kerak: ko'p server yuboruvchi domenni
    tekshiradi (SPF, reverse DNS) va mos kelmasa ulanishni uzadi.
    """

    name = "smtp"

    def __init__(
        self,
        *,
        helo_hostname: str,
        mail_from: str,
        resolver: MxResolver | None = None,
        throttle: DomainThrottle | None = None,
        timeout: float = 10.0,
        retries: int = 2,
        detect_catch_all: bool = True,
    ) -> None:
        self.helo_hostname = helo_hostname
        self.mail_from = mail_from
        self.resolver = resolver or MxResolver()
        self.throttle = throttle or DomainThrottle(interval=1.0, concurrency=1)
        self.timeout = timeout
        self.retries = max(0, retries)
        self.detect_catch_all = detect_catch_all
        #: Domen → catch-all mi. Domen bo'yicha bir marta aniqlanadi.
        self._catch_all: dict[str, bool | None] = {}
        self._catch_all_locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------ public API

    async def verify(self, email: str) -> VerificationResult:
        reason = check_syntax(email)
        if reason is not None:
            return self._result(email, EmailStatus.INVALID, f"sintaksis: {reason}")

        domain = domain_of(email)
        lookup = await self.resolver.resolve(domain)
        if not lookup.ok:
            # MX yo'q = bu domen pochta qabul qilmaydi. Bu aniq javob, taxmin
            # emas, shuning uchun `invalid`.
            return self._result(
                email, EmailStatus.INVALID, f"MX: {lookup.error or 'topilmadi'}"
            )

        host = lookup.hosts[0]
        probe = await self._probe_with_retry(host, domain, email)

        if probe.code is None:
            return self._result(
                email, EmailStatus.UNKNOWN, probe.reason, mx_host=host
            )

        if probe.code == 550 or 500 <= probe.code < 600:
            return self._result(
                email,
                EmailStatus.INVALID,
                f"server rad etdi ({probe.code}): {probe.reason}",
                mx_host=host,
                smtp_code=probe.code,
            )

        if 200 <= probe.code < 300:
            if self.detect_catch_all and await self._is_catch_all(host, domain):
                return self._result(
                    email,
                    EmailStatus.RISKY,
                    "domen catch-all: har qanday manzilni qabul qiladi, "
                    "shuning uchun 250 javobi mavjudlikni isbotlamaydi",
                    mx_host=host,
                    smtp_code=probe.code,
                )
            return self._result(
                email,
                EmailStatus.VALID,
                f"server qabul qildi ({probe.code})",
                mx_host=host,
                smtp_code=probe.code,
            )

        return self._result(
            email,
            EmailStatus.UNKNOWN,
            f"vaqtinchalik javob ({probe.code}): {probe.reason}",
            mx_host=host,
            smtp_code=probe.code,
        )

    # --------------------------------------------------------------- probing

    class _Probe:
        __slots__ = ("code", "reason")

        def __init__(self, code: int | None, reason: str) -> None:
            self.code = code
            self.reason = reason

    async def _probe_with_retry(self, host: str, domain: str, email: str) -> _Probe:
        """`RCPT TO` ni `retries + 1` marta urinadi.

        Qayta urinish FAQAT vaqtinchalik holatda: 4xx, timeout, ulanish
        uzilishi. `550` yakuniy javob — uni takrorlash serverga ortiqcha yuk
        va bizga yangi ma'lumot bermaydi.
        """
        attempts = self.retries + 1
        probe = self._Probe(None, "urinish bo'lmadi")
        for attempt in range(attempts):
            async with self.throttle.acquire(domain):
                probe = await self._probe_once(host, email)
            if probe.code is not None and not self._is_transient(probe.code):
                return probe
            if attempt < attempts - 1:
                # Oddiy eksponensial kutish: 1s, 2s.
                await asyncio.sleep(2**attempt)
        return probe

    @staticmethod
    def _is_transient(code: int) -> bool:
        return code // 100 in TRANSIENT_PREFIXES

    async def _probe_once(self, host: str, email: str, *, use_tls: bool = True) -> _Probe:
        # `start_tls=False` SHART: aiosmtplib `connect()` ichida STARTTLS'ni
        # O'ZI bajaradi va standart (sertifikat tekshiradigan) kontekstdan
        # foydalanadi. Ya'ni bizning `starttls()` chaqiruvimizgacha ulanish
        # allaqachon `SSLCertVerificationError` bilan uzilgan bo'lardi va
        # Gmail kabi MX'lar doimo `unknown` bo'lib qolardi.
        client = aiosmtplib.SMTP(
            hostname=host,
            port=25,
            timeout=self.timeout,
            start_tls=False,
            tls_context=_probe_tls_context(),
            validate_certs=False,
        )
        try:
            await client.connect()
            await client.ehlo(hostname=self.helo_hostname)
            if use_tls and client.supports_extension("starttls"):
                try:
                    await client.starttls(tls_context=_probe_tls_context())
                    await client.ehlo(hostname=self.helo_hostname)
                except (aiosmtplib.SMTPException, ssl.SSLError, OSError):
                    # STARTTLS yiqilgach seans ishlamay qoladi — davom etib
                    # bo'lmaydi. Yangi ulanish ochib, TLS'siz urinamiz.
                    try:
                        await client.quit()
                    except Exception:  # noqa: BLE001
                        pass
                    return await self._probe_once(host, email, use_tls=False)
            await client.mail(self.mail_from)
            code, message = await client.rcpt(email)
            return self._Probe(code, _clean(message))
        except aiosmtplib.SMTPResponseException as exc:
            return self._Probe(exc.code, _clean(exc.message))
        except (aiosmtplib.SMTPConnectError, aiosmtplib.SMTPServerDisconnected) as exc:
            return self._Probe(None, f"ulanib bo'lmadi: {_clean(str(exc))}")
        except (asyncio.TimeoutError, TimeoutError):
            return self._Probe(None, f"vaqt tugadi ({self.timeout:.0f}s)")
        except (OSError, aiosmtplib.SMTPException) as exc:
            return self._Probe(None, f"SMTP xatosi: {exc.__class__.__name__}")
        finally:
            # `QUIT` — xushmuomalalik: server ulanishni timeout bilan yopishini
            # kutmaydi. Bu yerdagi har qanday xato ahamiyatsiz.
            try:
                await client.quit()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------- catch-all

    async def _is_catch_all(self, host: str, domain: str) -> bool:
        """Domen borini ham, yo'qini ham qabul qiladimi.

        Tasodifiy, deyarli mavjud bo'lishi mumkin bo'lmagan manzil so'raladi.
        Server unga ham `250` bersa, uning `250` javobi hech narsani
        anglatmaydi va shu domendagi HAR BIR manzil `risky` bo'ladi.

        Natija domen bo'yicha keshlanadi: bu qo'shimcha SMTP suhbati, uni har
        bir manzil uchun takrorlash yukni ikki barobar oshirardi.
        """
        cached = self._catch_all.get(domain)
        if cached is not None:
            return cached

        lock = self._catch_all_locks.setdefault(domain, asyncio.Lock())
        async with lock:
            cached = self._catch_all.get(domain)
            if cached is not None:
                return cached

            probe_address = f"{secrets.token_hex(12)}@{domain}"
            async with self.throttle.acquire(domain):
                probe = await self._probe_once(host, probe_address)
            # Faqat aniq `2xx` catch-all deb hisoblanadi. Timeout yoki 4xx —
            # bilmaymiz, va "bilmayman" catch-all EMAS: aks holda tarmoq
            # uzilishi butun domenni `risky` qilib qo'yardi.
            is_catch_all = probe.code is not None and 200 <= probe.code < 300
            self._catch_all[domain] = is_catch_all
            return is_catch_all


def _clean(message: object) -> str:
    """SMTP javobini bitta qatorga siqadi — CSV maydonini buzmasin."""
    text = message.decode("utf-8", "replace") if isinstance(message, bytes) else str(message)
    return " ".join(text.split())[:200]
