"""Bildirishnomalar — bitta foydalanuvchiga qaratilgan xabar.

Model ataylab **yassi**: `GenericForeignKey` yo'q, o'rniga `url` maydonida
frontend yo'li (`/w/<ws>/…`) saqlanadi. Sabab — bildirishnoma o'zi
ko'rsatayotgan obyektdan uzoq yashaydi (vazifa o'chirilishi, a'zolik
tugashi mumkin), shuning uchun u **hodisaning nusxasi** bo'lishi kerak,
tirik obyektga havola emas: eski qator ham o'qiladigan bo'lib qoladi va
ro'yxatni chizish uchun N ta JOIN kerak bo'lmaydi.

Ko'rinuvchanlik: qator faqat `user` ning o'zi uchun. `workspace` shunchaki
filtr/kontekst — bildirishnomani o'qish ish maydoni a'zoligini talab
qilmaydi (a'zolikdan chiqarilgan odam ham "chiqarildingiz" xabarini
ko'rishi kerak).
"""

from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class NotificationKind(models.TextChoices):
    """Yopiq lug'at. Yangi tur qo'shish = shu yerdagi bitta qator.

    Frontend `kind` bo'yicha ikonka tanlaydi; noma'lum turni ham chiza
    olishi uchun `title`/`body` doim to'ldirilgan bo'ladi.
    """

    MEMBER_ADDED = "member_added", "Ish maydoniga qo'shildingiz"
    MEMBER_JOINED = "member_joined", "Jamoaga yangi a'zo qo'shildi"
    MEMBER_REMOVED = "member_removed", "Ish maydonidan chiqarildingiz"
    ROLE_CHANGED = "role_changed", "Rolingiz o'zgardi"
    INVITATION_ACCEPTED = "invitation_accepted", "Taklif qabul qilindi"
    TASK_ASSIGNED = "task_assigned", "Vazifa biriktirildi"


class Notification(UUIDModel, TimeStampedModel):
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    #: Kontekst va filtr. A'zolik tugaganda ham xabar qolishi uchun `SET_NULL`
    #: emas `CASCADE`: ish maydonining O'ZI o'chirilsa xabarning ma'nosi ham
    #: yo'qoladi, ammo a'zolikning tugashi ish maydonini o'chirmaydi.
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    #: Harakatni qilgan odam — o'chirilsa xabar anonim bo'lib qoladi.
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    kind = models.CharField(max_length=32, choices=NotificationKind.choices)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=400, blank=True, default="")
    #: Frontend'ning ILDIZGA NISBATAN yo'li ("/w/<id>/settings/members").
    #: Tashqi URL hech qachon yozilmaydi — klient uni `next/link` ga beradi.
    url = models.CharField(max_length=300, blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        verbose_name = "bildirishnoma"
        verbose_name_plural = "bildirishnomalar"
        indexes = [
            # Qo'ng'iroqchaning ikkala so'rovi ham shu indeksdan o'qiydi:
            # "oxirgi 20 ta" va "o'qilmaganlar soni".
            models.Index(fields=["user", "-created_at"], name="idx_notif_user_created"),
            models.Index(fields=["user", "read_at"], name="idx_notif_user_read"),
        ]

    def __str__(self):
        return f"{self.kind} → {self.user_id}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
