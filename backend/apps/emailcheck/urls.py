from django.urls import path

from apps.emailcheck.views import CheckEmailView

urlpatterns = [
    path(
        "workspaces/<uuid:workspace_id>/check-email/",
        CheckEmailView.as_view(),
        name="workspace-check-email",
    ),
]
