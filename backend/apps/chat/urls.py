from django.urls import path

from apps.chat import views

urlpatterns = [
    path(
        "workspaces/<uuid:workspace_id>/chat/channels/",
        views.ConversationListView.as_view(),
        name="chat-channels",
    ),
    path(
        "workspaces/<uuid:workspace_id>/chat/direct/",
        views.DirectConversationView.as_view(),
        name="chat-direct",
    ),
    path(
        "chat/conversations/<uuid:conversation_id>/join/",
        views.JoinConversationView.as_view(),
        name="chat-join",
    ),
    path(
        "chat/conversations/<uuid:conversation_id>/messages/",
        views.MessageListView.as_view(),
        name="chat-messages",
    ),
]
