"""Abstract base models shared by every app. No concrete models live here."""

import uuid
from typing import Any, Self, cast

from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

HEX_COLOR = RegexValidator(r"^#[0-9A-F]{6}$", "Must be an uppercase #RRGGBB hex colour.")


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet[Any]):
    def alive(self) -> Self:
        return self.filter(deleted_at__isnull=True)

    def dead(self) -> Self:
        return self.filter(deleted_at__isnull=False)

    # Qaytish turi ATAYLAB `QuerySet.delete()` dan farq qiladi (u
    # `(soni, {model: soni})` beradi, bu esa `UPDATE` qatorlari sonini) —
    # shuning uchun `Any`: bu override tipni torroq qilmaydi, boshqa
    # ma'nodagi qiymat qaytaradi.
    def delete(self) -> Any:  # bulk soft delete
        return self.update(deleted_at=timezone.now())

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        return super().delete()


# `from_queryset` sinfni ISH VAQTIDA quradi, mypy esa dinamik asos sinfni
# tahlil qila olmaydi. Runtime xatti-harakati o'zgarmaydi; muqobili —
# menejerni qo'lda takrorlash, ya'ni bir xil kodni ikki joyda saqlash.
class AliveManager(models.Manager.from_queryset(SoftDeleteQuerySet)):  # type: ignore[misc]
    def get_queryset(self) -> SoftDeleteQuerySet:
        # `super()` dinamik asosdan keladi (yuqoridagi izoh), ya'ni mypy uchun
        # `Any`. `cast` faqat tipni aytadi — kod bir xil ishlaydi.
        queryset = cast(SoftDeleteQuerySet, super().get_queryset())
        return queryset.filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = AliveManager()  # default manager -> live rows only
    all_objects = models.Manager.from_queryset(SoftDeleteQuerySet)()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    # `Model.delete()` `(soni, {model: soni})` qaytaradi; soft delete esa
    # hech nima qaytarmaydi — bu qasddan qilingan farq, tip xatosi emas.
    def delete(self, using: Any = None, keep_parents: bool = False) -> None:  # type: ignore[override]
        self.deleted_at = timezone.now()
        # `updated_at` shu sinfda emas, `TimeStampedModel` da — konkret model
        # ikkalasidan ham meros oladi (`Task`, `Comment`, `Message`), lekin
        # mypy buni faqat shu abstrakt sinf doirasida ko'radi.
        self.save(update_fields=["deleted_at", "updated_at"])  # type: ignore[misc]

    def hard_delete(self, using: Any = None, keep_parents: bool = False) -> None:
        super().delete(using=using, keep_parents=keep_parents)


class PositionedModel(models.Model):
    """Fractional-index ordering. See docs/DATA_MODEL.md section 8."""

    position = models.CharField(max_length=64, db_index=True, db_collation="C")

    class Meta:
        abstract = True
