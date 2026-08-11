"""Ommaviy tekshiruvni boshqaradigan qatlam.

Ishlab chiqaruvchi/iste'molchi sxemasi: bitta yetkazuvchi kirish
iteratoridan o'qiydi, `concurrency` ta ishchi tekshiradi, natijalar kelishi
bilan chiqadi.

Nega `asyncio.gather` emas: `gather` butun ro'yxat uchun vazifa yaratadi,
ya'ni 500 000 qatorda 500 000 ta korutina obyekti xotirada turadi va
birinchi natija hammasi tugaguncha chiqmaydi. Bu yerdagi navbat esa
chegaralangan (`maxsize`), shuning uchun xotira kirish hajmiga BOG'LIQ EMAS
va natija darhol oqadi.
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Iterable

from apps.emailcheck.verifiers.base import EmailStatus, VerificationResult, Verifier

#: Navbat chuqurligi ishchilar soniga nisbatan. Kichik zaxira ishchilarni
#: och qoldirmaydi, katta zaxira esa xotirani bekorga band qiladi.
_QUEUE_FACTOR = 4

ProgressCallback = Callable[[int, int | None], None]


@dataclass(slots=True)
class RunStats:
    """Yurish yakunidagi sonlar."""

    total: int = 0
    counts: Counter = None  # type: ignore[assignment]
    elapsed: float = 0.0

    def __post_init__(self) -> None:
        if self.counts is None:
            self.counts = Counter()

    def add(self, result: VerificationResult) -> None:
        self.total += 1
        self.counts[result.status.value] += 1

    def as_dict(self) -> dict[str, int]:
        return {status.value: self.counts.get(status.value, 0) for status in EmailStatus}


async def verify_stream(
    emails: Iterable[str],
    verifier: Verifier,
    *,
    concurrency: int = 20,
    on_progress: ProgressCallback | None = None,
    total_hint: int | None = None,
) -> AsyncIterator[VerificationResult]:
    """Manzillarni tekshiradi va natijalarni TAYYOR BO'LISHI bilan qaytaradi.

    Tartib SAQLANMAYDI — natija kirish tartibida emas, tugash tartibida
    keladi. Bu ataylab: sekin domen butun oqimni to'xtatib qo'ymasligi
    kerak. Kirish tartibi kerak bo'lsa chiqishni `email` bo'yicha
    solishtiring.
    """
    if concurrency < 1:
        raise ValueError("concurrency kamida 1 bo'lishi kerak")

    queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=concurrency * _QUEUE_FACTOR)
    results: asyncio.Queue[VerificationResult | None] = asyncio.Queue(
        maxsize=concurrency * _QUEUE_FACTOR
    )

    async def produce() -> None:
        # Sinxron iterator (fayl o'qish) event loop'ni bloklamasligi uchun
        # oqimga chiqariladi.
        def pull(iterator):
            try:
                return next(iterator)
            except StopIteration:
                return None

        iterator = iter(emails)
        while True:
            item = await asyncio.to_thread(pull, iterator)
            if item is None:
                break
            await queue.put(item)
        for _ in range(concurrency):
            await queue.put(None)

    async def work() -> None:
        while True:
            email = await queue.get()
            if email is None:
                return
            try:
                result = await verifier.verify(email)
            except Exception as exc:  # noqa: BLE001
                # `Verifier` shartnomasi buni taqiqlaydi, lekin bitta
                # noto'g'ri amalga oshiruv butun yurishni to'xtatmasligi
                # kerak.
                result = VerificationResult(
                    email=email,
                    status=EmailStatus.UNKNOWN,
                    reason=f"ichki xato: {exc.__class__.__name__}",
                    provider=getattr(verifier, "name", ""),
                )
            await results.put(result)

    producer = asyncio.create_task(produce())
    workers = [asyncio.create_task(work()) for _ in range(concurrency)]

    async def close_results() -> None:
        await producer
        await asyncio.gather(*workers)
        await results.put(None)

    closer = asyncio.create_task(close_results())

    done = 0
    try:
        while True:
            result = await results.get()
            if result is None:
                break
            done += 1
            if on_progress is not None:
                on_progress(done, total_hint)
            yield result
    finally:
        # Iste'molchi oqimni erta tashlab ketsa (`break`, istisno), fon
        # vazifalari osilib qolmasligi kerak.
        for task in (producer, closer, *workers):
            task.cancel()
        await asyncio.gather(producer, closer, *workers, return_exceptions=True)


async def verify_all(
    emails: Iterable[str],
    verifier: Verifier,
    *,
    concurrency: int = 20,
    on_progress: ProgressCallback | None = None,
    sink: Callable[[VerificationResult], None] | None = None,
    total_hint: int | None = None,
) -> RunStats:
    """`verify_stream` ustidagi qulaylik: sanaydi va `sink` ga uzatadi.

    `sink` — odatda `io.ResultWriter.write`. Natijalar ro'yxat sifatida
    YIG'ILMAYDI, shuning uchun xotira kirish hajmiga bog'liq emas.
    """
    stats = RunStats()
    started = time.monotonic()
    async for result in verify_stream(
        emails,
        verifier,
        concurrency=concurrency,
        on_progress=on_progress,
        total_hint=total_hint,
    ):
        stats.add(result)
        if sink is not None:
            sink(result)
    stats.elapsed = time.monotonic() - started
    return stats
