"""Abstract base models shared by every app. No concrete models live here."""

import uuid

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


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):  # bulk soft delete
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()


class AliveManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = AliveManager()  # default manager -> live rows only
    all_objects = models.Manager.from_queryset(SoftDeleteQuerySet)()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)


class PositionedModel(models.Model):
    """Fractional-index ordering. See docs/DATA_MODEL.md section 8."""

    position = models.CharField(max_length=64, db_index=True, db_collation="C")

    class Meta:
        abstract = True
