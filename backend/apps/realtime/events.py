"""Broadcast helpers — the ONLY place REST mutations turn into WebSocket frames.

Called from the service/serializer layer (never from views) so REST and
WebSocket payloads stay shape-identical. Frame format: docs/API_CONTRACT.md §15.2.

Group names: list.<list_id>, workspace.<workspace_id>, user.<user_id>.
"""

import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone


def list_group(list_id) -> str:
    return f"list.{list_id}"


def workspace_group(workspace_id) -> str:
    return f"workspace.{workspace_id}"


def user_group(user_id) -> str:
    return f"user.{user_id}"


def _ts() -> str:
    return timezone.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _send(group: str, event_type: str, payload: dict) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        group, {"type": "broadcast", "event": {"type": event_type, "payload": payload}}
    )


def _payload(*, list_id, workspace_id, data, actor=None, client_id=None, rebalanced=None):
    payload = {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "ts": _ts(),
        "list_id": str(list_id) if list_id else None,
        "workspace_id": str(workspace_id) if workspace_id else None,
        "actor": {
            "id": str(actor.id) if actor is not None else None,
            "client_id": client_id or None,
        },
        "data": data,
    }
    if rebalanced is not None:
        payload["rebalanced"] = rebalanced
    return payload


def emit_task_event(event_type, task, *, actor=None, client_id=None, rebalanced=None):
    """task.created / task.updated / task.moved — data is the full Task object."""
    from apps.tasks.serializers import TaskSerializer

    workspace_id = task.list.space.workspace_id
    payload = _payload(
        list_id=task.list_id,
        workspace_id=workspace_id,
        data=TaskSerializer(task).data,
        actor=actor,
        client_id=client_id,
        rebalanced=rebalanced if event_type == "task.moved" else None,
    )
    _send(list_group(task.list_id), event_type, payload)


def emit_task_deleted(task, *, actor=None, client_id=None):
    workspace_id = task.list.space.workspace_id
    payload = _payload(
        list_id=task.list_id,
        workspace_id=workspace_id,
        data={"id": str(task.id), "list_id": str(task.list_id)},
        actor=actor,
        client_id=client_id,
    )
    _send(list_group(task.list_id), "task.deleted", payload)


def emit_comment_event(event_type, comment, *, actor=None, client_id=None):
    """comment.created / comment.updated — data is the full Comment object."""
    from apps.comments.serializers import CommentSerializer

    task = comment.task
    payload = _payload(
        list_id=task.list_id,
        workspace_id=task.list.space.workspace_id,
        data=CommentSerializer(comment).data,
        actor=actor,
        client_id=client_id,
    )
    _send(list_group(task.list_id), event_type, payload)


def emit_comment_deleted(comment, *, actor=None, client_id=None):
    task = comment.task
    payload = _payload(
        list_id=task.list_id,
        workspace_id=task.list.space.workspace_id,
        data={"id": str(comment.id), "task_id": str(task.id)},
        actor=actor,
        client_id=client_id,
    )
    _send(list_group(task.list_id), "comment.deleted", payload)


def emit_list_updated(task_list, *, actor=None, client_id=None):
    """list.updated on the workspace channel (rename/recolor/archive/move/counts)."""
    from apps.workspaces.serializers import ListSerializer

    workspace_id = task_list.space.workspace_id
    payload = _payload(
        list_id=task_list.id,
        workspace_id=workspace_id,
        data=ListSerializer(task_list).data,
        actor=actor,
        client_id=client_id,
    )
    _send(workspace_group(workspace_id), "list.updated", payload)


def emit_presence(list_id, event_type, data):
    payload = _payload(list_id=list_id, workspace_id=None, data=data)
    _send(list_group(list_id), event_type, payload)
