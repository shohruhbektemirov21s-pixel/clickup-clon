"""Domen bo'yicha tezlik cheklovi.

Ommaviy tekshiruvda IP bloklanishining eng keng tarqalgan sababi — bitta
pochta serveriga bir vaqtda o'nlab ulanish ochish. Global concurrency bunga
yordam bermaydi: 100 ta parallel ish 100 ta har xil domenga tarqalsa
muammosiz, lekin hammasi `gmail.com` ga tushsa server darhol cheklaydi.

Shuning uchun ikki qatlam bor va ular MUSTAQIL:

* `asyncio.Semaphore` — butun yurish bo'yicha nechta ish barobar ketishi;
* `DomainThrottle` — BITTA domenga nechta barobar ulanish va ular orasidagi
  eng kichik interval.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager


class DomainThrottle:
    """Har bir domen uchun: `concurrency` ta barobar ish, `interval` s oralab.

    Interval **boshlanishlar** orasida o'lchanadi, tugashlar orasida emas:
    tekshiruv 5 soniya davom etsa, keyingisi darhol boshlanadi, chunki
    serverga yuk allaqachon o'sha tezlikda tushgan.
    """

    def __init__(self, *, interval: float = 1.0, concurrency: int = 1) -> None:
        if interval < 0:
            raise ValueError("interval manfiy bo'lishi mumkin emas")
        if concurrency < 1:
            raise ValueError("concurrency kamida 1 bo'lishi kerak")
        self.interval = interval
        self.concurrency = concurrency
        self._gates: dict[str, asyncio.Semaphore] = {}
        self._next_free: dict[str, float] = {}
        # `_next_free` ni o'qish va yangilash atomar bo'lishi shart, aks holda
        # ikki korutina bir xil vaqtni ko'rib, ikkalasi ham darhol o'tib
        # ketardi.
        self._clock_lock = asyncio.Lock()

    def _gate(self, domain: str) -> asyncio.Semaphore:
        gate = self._gates.get(domain)
        if gate is None:
            gate = asyncio.Semaphore(self.concurrency)
            self._gates[domain] = gate
        return gate

    async def _wait_turn(self, domain: str) -> None:
        if self.interval <= 0:
            return
        while True:
            async with self._clock_lock:
                now = time.monotonic()
                ready_at = self._next_free.get(domain, 0.0)
                if now >= ready_at:
                    # Navbatni band qilamiz va darhol o'tamiz.
                    self._next_free[domain] = now + self.interval
                    return
                delay = ready_at - now
            # Kutish qulf TASHQARISIDA: aks holda bitta domenning kutishi
            # boshqa domenlarni ham to'xtatib qo'yardi.
            await asyncio.sleep(delay)

    @asynccontextmanager
    async def acquire(self, domain: str):
        """Domen uchun navbat oladi; blok tugaguncha ushlab turadi."""
        gate = self._gate(domain)
        async with gate:
            await self._wait_turn(domain)
            yield
