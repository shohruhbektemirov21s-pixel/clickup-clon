"""Comment services — events emitted from here, never from views."""

import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.comments.models import Comment
from apps.core.enums import WatcherSource
from apps.realtime import events
from apps.tasks.services import add_watcher
from apps.workspaces.services import check_client_id


def _refresh_comment_count(task):
    task.comment_count = Comment.objects.filter(task=task).count()
    task.save(update_fields=["comment_count", "updated_at"])


def _refresh_reply_count(parent):
    parent.reply_count = Comment.objects.filter(parent=parent).count()
    parent.save(update_fields=["reply_count", "updated_at"])


@transaction.atomic
def create_comment(task, author, data, client_id=None) -> Comment:
    check_client_id(Comment, data.get("id"))
    parent = None
    parent_id = data.get("parent_id")
    if parent_id:
        parent = Comment.all_objects.filter(pk=parent_id).first()
        if parent is None or parent.task_id != task.id:
            raise ValidationError(
                {"parent_id": ["Parent comment must be on the same task."]}
            )
        if parent.parent_id is not None:
            raise ValidationError(
                {"parent_id": ["Comments can only be nested one level deep."]}
            )
    comment = Comment.objects.create(
        id=data.get("id") or uuid.uuid4(),
        task=task,
        parent=parent,
        author=author,
        body_html=data["body_html"],
        body_json=data.get("body_json"),
    )
    if parent is not None:
        _refresh_reply_count(parent)
    _refresh_comment_count(task)
    add_watcher(task, author, WatcherSource.AUTO_COMMENT)
    events.emit_comment_event("comment.created", comment, actor=author, client_id=client_id)
    return comment


@transaction.atomic
def edit_comment(comment, data, actor, client_id=None) -> Comment:
    comment.body_html = data["body_html"]
    comment.body_json = data.get("body_json")
    comment.is_edited = True
    comment.edited_at = timezone.now()
    comment.save(
        update_fields=["body_html", "body_json", "is_edited", "edited_at", "updated_at"]
    )
    events.emit_comment_event("comment.updated", comment, actor=actor, client_id=client_id)
    return comment


@transaction.atomic
def delete_comment(comment, actor, client_id=None):
    comment.delete()  # soft
    if comment.parent_id:
        parent = Comment.all_objects.filter(pk=comment.parent_id).first()
        if parent is not None:
            _refresh_reply_count(parent)
    _refresh_comment_count(comment.task)
    events.emit_comment_deleted(comment, actor=actor, client_id=client_id)
