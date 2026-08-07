from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower

from apps.core.enums import PRIORITY_ORDER, ActivityVerb, Priority, WatcherSource
from apps.core.models import (
    HEX_COLOR,
    PositionedModel,
    SoftDeleteModel,
    TimeStampedModel,
    UUIDModel,
)


class Tag(UUIDModel, TimeStampedModel):
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="tags"
    )
    name = models.CharField(max_length=60)
    color = models.CharField(max_length=7, default="#7B68EE", validators=[HEX_COLOR])
    usage_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tags",
    )

    class Meta:
        db_table = "tags"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint("workspace", Lower("name"), name="uniq_tag_name_per_workspace"),
        ]
        indexes = [models.Index(Lower("name"), name="idx_tag_name_ci")]

    def __str__(self):
        return self.name


class Task(UUIDModel, TimeStampedModel, SoftDeleteModel, PositionedModel):
    list = models.ForeignKey(
        "workspaces.TaskList", on_delete=models.CASCADE, related_name="tasks"
    )
    status = models.ForeignKey(
        "workspaces.Status", on_delete=models.PROTECT, related_name="tasks"
    )

    title = models.CharField(max_length=500)
    description_html = models.TextField(blank=True, default="")
    description_json = models.JSONField(null=True, blank=True, default=None)

    priority = models.CharField(
        max_length=7, choices=Priority.choices, default=Priority.NONE, db_index=True
    )
    priority_order = models.PositiveSmallIntegerField(default=5, db_index=True, editable=False)

    due_date = models.DateTimeField(null=True, blank=True, db_index=True)
    start_date = models.DateTimeField(null=True, blank=True)
    time_estimate_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(60 * 24 * 365)],
    )

    archived = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    comment_count = models.PositiveIntegerField(default=0)

    assignees = models.ManyToManyField(
        "accounts.User",
        through="TaskAssignee",
        through_fields=("task", "user"),
        related_name="assigned_tasks",
        blank=True,
    )
    watchers = models.ManyToManyField(
        "accounts.User", through="TaskWatcher", related_name="watched_tasks", blank=True
    )
    tags = models.ManyToManyField("Tag", through="TaskTag", related_name="tasks", blank=True)

    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tasks",
    )
    updated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_tasks",
    )

    class Meta:
        db_table = "tasks"
        ordering = ["position", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["list", "status", "position"],
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_task_position_per_column",
            ),
            models.CheckConstraint(
                condition=models.Q(start_date__isnull=True)
                | models.Q(due_date__isnull=True)
                | models.Q(start_date__lte=models.F("due_date")),
                name="task_start_before_due",
            ),
        ]
        indexes = [
            models.Index(fields=["list", "status", "position"], name="idx_task_column_pos"),
            models.Index(fields=["list", "deleted_at", "archived"], name="idx_task_list_live"),
            models.Index(fields=["list", "updated_at"], name="idx_task_list_updated"),
            models.Index(fields=["due_date"], name="idx_task_due"),
            models.Index(fields=["priority_order"], name="idx_task_priority_order"),
            models.Index(fields=["created_by"], name="idx_task_creator"),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.priority_order = PRIORITY_ORDER[self.priority]
        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            fields = set(kwargs["update_fields"])
            if "priority" in fields:
                fields.add("priority_order")
            kwargs["update_fields"] = list(fields)
        super().save(*args, **kwargs)

    def clean(self):
        effective = self.list.effective_status_set
        if self.status.status_set_id != effective.id:
            raise ValidationError(
                {"status_id": "Status does not belong to this list's status set."}
            )
        if self.start_date and self.due_date and self.start_date > self.due_date:
            raise ValidationError({"start_date": "start_date must be on or before due_date."})

    @property
    def workspace_id(self):
        return self.list.space.workspace_id


class TaskAssignee(UUIDModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="task_assignees")
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="task_assignments"
    )
    assigned_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "task_assignees"
        ordering = ["assigned_at"]
        constraints = [
            models.UniqueConstraint(fields=["task", "user"], name="uniq_task_assignee"),
        ]
        indexes = [
            models.Index(fields=["user", "task"], name="idx_assignee_user_task"),
        ]


class TaskWatcher(UUIDModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="task_watchers")
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="task_watches"
    )
    source = models.CharField(
        max_length=14, choices=WatcherSource.choices, default=WatcherSource.MANUAL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "task_watchers"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["task", "user"], name="uniq_task_watcher"),
        ]
        indexes = [models.Index(fields=["user"], name="idx_watcher_user")]


class TaskActivity(UUIDModel, TimeStampedModel):
    """Immutable audit trail of what happened to a task, and when.

    Rows are written from apps.tasks.services only (never from views) and are
    read back through GET tasks/{id}/activity/. Never updated, never deleted
    except by the task's own cascade.
    """

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,  # history outlives the user
        null=True,
        blank=True,
        related_name="task_activities",
    )
    verb = models.CharField(max_length=16, choices=ActivityVerb.choices, db_index=True)
    from_value = models.CharField(max_length=255, null=True, blank=True)
    to_value = models.CharField(max_length=255, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "task_activities"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task", "-created_at"], name="idx_activity_task_recent"),
        ]

    def __str__(self):
        return f"{self.verb} @ {self.created_at:%Y-%m-%d %H:%M}"


class TaskTag(UUIDModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="task_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="task_tags")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "task_tags"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["task", "tag"], name="uniq_task_tag"),
        ]
        indexes = [models.Index(fields=["tag", "task"], name="idx_tasktag_tag_task")]
