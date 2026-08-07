from django.urls import path

from apps.workspaces import views

urlpatterns = [
    # workspaces
    path("workspaces/", views.WorkspaceListCreateView.as_view(), name="workspace-list"),
    path(
        "workspaces/<uuid:workspace_id>/",
        views.WorkspaceDetailView.as_view(),
        name="workspace-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/tree/",
        views.WorkspaceTreeView.as_view(),
        name="workspace-tree",
    ),
    # members
    path(
        "workspaces/<uuid:workspace_id>/members/",
        views.MemberListView.as_view(),
        name="member-list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/members/leave/",
        views.MemberLeaveView.as_view(),
        name="member-leave",
    ),
    path(
        "workspaces/<uuid:workspace_id>/members/<uuid:user_id>/",
        views.MemberDetailView.as_view(),
        name="member-detail",
    ),
    # invitations
    path(
        "workspaces/<uuid:workspace_id>/invitations/",
        views.InvitationListCreateView.as_view(),
        name="invitation-list",
    ),
    path("invitations/lookup/", views.InvitationLookupView.as_view(), name="invitation-lookup"),
    path("invitations/accept/", views.InvitationAcceptView.as_view(), name="invitation-accept"),
    path(
        "invitations/decline/", views.InvitationDeclineView.as_view(), name="invitation-decline"
    ),
    path(
        "invitations/<uuid:invitation_id>/",
        views.InvitationDetailView.as_view(),
        name="invitation-detail",
    ),
    path(
        "invitations/<uuid:invitation_id>/resend/",
        views.InvitationResendView.as_view(),
        name="invitation-resend",
    ),
    # spaces
    path(
        "workspaces/<uuid:workspace_id>/spaces/",
        views.SpaceListCreateView.as_view(),
        name="space-list",
    ),
    path("spaces/<uuid:space_id>/", views.SpaceDetailView.as_view(), name="space-detail"),
    path(
        "spaces/<uuid:space_id>/status-set/",
        views.SpaceStatusSetView.as_view(),
        name="space-status-set",
    ),
    # folders
    path(
        "spaces/<uuid:space_id>/folders/",
        views.FolderListCreateView.as_view(),
        name="folder-list",
    ),
    path("folders/<uuid:folder_id>/", views.FolderDetailView.as_view(), name="folder-detail"),
    # lists
    path("spaces/<uuid:space_id>/lists/", views.ListListCreateView.as_view(), name="list-list"),
    path("lists/<uuid:list_id>/", views.ListDetailView.as_view(), name="list-detail"),
    path("lists/<uuid:list_id>/move/", views.ListMoveView.as_view(), name="list-move"),
    path(
        "lists/<uuid:list_id>/status-set/",
        views.ListStatusSetView.as_view(),
        name="list-status-set",
    ),
    # search
    path(
        "workspaces/<uuid:workspace_id>/search/",
        views.WorkspaceSearchView.as_view(),
        name="workspace-search",
    ),
]
