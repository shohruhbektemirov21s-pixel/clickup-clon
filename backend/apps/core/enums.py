from django.db import models


class WorkspaceRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
    GUEST = "guest", "Guest"


ROLE_RANK = {
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


class StatusType(models.TextChoices):
    OPEN = "open", "Not started"
    ACTIVE = "active", "Active"
    CLOSED = "closed", "Closed"


class Priority(models.TextChoices):
    URGENT = "urgent", "Urgent"
    HIGH = "high", "High"
    NORMAL = "normal", "Normal"
    LOW = "low", "Low"
    NONE = "none", "No priority"


PRIORITY_ORDER = {
    Priority.URGENT: 1,
    Priority.HIGH: 2,
    Priority.NORMAL: 3,
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
