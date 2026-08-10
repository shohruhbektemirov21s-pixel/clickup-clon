"""Broadcast helpers — the ONLY place REST mutations turn into WebSocket frames.

Called from the service/serializer layer (never from views) so REST and
WebSocket payloads stay shape-identical. Frame format: docs/API_CONTRACT.md §15.2.

Group names: ``list.<list_id>``, ``space.<space_id>``, ``workspace.<workspace_id>``,
``user.<user_id>``.

**Why a `space.<id>` group exists (AppSec — private-space leak).**
A frame is serialised once and fanned out to every channel in the group, so the
group itself is the authorisation boundary. ``workspace.<id>`` used to carry
`task.*` and `list.updated`, and *every* workspace member joins that group —
including a guest who gets a `404` for the very same list over REST. Content
from a private space therefore reached people who cannot read it.

The rule is now: **a frame only ever goes to a group whose members are known to
be allowed to see it.**

    list.<list_id>        task.* / comment.* / attachment.* / presence.*
                          (the list handshake already checks read access)
    space.<space_id>      the same task.* frames plus `list.updated`, for
                          sockets that are not scoped to a single list
    workspace.<ws_id>     ONLY genuinely workspace-wide frames (`permission.updated`)
    user.<user_id>        `access.revoked` — private, single recipient

``WorkspaceConsumer`` joins exactly the ``space.<id>`` groups that
``apps.core.access.visible_spaces_q()`` returns for that membership, so the WS
and REST answers to "can you see this space?" come from one predicate.

**Why every embedded email is nulled (AppSec O-1).**
`API_CONTRACT.md` §1 marks "a guest never sees another user's email" as
BINDING, and `UserSummarySerializer` enforces it from the caller's membership.
A broadcast has no caller: one payload is serialised once and delivered to
recipients with different authority, so per-recipient masking is impossible
here. `_mask()` therefore nulls `email` in every embedded `UserSummary` of
every frame — the same call the team already made for presence
(`consumers.PRESENCE_FIELDS`). Clients read emails from
`workspaces/{id}/members/`, which *is* per-caller masked. The scrub lives in
`_payload()`, so a new emitter cannot forget it.
"""

import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.utils import timezone

#: Broadcast freymidan olib tashlanadigan maydonlar. Qiymat `null` bo'ladi,
#: kalit qoladi: aynan shu mehmon REST'da ko'radigan shakl (`email: null`),
#: ya'ni `payload.data` §15.2 talab qilganidek REST bilan bir xil qoladi.
BROADCAST_MASKED_FIELDS = frozenset({"email"})


def list_group(list_id) -> str:
    return f"list.{list_id}"


def space_group(space_id) -> str:
    return f"space.{space_id}"


def workspace_group(workspace_id) -> str:
    return f"workspace.{workspace_id}"


def user_group(user_id) -> str:
    return f"user.{user_id}"


