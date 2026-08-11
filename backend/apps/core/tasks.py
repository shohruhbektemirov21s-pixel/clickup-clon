"""Davriy fon vazifalari — saqlash muddati va o'sib boradigan jadvallar.

Bu yerdagi ikkala vazifa ham MAVJUD, hujjatlashtirilgan bo'shliqni yopadi:

* `purge_soft_deleted` — ADR 0003 (`docs/adr/0003-soft-delete.md`) "Oqibatlar"
  bo'limida ochiq yozilgan: `Task`/`Comment`/`Message` soft-delete qilinadi,
  lekin ularni **tozalaydigan joy yo'q**. Ya'ni o'chirilgan har bir vazifa,
  izoh va chat xabari bazada abadiy qoladi.
* `flush_expired_tokens` — `ROTATE_REFRESH_TOKENS` va
  `BLACKLIST_AFTER_ROTATION` yoqilgani uchun (`config/settings.py`)
  har bir `POST auth/refresh/` `OutstandingToken` + `BlacklistedToken`
  yozadi. Muddati o'tgan qatorlar hech qachon o'z-o'zidan o'chmaydi.

Nega `apps/core/`? Ikkala vazifa ham bitta ilovaga tegishli emas:
`purge_soft_deleted` uchta ilovaning modellarini kesib o'tadi. Modellar
`apps.get_model()` orqali ISH VAQTIDA olinadi — `apps.core` hech qaysi
yuqori qatlam ilovasini import qilmaydi va ADR'dagi qatlam tartibi buzilmaydi.

Vazifalar Celery'siz ham chaqirilishi mumkin: broker bo'sh bo'lganda
`CELERY_TASK_ALWAYS_EAGER` yoqiladi, ya'ni `.delay()` shu jarayonda ishlaydi.
Qo'lda ishga tushirish uchun `manage.py purge_soft_deleted` ham bor.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

#: `SoftDeleteModel` dan meros oladigan BARCHA modellar — ADR 0003 dagi
#: ro'yxat bilan bir xil tartibda. Yangi soft-delete model qo'shsangiz shu
#: yerga ham qo'shing, aks holda uning qatorlari abadiy qoladi.
#: `apps/core/tests/test_tasks.py` bu ro'yxatning to'liqligini tekshiradi.
SOFT_DELETE_MODELS: tuple[str, ...] = (
    "tasks.Task",
    "comments.Comment",
    "chat.Message",
)


def _batch_size(value: int | None) -> int:
    size = value if value is not None else getattr(settings, "PURGE_BATCH_SIZE", 500)
    return max(int(size), 1)


def _drop_attachment_files(task_ids: list[Any]) -> None:
    """Purge qilinayotgan vazifalarning biriktirma FAYLLARINI diskdan oladi.

    ADR 0003 aynan shu holatni "Salbiy oqibat" deb sanaydi: `TaskAttachment`
    `Task` ga FK orqali bog'langan, lekin `Task` soft-delete bo'lganda CASCADE
    ishga tushmaydi. Endi vazifa QATTIQ o'chganda CASCADE qatorni olib
    tashlaydi — ammo Django FileField'ning diskdagi faylini HECH QACHON
    o'chirmaydi. Bu yerda uni qo'lda olmasak, `media/` da egasiz fayllar
    to'planib qoladi.

    Fayllar `on_commit` da o'chiriladi: tranzaksiya qaytsa qator joyida
    qoladi va unga mos fayl ham diskda turishi SHART.
    """
    TaskAttachment = apps.get_model("tasks", "TaskAttachment")
    stored = [
        attachment.file
        for attachment in TaskAttachment.objects.filter(task_id__in=task_ids).only("file")
        if attachment.file
    ]
    if not stored:
        return

    def _delete_files() -> None:
        for handle in stored:
            try:
                handle.delete(save=False)
            except (OSError, ValueError):
                # Fayl allaqachon yo'q yoki saqlash qatlami javob bermadi —
                # bu tozalash ishini to'xtatish uchun sabab emas.
                logger.warning("purge: biriktirma faylini o'chirib bo'lmadi: %s", handle.name)

    transaction.on_commit(_delete_files)


def _purge_model(label: str, cutoff: datetime, batch_size: int) -> int:
    """Bitta modelning muddati o'tgan qatorlarini partiyalab QATTIQ o'chiradi."""
    model = apps.get_model(label)
    manager = getattr(model, "all_objects", None)
    if manager is None:  # pragma: no cover - ro'yxat testda tekshiriladi
        raise RuntimeError(f"{label} soft-delete model emas: `all_objects` yo'q.")

    removed = 0
    while True:
        # Chegara QAT'IY `<`: `deleted_at` aynan cutoff'ga teng bo'lgan qator
        # hali saqlash muddati ICHIDA hisoblanadi.
        ids = list(
            manager.filter(deleted_at__isnull=False, deleted_at__lt=cutoff)
            .order_by("deleted_at")
            .values_list("pk", flat=True)[:batch_size]
        )
        if not ids:
            break

        with transaction.atomic():
            if label == "tasks.Task":
                _drop_attachment_files(ids)
            # `hard_delete()` — `SoftDeleteQuerySet.delete()` soft o'chiradi,
            # ya'ni oddiy `.delete()` bu yerda cheksiz sikl bo'lardi.
            manager.filter(pk__in=ids).hard_delete()

        removed += len(ids)
        # Partiya to'lmadi -> boshqa nomzod yo'q, yana bir bo'sh so'rov shart emas.
        if len(ids) < batch_size:
            break

    return removed


# celery type stub'lari yo'q: `shared_task` mypy uchun tiplanmagan dekorator,
# shuning uchun u bezagan funksiyani ham tiplanmagan deb hisoblaydi.
@shared_task(name="core.purge_soft_deleted")  # type: ignore[untyped-decorator]
def purge_soft_deleted(
    retention_days: int | None = None, batch_size: int | None = None
) -> dict[str, int]:
    """Saqlash muddati o'tgan soft-delete qatorlarini butunlay o'chiradi.

    `retention_days` berilmasa `settings.SOFT_DELETE_RETENTION_DAYS` (30)
    ishlatiladi. Qiymat 0 yoki manfiy bo'lsa tozalash O'CHIRILADI va vazifa
    hech nimaga tegmasdan qaytadi — bu "hamma narsani hoziroq o'chir" degani
    EMAS, chunki shunday talqin bitta noto'g'ri env qiymati bilan butun
    o'chirilganlar tarixini yo'q qilardi.

    Qaytaradi: `{"<app>.<Model>": o'chirilgan_qatorlar_soni}`.
    """
    days = (
        retention_days
        if retention_days is not None
        else getattr(settings, "SOFT_DELETE_RETENTION_DAYS", 30)
    )
    if days <= 0:
        logger.info("purge_soft_deleted: saqlash muddati %s -> o'chirilgan, ish yo'q", days)
        return {label: 0 for label in SOFT_DELETE_MODELS}

    cutoff = timezone.now() - timedelta(days=days)
    size = _batch_size(batch_size)

    result = {label: _purge_model(label, cutoff, size) for label in SOFT_DELETE_MODELS}
    total = sum(result.values())
    if total:
        logger.info("purge_soft_deleted: %s qator o'chirildi (%s)", total, result)
    return result


@shared_task(name="core.flush_expired_tokens")  # type: ignore[untyped-decorator]
def flush_expired_tokens(batch_size: int | None = None) -> int:
    """Muddati o'tgan `OutstandingToken` qatorlarini o'chiradi.

    `BlacklistedToken` `OutstandingToken` ga FK bilan bog'langan, shuning
    uchun u CASCADE bilan birga ketadi. Muddati o'tgan token'ni qora
    ro'yxatda saqlashning ma'nosi yo'q: u allaqachon `exp` bo'yicha rad
    etiladi.

    Bu simplejwt'ning `manage.py flushexpiredtokens` buyrug'i bilan bir xil
    ishni qiladi, lekin partiyalab (o'sha buyruq bitta `DELETE` yuboradi va
    million qatorli jadvalda uzoq qulf ushlaydi) va o'chirilgan sonni
    qaytaradi.
    """
    OutstandingToken = apps.get_model("token_blacklist", "OutstandingToken")
    now = timezone.now()
    size = _batch_size(batch_size)

    removed = 0
    while True:
        ids = list(
            OutstandingToken.objects.filter(expires_at__lte=now)
            .order_by("expires_at")
            .values_list("pk", flat=True)[:size]
        )
        if not ids:
            break
        with transaction.atomic():
            OutstandingToken.objects.filter(pk__in=ids).delete()
        removed += len(ids)
        if len(ids) < size:
            break

    if removed:
        logger.info("flush_expired_tokens: %s ta muddati o'tgan token o'chirildi", removed)
    return removed
