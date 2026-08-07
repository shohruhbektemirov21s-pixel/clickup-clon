from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel, UUIDModel


class Comment(UUIDModel, TimeStampedModel, SoftDeleteModel):
    task = models.ForeignKey("tasks.Task", on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    author = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="comments"
    )

    body_html = models.TextField()
    body_json = models.JSONField(null=True, blank=True, default=None)

    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    reply_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "comments"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["task", "deleted_at", "created_at"], name="idx_comment_task_live"
            ),
            models.Index(fields=["parent", "created_at"], name="idx_comment_parent"),
            models.Index(fields=["author"], name="idx_comment_author"),
        ]

    def clean(self):
        if self.parent_id:
            if self.parent.parent_id is not None:
                raise ValidationError(
                    {"parent_id": "Comments can only be nested one level deep."}
                )
            if self.parent.task_id != self.task_id:
                raise ValidationError(
                    {"parent_id": "Parent comment belongs to a different task."}
                )