def _ts() -> str:
    return timezone.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _mask(value):
    """Recursively null every masked field in a serialised payload.

    Deliberately structural rather than a list of known nesting paths: a new
    nested `UserSummary` (a new watcher-like relation, a new activity actor)
    is covered the day it is added instead of the day someone remembers.
    """
    if isinstance(value, dict):
        return {
            key: (None if key in BROADCAST_MASKED_FIELDS else _mask(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_mask(item) for item in value]
    return value


def public_base_url() -> str:
    """Scheme+host the API is reachable at, or `""` when it is not configured.

    REST builds absolute URLs from the live request (`build_absolute_uri`); a
    broadcast has no request, so the base has to be configured. Set
    ``PUBLIC_BASE_URL`` (e.g. ``https://api.example.com``) in settings to make
    broadcast URLs byte-identical to REST ones. ``CSRF_TRUSTED_ORIGINS[0]`` is
    used as a fallback because it is already "the API's public origin". With
    neither set (dev / tests) URLs stay root-relative — still resolvable by a
    browser against the API origin, and documented here rather than accidental.
    """
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").strip()
    if not base:
        origins = getattr(settings, "CSRF_TRUSTED_ORIGINS", None) or []
        base = origins[0] if origins else ""
    return base.rstrip("/")


def absolute_url(path):
    """Root-relative path → absolute URL when a public base is configured."""
    if not isinstance(path, str) or not path.startswith("/"):
        return path
    return f"{public_base_url()}{path}"


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
        # Bitta joyda maskalanadi — yangi emitter uni unuta olmaydi.
        "data": _mask(data),
    }
    if rebalanced is not None:
        payload["rebalanced"] = rebalanced
    return payload


def emit_task_event(event_type, task, *, actor=None, client_id=None, rebalanced=None):
    """task.created / task.updated / task.moved — data is the full Task object."""
    from apps.tasks.serializers import TaskSerializer

    space_id = task.list.space_id
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
    # The space channel carries the same frame so views that are not scoped to
    # one list — the dashboard's "my tasks" and team counters — stay live
    # without opening a socket per list. It is the SPACE and not the workspace
    # because the workspace group contains members who cannot read this space.
    _send(space_group(space_id), event_type, payload)


def emit_task_deleted(task, *, actor=None, client_id=None):
    space_id = task.list.space_id
    workspace_id = task.list.space.workspace_id
    payload = _payload(
        list_id=task.list_id,
        workspace_id=workspace_id,
        data={"id": str(task.id), "list_id": str(task.list_id)},
        actor=actor,
        client_id=client_id,
    )
    _send(list_group(task.list_id), "task.deleted", payload)
    _send(space_group(space_id), "task.deleted", payload)


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


def emit_attachment_added(attachment, *, actor=None, client_id=None):
    """attachment.added — data is the full TaskAttachment object (§10.7)."""
    from apps.tasks.serializers import TaskAttachmentSerializer

    task = attachment.task
    data = dict(TaskAttachmentSerializer(attachment).data)
    # `get_download_url` needs `request` to build an absolute URL and a
    # broadcast has none, so it would otherwise emit a relative URL where REST
    # emits an absolute one — §15.2 requires the two to be shape-identical.
    data["download_url"] = absolute_url(data.get("download_url"))
    payload = _payload(
        list_id=task.list_id,
        workspace_id=task.list.space.workspace_id,
        data=data,
        actor=actor,
        client_id=client_id,
    )
    _send(list_group(task.list_id), "attachment.added", payload)


def emit_attachment_removed(attachment, *, actor=None, client_id=None):
    """attachment.removed — data is `{"id", "task_id"}` (row is already gone)."""
    task = attachment.task
    payload = _payload(
        list_id=task.list_id,
        workspace_id=task.list.space.workspace_id,
        data={"id": str(attachment.id), "task_id": str(task.id)},
        actor=actor,
        client_id=client_id,
    )
    _send(list_group(task.list_id), "attachment.removed", payload)


def emit_list_updated(task_list, *, actor=None, client_id=None):
    """list.updated for the sidebar (rename/recolor/archive/move/counts).

    Space-scoped, not workspace-scoped: the list's *name* alone discloses the
    contents of a private space to anyone holding a workspace socket.
    """
    from apps.workspaces.serializers import ListSerializer

    payload = _payload(
        list_id=task_list.id,
        workspace_id=task_list.space.workspace_id,
        data=ListSerializer(task_list).data,
        actor=actor,
        client_id=client_id,
    )
    _send(space_group(task_list.space_id), "list.updated", payload)


def emit_permissions_updated(workspace, *, actor=None, client_id=None):
    """permission.updated on the workspace channel (DESIGN_PERMISSIONS.md D.10).

    Genuinely workspace-wide (it carries no space content, only a version
    counter), so this is one of the few frames the workspace group still
    carries. Receiving it also makes every open socket re-evaluate its own
    scope — see `BaseConsumer.resync_scope`.
    """
    payload = _payload(
        list_id=None,
        workspace_id=workspace.id,
        data={
            "workspace_id": str(workspace.id),
            "version": workspace.permissions_version,
        },
        actor=actor,
        client_id=client_id,
    )
    _send(workspace_group(workspace.id), "permission.updated", payload)


def emit_access_revoked(user_id, *, workspace_id, space_id=None):
    """access.revoked on the private user channel (DESIGN_PERMISSIONS.md D.10)."""
    payload = _payload(
        list_id=None,
        workspace_id=workspace_id,
        data={
            "workspace_id": str(workspace_id),
            "space_id": str(space_id) if space_id else None,
        },
    )
    _send(user_group(user_id), "access.revoked", payload)


def emit_presence(list_id, event_type, data):
    payload = _payload(list_id=list_id, workspace_id=None, data=data)
    _send(list_group(list_id), event_type, payload)
