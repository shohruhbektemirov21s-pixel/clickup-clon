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
