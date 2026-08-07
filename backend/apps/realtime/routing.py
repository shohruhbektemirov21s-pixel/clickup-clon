from django.urls import re_path

from apps.realtime import consumers

UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

websocket_urlpatterns = [
    re_path(
        rf"^ws/list/(?P<list_id>{UUID})/$",
        consumers.ListConsumer.as_asgi(),
    ),
    re_path(
        rf"^ws/workspaces/(?P<workspace_id>{UUID})/$",
        consumers.WorkspaceConsumer.as_asgi(),
    ),
]
