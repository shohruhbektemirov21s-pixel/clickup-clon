from django.urls import path

from apps.tasks import attachments, views

urlpatterns = [
    path(
        "tasks/<uuid:task_id>/attachments/",
        attachments.TaskAttachmentsView.as_view(),
        name="task-attachments",
    ),
    path(
        "attachments/<uuid:attachment_id>/",
        attachments.AttachmentDetailView.as_view(),
        name="attachment-detail",
    ),
    path(
        "attachments/<uuid:attachment_id>/download/",
        attachments.AttachmentDownloadView.as_view(),
        name="attachment-download",
    ),
    path("lists/<uuid:list_id>/tasks/", views.ListTasksView.as_view(), name="list-tasks"),
    path("tasks/<uuid:task_id>/", views.TaskDetailView.as_view(), name="task-detail"),
    path("tasks/<uuid:task_id>/move/", views.TaskMoveView.as_view(), name="task-move"),
    path("tasks/<uuid:task_id>/watch/", views.TaskWatchView.as_view(), name="task-watch"),
    path(
        "tasks/<uuid:task_id>/activity/",
        views.TaskActivityView.as_view(),
        name="task-activity",
    ),
    path(
        "workspaces/<uuid:workspace_id>/tasks/",
        views.WorkspaceTasksView.as_view(),
        name="workspace-tasks",
    ),
    path(
        "workspaces/<uuid:workspace_id>/tags/",
        views.WorkspaceTagsView.as_view(),
        name="workspace-tags",
    ),
    path("tags/<uuid:tag_id>/", views.TagDetailView.as_view(), name="tag-detail"),
]
