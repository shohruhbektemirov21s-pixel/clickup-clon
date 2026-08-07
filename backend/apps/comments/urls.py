from django.urls import path

from apps.comments import views

urlpatterns = [
    path(
        "tasks/<uuid:task_id>/comments/",
        views.TaskCommentsView.as_view(),
        name="task-comments",
    ),
    path(
        "comments/<uuid:comment_id>/",
        views.CommentDetailView.as_view(),
        name="comment-detail",
    ),
]
