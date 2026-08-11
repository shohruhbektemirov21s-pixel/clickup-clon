"""Ommaviy email tekshiruvi — CLI.

    # SMTP bilan (mahalliy, bepul, yirik provayderlarda "unknown" beradi)
    ../.venv/Scripts/python.exe manage.py verify_emails royxat.csv \\
        --output natija.csv \\
        --helo mening-domenim.uz --mail-from tekshiruv@mening-domenim.uz

    # Tashqi API bilan (ishonchli, pullik)
    ../.venv/Scripts/python.exe manage.py verify_emails royxat.csv \\
        --output natija.csv --verifier zerobounce --api-key $KALIT

Progress va hisobot `stderr` ga, natija CSV `--output` ga (yoki `-` bilan
`stdout` ga) tushadi — shuning uchun quvurga ulash xavfsiz:

    ... verify_emails royxat.txt --output - | grep ,valid,
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.emailcheck import io as check_io
from apps.emailcheck.resolver import MxResolver
from apps.emailcheck.runner import verify_all
from apps.emailcheck.throttle import DomainThrottle
from apps.emailcheck.verifiers import PROVIDERS, build_verifier


class Command(BaseCommand):
    help = "Email ro'yxatini ommaviy tekshiradi (sintaksis + MX + SMTP/API)."

    def add_arguments(self, parser):
        parser.add_argument("input", help="CSV yoki TXT fayl (har qatorda bitta email).")
        parser.add_argument(
            "--output",
            default="-",
            help="Natija CSV fayli. `-` bo'lsa stdout (standart).",
        )
        parser.add_argument(
            "--verifier",
            default="smtp",
            choices=["smtp", *sorted(PROVIDERS)],
            help="Tekshirish usuli (standart: smtp).",
        )
        parser.add_argument("--api-key", default="", help="Tashqi API kaliti.")
        parser.add_argument(
            "--concurrency",
            type=int,
            default=20,
            help="Barobar ketadigan tekshiruvlar soni (standart: 20).",
        )
        parser.add_argument(
            "--per-domain-interval",
            type=float,
            default=1.0,
            help="Bitta domenga so'rovlar orasidagi eng kichik interval, soniya (standart: 1.0).",
        )
        parser.add_argument(
            "--per-domain-concurrency",
            type=int,
            default=1,
            help="Bitta domenga barobar ulanish (standart: 1).",
        )
        parser.add_argument("--timeout", type=float, default=10.0, help="Soniyada (standart: 10).")
        parser.add_argument(
            "--retries", type=int, default=2, help="Vaqtinchalik xatoda qayta urinish (standart: 2)."
        )
        parser.add_argument("--helo", default="", help="SMTP EHLO uchun xost nomi.")
        parser.add_argument("--mail-from", default="", help="SMTP MAIL FROM manzili.")
        parser.add_argument(
            "--no-catch-all-check",
            action="store_true",
            help="Catch-all tekshiruvini o'tkazib yubor (tezroq, lekin 'risky' aniqlanmaydi).",
        )
        parser.add_argument(
            "--no-dedupe", action="store_true", help="Takrorlanganlarni ham qayta tekshir."
        )
        parser.add_argument(
            "--limit", type=int, default=0, help="Faqat birinchi N manzil (0 = hammasi)."
        )

    def handle(self, *args, **options):
        source = Path(options["input"])
        if not source.exists():
            raise CommandError(f"Fayl topilmadi: {source}")

        verifier = self._build(options)
        emails = check_io.read_emails(source, dedupe=not options["no_dedupe"])
        if options["limit"] > 0:
            emails = _take(emails, options["limit"])

        destination = options["output"]
        writer = check_io.ResultWriter(sys.stdout if destination == "-" else destination)
        progress = _Progress(self.stderr)

        try:
            stats = asyncio.run(
                self._run(
                    emails,
                    verifier,
                    writer,
                    concurrency=options["concurrency"],
                    on_progress=progress,
                )
            )
        except KeyboardInterrupt:
            progress.finish()
            self.stderr.write("\nTo'xtatildi — shu paytgacha yozilganlari faylda qoldi.")
            raise CommandError("foydalanuvchi to'xtatdi") from None
        finally:
            writer.close()

        progress.finish()
        check_io.write_summary(
            stats.as_dict(), total=stats.total, elapsed=stats.elapsed, stream=sys.stderr
        )
        if destination != "-":
            self.stderr.write(f"Natija: {destination}")

    @staticmethod
    async def _run(emails, verifier, writer, *, concurrency, on_progress):
        async with verifier:
            return await verify_all(
                emails,
                verifier,
                concurrency=concurrency,
                on_progress=on_progress,
                sink=writer.write,
            )

    def _build(self, options):
        kind = options["verifier"]
        if kind == "smtp":
            helo = options["helo"] or getattr(settings, "EMAILCHECK_HELO_HOSTNAME", "")
            mail_from = options["mail_from"] or getattr(settings, "EMAILCHECK_MAIL_FROM", "")
            if not helo or not mail_from:
                raise CommandError(
                    "SMTP uchun --helo va --mail-from kerak (yoki settings'da "
                    "EMAILCHECK_HELO_HOSTNAME / EMAILCHECK_MAIL_FROM). Ular HAQIQIY "
                    "va sizga tegishli bo'lishi shart: ko'p server yuboruvchi domenni "
                    "tekshiradi va mos kelmasa ulanishni uzadi."
                )
            return build_verifier(
                "smtp",
                helo_hostname=helo,
                mail_from=mail_from,
                resolver=MxResolver(timeout=options["timeout"]),
                throttle=DomainThrottle(
                    interval=options["per_domain_interval"],
                    concurrency=options["per_domain_concurrency"],
                ),
                timeout=options["timeout"],
                retries=options["retries"],
                detect_catch_all=not options["no_catch_all_check"],
            )

        api_key = options["api_key"] or getattr(settings, "EMAILCHECK_API_KEY", "")
        if not api_key:
            raise CommandError(f"{kind} uchun --api-key kerak (yoki settings.EMAILCHECK_API_KEY).")
        return build_verifier(
            kind, api_key=api_key, timeout=options["timeout"], retries=options["retries"]
        )


def _take(iterator, limit: int):
    for index, item in enumerate(iterator):
        if index >= limit:
            return
        yield item


class _Progress:
    """`stderr` ga bir qatorli progress yozadi.

    Yangilanish sekundiga bir marta: har natijada yozish 100 000 qatorli
    yurishda terminalni cho'ktiradi va tekshiruvdan ko'ra ko'proq vaqt
    oladi.
    """

    def __init__(self, stream, *, min_interval: float = 1.0) -> None:
        self._stream = stream
        self._min_interval = min_interval
        self._last = 0.0
        self._started = time.monotonic()
        self._dirty = False

    def __call__(self, done: int, total: int | None) -> None:
        now = time.monotonic()
        if now - self._last < self._min_interval:
            return
        self._last = now
        elapsed = now - self._started
        rate = done / elapsed if elapsed > 0 else 0.0
        suffix = f"/{total}" if total else ""
        self._stream.write(f"\rTekshirildi: {done}{suffix}  ({rate:.1f}/s)")
        self._stream.flush()
        self._dirty = True

    def finish(self) -> None:
        if self._dirty:
            self._stream.write("\n")
            self._stream.flush()
            self._dirty = False
