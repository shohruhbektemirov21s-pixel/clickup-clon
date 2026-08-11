from django.db import models


class WorkspaceRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
    GUEST = "guest", "Guest"


#: Kalitlar `TextChoices` a'zolari (ular `str` ning o'zi), qiymat — daraja.
#: Tip ATAYLAB `dict[str, int]`: chaqiruvchilar `membership.role` ni
#: (oddiy `CharField` qiymati) kalit sifatida beradi.
ROLE_RANK: dict[str, int] = {
    WorkspaceRole.OWNER: 4,
    WorkspaceRole.ADMIN: 3,
    WorkspaceRole.MEMBER: 2,
    WorkspaceRole.GUEST: 1,
}


class Profession(models.TextChoices):
    """Kasb roli — SOF PROFIL MA'LUMOTI, RUXSAT ROLI EMAS.

    XAVFSIZLIK (binding): `Profession` hech qanday ruxsatga ta'sir qilmaydi.
    Vakolat faqat `WorkspaceRole` + `RolePermission` matritsasi orqali
    hisoblanadi (`apps/core/access.py::has_perm`). Bu yerga yangi qiymat
    qo'shish hech kimga hech qanday huquq bermaydi va olmaydi — u faqat
    "PM loyihaga mos odamni topsin" uchun ko'rsatiladigan yorliq.
    Bo'sh qiymat ("") ruxsat etiladi = "ko'rsatilmagan".
    """

    PROJECT_MANAGER = "project_manager", "Loyiha menejeri"
    DEVELOPER = "developer", "Dasturchi"
    DESIGNER = "designer", "Dizayner"
    QA = "qa", "Tester"
    ANALYST = "analyst", "Analitik"
    MARKETING = "marketing", "Marketolog"
    OTHER = "other", "Boshqa"


class AssignableRole(models.TextChoices):
    """RolePermission jadvalida saqlanadigan rollar. owner YO'Q.

    docs/DESIGN_PERMISSIONS.md AD-3: owner ruxsatlari hech qachon DB'da
    saqlanmaydi — `has_perm()` short-circuit qiladi va DB'da
    `CheckConstraint(role != 'owner')` turadi.
    """

    ADMIN = "admin", "Admin"
    MEMBER = "member", "A'zo"
    GUEST = "guest", "Mehmon"


class SpaceAccess(models.TextChoices):
    """Bo'lim ichidagi lokal daraja — docs/DESIGN_PERMISSIONS.md §B.5."""

    VIEWER = "viewer", "Ko'ruvchi"  # faqat o'qish (eng past huquq g'olib)
    CONTRIBUTOR = "contributor", "Ishtirokchi"  # workspace roli bo'yicha yozish
    MANAGER = "manager", "Menejer (PM)"  # + lokal space.manage_members


class SpaceMemberSource(models.TextChoices):
    MANUAL = "manual", "Qo'lda"
    AUTO_CREATOR = "auto_creator", "Avto (yaratuvchi)"
    AUTO_ASSIGNEE = "auto_assignee", "Avto (biriktirilgan)"
    BACKFILL = "backfill", "Migratsiya"


class InvitationRole(models.TextChoices):  # owner is NOT invitable
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
    GUEST = "guest", "Guest"


class InvitationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REVOKED = "revoked", "Revoked"
    EXPIRED = "expired", "Expired"


class TaskStatus(models.TextChoices):
    """Vazifa holati — YOPIQ to'plam, kodda yashaydi (DB'da sozlanmaydi).

    Ikkinchi element (o'zbekcha yorliq) faqat Django admin uchun: API HECH
    QACHON `label` ni saqlamaydi va faqat kodni qaytaradi. Doska ustunlari
    ham shu ro'yxatdan quriladi, ya'ni ustun to'plami har bir ro'yxat uchun
    bir xil va serverdan keladi.
    """

    TODO = "todo", "Boshlanmagan"
    IN_PROGRESS = "in_progress", "Jarayonda"
    REVIEW = "review", "Tekshirilmoqda"
    DONE = "done", "Bajarildi"


#: Yopiq (bajarilgan) deb hisoblanadigan kodlar. `completed_at` shu to'plamga
#: kirganda o'rnatiladi, chiqqanda tozalanadi.
CLOSED_STATUSES = frozenset({TaskStatus.DONE})

#: Doskadagi ustunlar tartibi — `?group_by=status` javobi AYNAN shu tartibda,
#: doim to'rtta guruh qaytaradi (bo'sh bo'lsa ham).
STATUS_ORDER = [TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.DONE]

#: Kod → ro'yxatdagi o'rni. Tekis ro'yxat javobining sukut tartibi ham shu
#: bo'yicha (alifbo bo'yicha emas: "done" < "in_progress" < "review" < "todo"
#: doskaning teskarisi bo'lardi).
STATUS_RANK = {code: index for index, code in enumerate(STATUS_ORDER)}


class Priority(models.TextChoices):
    URGENT = "urgent", "Urgent"
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"
    NONE = "none", "No priority"


PRIORITY_ORDER = {
    Priority.URGENT: 1,
    Priority.HIGH: 2,
    Priority.MEDIUM: 3,
    Priority.LOW: 4,
    Priority.NONE: 5,
}


class WatcherSource(models.TextChoices):
    MANUAL = "manual", "Manual"
    AUTO_CREATOR = "auto_creator", "Auto (creator)"
    AUTO_ASSIGNEE = "auto_assignee", "Auto (assignee)"
    AUTO_COMMENT = "auto_comment", "Auto (commented)"


class ActivityVerb(models.TextChoices):
    """Task history vocabulary — closed set, see API_CONTRACT.md section 10.6."""

    CREATED = "created", "Created"
    STATUS_CHANGED = "status_changed", "Status changed"
    ASSIGNEE_ADDED = "assignee_added", "Assignee added"
    ASSIGNEE_REMOVED = "assignee_removed", "Assignee removed"
    PRIORITY_CHANGED = "priority_changed", "Priority changed"
    DUE_DATE_CHANGED = "due_date_changed", "Due date changed"
    RENAMED = "renamed", "Renamed"
    MOVED = "moved", "Moved"
    COMPLETED = "completed", "Completed"
    DELETED = "deleted", "Deleted"
    RESTORED = "restored", "Restored"
    # Biriktirma hodisalari — yozuv `apps.tasks.attachments` dan chiqadi
    # (servis qatlamiga tegmasdan). `attachment_removed` 18 belgi, shuning
    # uchun `TaskActivity.verb.max_length` 32 ga kengaytirilgan.
    ATTACHMENT_ADDED = "attachment_added", "Attachment added"
    ATTACHMENT_REMOVED = "attachment_removed", "Attachment removed"
