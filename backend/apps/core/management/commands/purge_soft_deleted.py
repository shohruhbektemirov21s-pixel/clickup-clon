"""Saqlash muddati o'tgan soft-delete qatorlarini tozalaydi (ADR 0003).

    ../.venv/Scripts/python.exe manage.py purge_soft_deleted             # faqat sanaydi
    ../.venv/Scripts/python.exe manage.py purge_soft_deleted --yes       # o'chiradi
    ../.venv/Scripts/python.exe manage.py purge_soft_deleted --days 90 --yes

**Standart holat — quruq yurish (dry run)**, `purge_demo` bilan bir xil
qoida bo'yicha: nima o'chishini ko'rsatadi va bazaga tegmaydi. Bu buyruq
`core.purge_soft_deleted` Celery vazifasining AYNAN o'sha kodini chaqiradi —
mantiq ikki joyda takrorlanmaydi. Ya'ni broker/beat yo'q bo'lgan o'rnatmada
ham tozalashni cron yoki qo'l bilan bajarish mumkin.
"""

from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.tasks import SOFT_DELETE_MODELS, purge_soft_deleted


class Command(BaseCommand):
    help = "Saqlash muddati o'tgan soft-delete qatorlarini butunlay o'chiradi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Saqlash muddati (kun). Standart — SOFT_DELETE_RETENTION_DAYS.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Haqiqatan o'chiradi. Bu bayroqsiz faqat sanaladi.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days is None:
            days = getattr(settings, "SOFT_DELETE_RETENTION_DAYS", 30)

        if days <= 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Saqlash muddati {days} kun — tozalash o'chirilgan, hech nima qilinmadi."
                )
            )
            return

        cutoff = timezone.now() - timedelta(days=days)
        self.stdout.write(f"Chegara: {cutoff.isoformat()} (saqlash muddati {days} kun)")

        if not options["yes"]:
            total = 0
            for label in SOFT_DELETE_MODELS:
                model = apps.get_model(label)
                count = model.all_objects.filter(
                    deleted_at__isnull=False, deleted_at__lt=cutoff
                ).count()
                total += count
                self.stdout.write(f"  {label}: {count}")
            self.stdout.write(
                self.style.WARNING(
                    f"Quruq yurish — {total} qator o'chirilishi kerak edi. "
                    "Haqiqatan o'chirish uchun --yes qo'shing."
                )
            )
            return

        result = purge_soft_deleted(retention_days=days)
        for label, count in result.items():
            self.stdout.write(f"  {label}: {count}")
        self.stdout.write(self.style.SUCCESS(f"Jami {sum(result.values())} qator o'chirildi."))
