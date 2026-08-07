"""Channels consumers for the list and workspace channels (contract §15)."""

from collections import defaultdict

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.realtime import events

# In-process presence registry: {list_id: {user_id: {"count": n, "user": summary}}}
_PRESENCE: dict[str, dict[str, dict]] = defaultdict(dict)


@database_sync_to_async
def _list_access(user, list_id):
    """Return (allowed, user_summary). Guests cannot read private spaces."""
    from apps.accounts.serializers import UserSummarySerializer
    from apps.core.enums import WorkspaceRole
    from apps.workspaces.models import TaskList, WorkspaceMember

    task_list = (
        TaskList.objects.select_related("space").filter(pk=list_id).first()
    )
    if task_list is None:
        return False, None, None
    membership = WorkspaceMember.objects.filter(
        workspace_id=task_list.space.workspace_id, user=user
    ).first()
    if membership is None:
        return False, None, None
    if membership.role == WorkspaceRole.GUEST and task_list.space.is_private:
        return False, None, None
    return True, UserSummarySerializer(user).data, str(task_list.space.workspace_id)


@database_sync_to_async
def _workspace_access(user, workspace_id):
    from apps.workspaces.models import WorkspaceMember

    return WorkspaceMember.objects.filter(workspace_id=workspace_id, user=user).exists()


class BaseConsumer(AsyncJsonWebsocketConsumer):
    async def send_error_and_close(self, code, message):
        await self.accept()
        await self.send_json({"type": "error", "payload": {"code": code, "message": message}})
        await self.close()

    async def broadcast(self, message):
        await self.send_json(message["event"])


class ListConsumer(BaseConsumer):
    channel = "list"

    async def connect(self):
        self.list_id = self.scope["url_route"]["kwargs"]["list_id"]
        self.group = events.list_group(self.list_id)
        self.joined = False
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close()
            return
        allowed, summary, _ws_id = await _list_access(user, self.list_id)
        if not allowed:
            await self.send_error_and_close("permission_denied", "No access to this list.")
            return

        self.user_summary = summary
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.channel_layer.group_add(events.user_group(user.id), self.channel_name)
        await self.accept()
        self.joined = True
        await self.send_json(
            {
                "type": "connection.ack",
                "payload": {
                    "data": {"channel": f"list.{self.list_id}", "user_id": str(user.id)}
                },
            }
        )

        # presence
        entry = _PRESENCE[self.list_id].setdefault(str(user.id), {"count": 0, "user": summary})
        entry["count"] += 1
        if entry["count"] == 1:
            await self.channel_layer.group_send(
                self.group,
                {
                    "type": "broadcast",
                    "event": {"type": "presence.join", "payload": {"data": {"user": summary}}},
                },
            )
        users = [e["user"] for e in _PRESENCE[self.list_id].values()]
        await self.send_json({"type": "presence.sync", "payload": {"data": {"users": users}}})

    async def disconnect(self, code):
        if not getattr(self, "joined", False):
            return
        user = self.scope.get("user")
        await self.channel_layer.group_discard(self.group, self.channel_name)
        if user is not None and not user.is_anonymous:
            await self.channel_layer.group_discard(
                events.user_group(user.id), self.channel_name
            )
            entry = _PRESENCE[self.list_id].get(str(user.id))
            if entry:
                entry["count"] -= 1
                if entry["count"] <= 0:
                    _PRESENCE[self.list_id].pop(str(user.id), None)
                    await self.channel_layer.group_send(
                        self.group,
                        {
                            "type": "broadcast",
                            "event": {
                                "type": "presence.leave",
                                "payload": {"data": {"user": self.user_summary}},
                            },
                        },
                    )

    async def receive_json(self, content, **kwargs):
        # Closed client vocabulary: presence.ping / presence.typing; ignore the rest.
        if content.get("type") not in ("presence.ping", "presence.typing"):
            return


class WorkspaceConsumer(BaseConsumer):
    channel = "workspace"

    async def connect(self):
        self.workspace_id = self.scope["url_route"]["kwargs"]["workspace_id"]
        self.group = events.workspace_group(self.workspace_id)
        self.joined = False
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close()
            return
        if not await _workspace_access(user, self.workspace_id):
            await self.send_error_and_close("permission_denied", "Not a workspace member.")
            return
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.channel_layer.group_add(events.user_group(user.id), self.channel_name)
        await self.accept()
        self.joined = True
        await self.send_json(
            {
                "type": "connection.ack",
                "payload": {
                    "data": {
                        "channel": f"workspace.{self.workspace_id}",
                        "user_id": str(user.id),
                    }
                },
            }
        )

    async def disconnect(self, code):
        if not getattr(self, "joined", False):
            return
        user = self.scope.get("user")
        await self.channel_layer.group_discard(self.group, self.channel_name)
        if user is not None and not user.is_anonymous:
            await self.channel_layer.group_discard(
                events.user_group(user.id), self.channel_name
            )

    async def receive_json(self, content, **kwargs):
        return
