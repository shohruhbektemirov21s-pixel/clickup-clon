"""Orfan (egasiz) biriktirma fayllarini topadi va o'chiradi.

NEGA KERAK
----------
`TaskAttachment.file` — bu diskdagi faylga havola, lekin **cascade
o'chirish faylni o'chirmaydi**. Vazifa / ro'yxat / bo'lim / workspace
o'chirilganda `TaskAttachment` qatorlari `ON DELETE CASCADE` bilan yo'q
bo'ladi, `Model.delete()` esa chaqirilmaydi (queryset cascade) — natijada
`MEDIA_ROOT/attachments/` da hech kimga tegishli bo'lmagan fayllar yig'ilib
qoladi. `DELETE attachments/{id}/` yo'li (apps.tasks.services) faylni
tozalaydi, cascade esa yo'q.

XAVFSIZLIK
----------
Bu buyruq **standart holatda hech narsani o'chirmaydi** (`--dry-run`).
O'chirish faqat aniq `--delete` bilan bo'ladi va faqat `--older-than-days`
(standart 7 kun) dan eski fayllarga tegadi: hozirgina yuklangan, lekin
tranzaksiyasi hali yopilmagan fayl DB'da ko'rinmasligi mumkin — uni
o'chirib yuborish ma'lumot yo'qotish bo'lardi.

MISOLLAR
--------
    python manage.py prune_attachments                     # faqat ko'rsatadi
    python manage.py prune_attachments --older-than-days 30
    python manage.py prune_attachments --delete            # haqiqatan o'chiradi
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.tasks.models import TaskAttachment

#: `TaskAttachment.file.upload_to` shu papkadan boshlanadi.
ATTACHMENT_DIR = "attachments"


def human_size(num_bytes: int) -> str:
    """Baytni odam o'qiydigan ko'rinishga o'tkazadi (1.5 MB)."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"  # pragma: no cover - yuqoridagi sikl qamrab oladi


class Command(BaseCommand):
    help = (
        "MEDIA_ROOT/attachments/ dagi, DB'da qatori qolmagan fayllarni topadi. "
        "Standart rejim — dry-run; o'chirish uchun --delete."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Topilgan orfan fayllarni HAQIQATAN o'chiradi.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Faqat ko'rsatadi (standart holat; --delete ni bekor qiladi).",
        )
        parser.add_argument(
            "--older-than-days",
            type=int,
            default=7,
            metavar="N",
            help=(
                "Faqat N kundan eski fayllar ko'rib chiqiladi (standart 7). "
                "Yaqinda yuklangan faylni tranzaksiya yopilmasdan o'chirmaslik uchun."
            ),
        )

    def handle(self, *args, **options):
        days = options["older_than_days"]
        if days < 0:
            raise CommandError("--older-than-days manfiy bo'lishi mumkin emas.")
        # Xavfsiz standart: --delete berilmasa YOKI --dry-run berilsa — quruq yurish.
        dry_run = options["dry_run"] or not options["delete"]

        media_root = Path(settings.MEDIA_ROOT)
        root = media_root / ATTACHMENT_DIR
        if not root.is_dir():
            self.stdout.write(
                self.style.WARNING(f"Papka topilmadi: {root} — tekshiradigan fayl yo'q.")
            )
            return

        # DB'dagi barcha yo'llar (storage'ga nisbatan, `attachments/2026/08/x.pdf`).
        known = {
            name.replace("\\", "/")
            for name in TaskAttachment.objects.values_list("file", flat=True)
            if name
        }

        cutoff = time.time() - days * 86400
        orphans: list[tuple[Path, int]] = []
        scanned = 0
        skipped_fresh = 0

        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                path = Path(dirpath) / filename
                scanned += 1
                relative = path.relative_to(media_root).as_posix()
                if relative in known:
                    continue
                try:
                    stat = path.stat()
                except OSError:  # boshqa jarayon o'chirib yubordi
                    continue
                if stat.st_mtime > cutoff:
                    skipped_fresh += 1
                    continue
                orphans.append((path, stat.st_size))

        total_bytes = sum(size for _p, size in orphans)

        self.stdout.write(f"Papka:        {root}")
        self.stdout.write(f"Ko'rildi:     {scanned} ta fayl")
        self.stdout.write(f"DB'da bor:    {len(known)} ta yozuv")
        if skipped_fresh:
            self.stdout.write(
                f"O'tkazildi:   {skipped_fresh} ta fayl {days} kundan yangi (tegilmadi)"
            )

        if not orphans:
            self.stdout.write(self.style.SUCCESS("Orfan fayl topilmadi — hammasi joyida."))
            return

        for path, size in orphans:
            self.stdout.write(f"  • {path.relative_to(media_root).as_posix()}  ({human_size(size)})")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY-RUN: {len(orphans)} ta orfan fayl topildi, "
                    f"{human_size(total_bytes)} joy band. Hech narsa o'chirilmadi — "
                    "o'chirish uchun --delete bilan qayta ishga tushiring."
                )
            )
            return

        deleted = 0
        freed = 0
        failed = 0
        for path, size in orphans:
            try:
                path.unlink()
            except OSError as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f"  ! {path}: {exc}"))
                continue
            deleted += 1
            freed += size

        self._prune_empty_dirs(root)

        self.stdout.write(
            self.style.SUCCESS(
                f"O'chirildi: {deleted} ta fayl, {human_size(freed)} joy bo'shatildi."
            )
        )
        if failed:
            self.stdout.write(
                self.style.ERROR(f"{failed} ta faylni o'chirib bo'lmadi (yuqoriga qarang).")
            )

    def _prune_empty_dirs(self, root: Path) -> None:
        """Fayllar ketgach qolgan bo'sh `YYYY/MM` papkalarini tozalaydi."""
        for dirpath, _dirnames, _filenames in os.walk(root, topdown=False):
            directory = Path(dirpath)
            if directory == root:
                continue
            try:
                next(directory.iterdir())
            except StopIteration:
                try:
                    directory.rmdir()
                except OSError:
                    pass
            except OSError:
                pass
