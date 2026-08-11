"""Domen uchun MX yozuvlarini topish — natija keshlanadi.

Nega alohida modul: bitta 50 000 qatorli ro'yxatda `gmail.com` 20 000 marta
uchraydi. Har safar DNS so'rash ma'nosiz, shuning uchun domen bo'yicha kesh
bor. Kesh **stampede'ga qarshi** himoyalangan: bir vaqtning o'zida 200 ta
korutina bir xil yangi domenni so'rasa, DNS'ga bitta so'rov ketadi va
qolganlari shu natijani kutadi.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import dns.asyncresolver
import dns.exception
import dns.resolver


@dataclass(frozen=True, slots=True)
class MxLookup:
    """Domen uchun DNS natijasi."""

    #: Ustuvorlik bo'yicha saralangan MX xostlari (eng past `preference` oldin).
    hosts: tuple[str, ...]
    #: Xato bo'lsa o'zbekcha sabab; muvaffaqiyatda `None`.
    error: str | None = None
    #: MX yo'q, lekin A/AAAA bor — RFC 5321 §5.1 bo'yicha domenning o'zi MX.
    implicit: bool = False

    @property
    def ok(self) -> bool:
        return bool(self.hosts)


class MxResolver:
    """Domen → MX, ichki kesh va stampede himoyasi bilan."""

    def __init__(self, *, timeout: float = 5.0, lifetime: float = 10.0) -> None:
        self._resolver = dns.asyncresolver.Resolver()
        self._resolver.timeout = timeout
        self._resolver.lifetime = lifetime
        self._cache: dict[str, MxLookup] = {}
        # Domen → shu domenni hozir kim so'rayotgani. Kalit `_cache` ga
        # yozilgandan keyin olib tashlanadi.
        self._inflight: dict[str, asyncio.Future[MxLookup]] = {}

    async def resolve(self, domain: str) -> MxLookup:
        domain = domain.lower().rstrip(".")
        cached = self._cache.get(domain)
        if cached is not None:
            return cached

        inflight = self._inflight.get(domain)
        if inflight is not None:
            # Boshqa korutina allaqachon so'rayapti — shu natijani kutamiz.
            return await asyncio.shield(inflight)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[MxLookup] = loop.create_future()
        self._inflight[domain] = future
        try:
            lookup = await self._lookup(domain)
        except Exception as exc:  # noqa: BLE001 — kesh hech qachon buzilmasin
            lookup = MxLookup(hosts=(), error=f"DNS xatosi: {exc.__class__.__name__}")
        self._cache[domain] = lookup
        self._inflight.pop(domain, None)
        if not future.done():
            future.set_result(lookup)
        return lookup

    async def _lookup(self, domain: str) -> MxLookup:
        try:
            answer = await self._resolver.resolve(domain, "MX")
        except dns.resolver.NXDOMAIN:
            return MxLookup(hosts=(), error="domen mavjud emas (NXDOMAIN)")
        except dns.resolver.NoAnswer:
            # MX yo'q — RFC 5321 §5.1: A/AAAA bo'lsa domenning o'zi MX
            # hisoblanadi. Ko'p kichik domenlar aynan shunday sozlangan.
            return await self._implicit_mx(domain)
        except dns.resolver.NoNameservers:
            return MxLookup(hosts=(), error="domen nameserver'lari javob bermadi")
        except (dns.exception.Timeout, asyncio.TimeoutError):
            return MxLookup(hosts=(), error="DNS so'rovi vaqt bo'yicha uzildi")

        hosts = tuple(
            str(record.exchange).rstrip(".")
            for record in sorted(answer, key=lambda r: r.preference)
            # "Null MX" (RFC 7505): domen ataylab pochta qabul qilmaydi.
            if str(record.exchange).rstrip(".") not in ("", ".")
        )
        if not hosts:
            return MxLookup(hosts=(), error="domen pochta qabul qilmaydi (null MX)")
        return MxLookup(hosts=hosts)

    async def _implicit_mx(self, domain: str) -> MxLookup:
        for record_type in ("A", "AAAA"):
            try:
                await self._resolver.resolve(domain, record_type)
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                continue
            except (dns.exception.Timeout, dns.resolver.NoNameservers, asyncio.TimeoutError):
                return MxLookup(hosts=(), error="DNS so'rovi vaqt bo'yicha uzildi")
            return MxLookup(hosts=(domain,), implicit=True)
        return MxLookup(hosts=(), error="MX yozuvi yo'q")
