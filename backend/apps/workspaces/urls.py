from django.urls import path

from apps.workspaces import space_members, views

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
        "workspaces/<uuid:workspace_id>/user-search/",
        views.WorkspaceUserSearchView.as_view(),
        name="workspace-user-search",
    ),
    path(
        "workspaces/<uuid:workspace_id>/members/leave/",
        views.MemberLeaveView.as_view(),
        name="member-leave",
    ),
    path(
        "workspaces/<uuid:workspace_id>/members/<uuid:user_id>/profile/",
        views.MemberProfileView.as_view(),
        name="member-profile",
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
    # space members (docs/DESIGN_PERMISSIONS.md D.6) — `bulk/` `<uuid:user_id>/`
    # dan OLDIN kelishi shart, aks holda u hech qachon mos kelmaydi.
    path(
        "spaces/<uuid:space_id>/members/",
        space_members.SpaceMemberListCreateView.as_view(),
        name="space-member-list",
    ),
    path(
        "spaces/<uuid:space_id>/members/bulk/",
        space_members.SpaceMemberBulkView.as_view(),
        name="space-member-bulk",
    ),
    path(
        "spaces/<uuid:space_id>/members/<uuid:user_id>/",
        space_members.SpaceMemberDetailView.as_view(),
        name="space-member-detail",
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
    # permissions (docs/DESIGN_PERMISSIONS.md D.1-D.5)
    path("permissions/", views.PermissionCatalogView.as_view(), name="permission-catalog"),
    path(
        "workspaces/<uuid:workspace_id>/role-permissions/",
        views.RolePermissionMatrixView.as_view(),
        name="role-permissions",
    ),
    path(
        "workspaces/<uuid:workspace_id>/role-permissions/reset/",
        views.RolePermissionResetView.as_view(),
        name="role-permissions-reset",
    ),
    path(
        "workspaces/<uuid:workspace_id>/my-permissions/",
        views.MyPermissionsView.as_view(),
        name="my-permissions",
    ),
    # search
    path(
        "workspaces/<uuid:workspace_id>/search/",
        views.WorkspaceSearchView.as_view(),
        name="workspace-search",
    ),
]
