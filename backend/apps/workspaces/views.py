import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone
from rest_framework import status as http
from rest_framework.exceptions import NotFound, PermissionDenied, Throttled, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.access import (
    bump_permissions_version,
    check_space_visible,
    effective_permissions,
    my_permissions,
    require_membership,
    require_membership_perm,
    require_space_perm,
    visible_spaces_q,
)
from apps.core.api import client_id_of, paginate, parse_bool
from apps.core.enums import AssignableRole, InvitationStatus, ROLE_RANK, WorkspaceRole
from apps.core.exceptions import ApiError, Conflict
from apps.core.permissions import (
    ALL_CODES,
    CATALOG_VERSION,
    PERMISSION_BY_CODE,
    grouped_catalog,
)
from apps.realtime import events
from apps.workspaces import services
from apps.workspaces.models import (
    Folder,
    Invitation,
    RolePermission,
    Space,
    SpaceMember,
    StatusSet,
    TaskList,
    Workspace,
    WorkspaceMember,
)
from apps.workspaces.serializers import (
    FolderSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    ListSerializer,
    MemberSerializer,
    ResetRolePermissionsSerializer,
    RolePermissionRowSerializer,
    RolePermissionUpdateSerializer,
    SpaceSerializer,
    StatusSetInputSerializer,
    StatusSetSerializer,
    WorkspaceSerializer,
)

# ---------------------------------------------------------------- resolvers


def _get_space(user, space_id, perm=None):
    """C.4 tartibi: resurs → a'zolik → ko'rinuvchanlik → ruxsat."""
    space = Space.objects.select_related("workspace").filter(pk=space_id).first()
    if space is None:
        raise NotFound()
    membership = require_membership(user, space.workspace_id)
    check_space_visible(membership, space)
    if perm is not None:
        require_space_perm(membership, space, perm)
    return space, membership


def _get_folder(user, folder_id, perm=None):
    folder = (
        Folder.objects.select_related("space", "space__workspace").filter(pk=folder_id).first()
    )
    if folder is None:
        raise NotFound()
    membership = require_membership(user, folder.space.workspace_id)
    check_space_visible(membership, folder.space)
    if perm is not None:
        require_space_perm(membership, folder.space, perm)
    return folder, membership


def get_list(user, list_id, perm=None):
    task_list = (
        TaskList.objects.select_related("space", "space__workspace", "folder")
        .filter(pk=list_id)
        .first()
    )
    if task_list is None:
        raise NotFound()
    membership = require_membership(user, task_list.space.workspace_id)
    check_space_visible(membership, task_list.space)
    if perm is not None:
        require_space_perm(membership, task_list.space, perm)
    return task_list, membership


def _validation_error(field, message):
    raise ValidationError({field: [message]})


# ---------------------------------------------------------------- workspaces


class WorkspaceListCreateView(APIView):
    def get(self, request):
        memberships = WorkspaceMember.objects.filter(user=request.user).select_related(
            "workspace"
        )
        roles = {str(m.workspace_id): m.role for m in memberships}
        workspaces = Workspace.objects.filter(id__in=roles.keys()).order_by("name")
        return paginate(
            request,
            workspaces,
            WorkspaceSerializer,
            context={"request": request, "roles": roles},
        )

    def post(self, request):
        serializer = WorkspaceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        workspace = services.bootstrap_workspace(
            request.user,
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
            color=serializer.validated_data.get("color"),
            workspace_id=request.data.get("id") or None,
        )
        data = WorkspaceSerializer(
            workspace, context={"request": request, "roles": {str(workspace.id): "owner"}}
        ).data
        return Response(data, status=http.HTTP_201_CREATED)


class WorkspaceDetailView(APIView):
    def get(self, request, workspace_id):
        membership = require_membership(request.user, workspace_id)
        data = WorkspaceSerializer(
            membership.workspace, context={"request": request, "membership": membership}
        ).data
        return Response(data)

    def patch(self, request, workspace_id):
        membership = require_membership_perm(request.user, workspace_id, "workspace.update")
        serializer = WorkspaceSerializer(
            membership.workspace,
            data=request.data,
            partial=True,
            context={"request": request, "membership": membership},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, workspace_id):
        membership = require_membership_perm(request.user, workspace_id, "workspace.delete")
        workspace = membership.workspace
        if request.data.get("confirm_name") != workspace.name:
            _validation_error("confirm_name", "confirm_name must exactly match the workspace name.")
        services.hard_delete_workspace(workspace)
        return Response(status=http.HTTP_204_NO_CONTENT)


class WorkspaceTreeView(APIView):
    def get(self, request, workspace_id):
        membership = require_membership(request.user, workspace_id)
        include_archived = parse_bool(request.query_params.get("archived"), False)
        archived_q = Q() if include_archived else Q(archived=False)

        spaces = (
            Space.objects.filter(workspace_id=workspace_id)
            .filter(visible_spaces_q(membership))
            .filter(archived_q)
            .order_by("position", "name")
            .prefetch_related("folders", "lists")
        )

        def list_node(task_list):
            return {
                "id": str(task_list.id),
                "name": task_list.name,
                "color": task_list.color,
                "folder_id": str(task_list.folder_id) if task_list.folder_id else None,
                "archived": task_list.archived,
                "position": task_list.position,
                "task_count": task_list.task_count,
                "open_task_count": task_list.open_task_count,
            }

        payload_spaces = []
        for space in spaces:
            folders = [f for f in space.folders.all() if include_archived or not f.archived]
            folders.sort(key=lambda f: (f.position, f.name))
            lists = [
                task_list
                for task_list in space.lists.all()
                if include_archived or not task_list.archived
            ]
            lists.sort(key=lambda x: (x.position, x.name))
            payload_spaces.append(
                {
                    "id": str(space.id),
                    "name": space.name,
                    "color": space.color,
                    "icon": space.icon,
                    "is_private": space.is_private,
                    "archived": space.archived,
                    "position": space.position,
                    "folders": [
                        {
                            "id": str(folder.id),
                            "name": folder.name,
                            "color": folder.color,
                            "archived": folder.archived,
                            "position": folder.position,
                            "lists": [
                                list_node(x) for x in lists if x.folder_id == folder.id
                            ],
                        }
                        for folder in folders
                    ],
                    "lists": [list_node(x) for x in lists if x.folder_id is None],
                }
            )
        workspace = membership.workspace
        return Response(
            {"id": str(workspace.id), "name": workspace.name, "spaces": payload_spaces}
        )


# ---------------------------------------------------------------- members


def _owner_count(workspace_id):
    return WorkspaceMember.objects.filter(
        workspace_id=workspace_id, role=WorkspaceRole.OWNER
    ).count()


def _remove_member(membership):
    """Delete a membership + their assignee/watcher rows in this workspace."""
    from apps.tasks.models import TaskAssignee, TaskWatcher

    workspace = membership.workspace
    TaskAssignee.objects.filter(
        user=membership.user, task__list__space__workspace=workspace
    ).delete()
    TaskWatcher.objects.filter(
        user=membership.user, task__list__space__workspace=workspace
    ).delete()
    # DESIGN_PERMISSIONS.md §B.4 invariant: SpaceMember never outlives the
    # WorkspaceMember it depends on.
    SpaceMember.objects.filter(
        user=membership.user, space__workspace=workspace
    ).delete()
    membership.delete()
    services.refresh_member_count(workspace)


ROSTER_RANK = Case(
    When(role=WorkspaceRole.OWNER, then=Value(0)),
    When(role=WorkspaceRole.ADMIN, then=Value(1)),
    When(role=WorkspaceRole.MEMBER, then=Value(2)),
    default=Value(3),
    output_field=IntegerField(),
)


class MemberListView(APIView):
    def get(self, request, workspace_id):
        require_membership_perm(request.user, workspace_id, "member.read")
        members = (
            WorkspaceMember.objects.filter(workspace_id=workspace_id)
            .select_related("user")
            .annotate(rank=ROSTER_RANK)
            .order_by("rank", "user__email")
        )
        return paginate(request, members, MemberSerializer)


class MemberDetailView(APIView):
    def _target(self, workspace_id, user_id):
        target = (
            WorkspaceMember.objects.select_related("user", "workspace")
            .filter(workspace_id=workspace_id, user_id=user_id)
            .first()
        )
        if target is None:
            raise NotFound()
        return target

    def patch(self, request, workspace_id, user_id):
        caller = require_membership_perm(request.user, workspace_id, "member.role_change")
        target = self._target(workspace_id, user_id)
        new_role = request.data.get("role")
        if new_role not in WorkspaceRole.values:
            _validation_error("role", "role must be one of owner, admin, member, guest.")

        # F-1 rank guard (ROLE_RANK, §B.7 whitelist): matritsa buni bypass qila
        # olmaydi — owner bo'lmagan chaqiruvchi owner'ga tega olmaydi va owner
        # rolini bera olmaydi.
        if ROLE_RANK[caller.role] < ROLE_RANK[WorkspaceRole.OWNER]:
            if target.role == WorkspaceRole.OWNER or new_role == WorkspaceRole.OWNER:
                raise PermissionDenied()
        # F-2 oxirgi owner invarianti — permission matritsasidan ustun.
        if (
            target.role == WorkspaceRole.OWNER
            and new_role != WorkspaceRole.OWNER
            and _owner_count(workspace_id) == 1
        ):
            raise Conflict("Cannot demote the last owner.")

        target.role = new_role
        target.save(update_fields=["role", "updated_at"])
        workspace = target.workspace
        if new_role == WorkspaceRole.OWNER:
            workspace.owner = target.user
            workspace.save(update_fields=["owner", "updated_at"])
        elif workspace.owner_id == target.user_id:
            other = (
                WorkspaceMember.objects.filter(
                    workspace_id=workspace_id, role=WorkspaceRole.OWNER
                )
                .exclude(user_id=target.user_id)
                .first()
            )
            if other is not None:
                workspace.owner = other.user
                workspace.save(update_fields=["owner", "updated_at"])
        return Response(MemberSerializer(target, context={"request": request}).data)

    def delete(self, request, workspace_id, user_id):
        caller = require_membership_perm(request.user, workspace_id, "member.remove")
        target = self._target(workspace_id, user_id)
        # F-1 rank guard (ROLE_RANK, §B.7 whitelist)
        if (
            ROLE_RANK[caller.role] < ROLE_RANK[WorkspaceRole.OWNER]
            and target.role == WorkspaceRole.OWNER
        ):
            raise PermissionDenied()
        # F-2 oxirgi owner invarianti — permission matritsasidan ustun.
        if target.role == WorkspaceRole.OWNER and _owner_count(workspace_id) == 1:
            raise Conflict("Cannot remove the last owner.")
        _remove_member(target)
        return Response(status=http.HTTP_204_NO_CONTENT)


class MemberLeaveView(APIView):
    def post(self, request, workspace_id):
        membership = require_membership(request.user, workspace_id)
        if membership.role == WorkspaceRole.OWNER and _owner_count(workspace_id) == 1:
            raise Conflict("The last owner cannot leave; transfer ownership first.")
        _remove_member(membership)
        return Response(status=http.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- invitations


def _effective_invite_status(invitation):
    if (
        invitation.status == InvitationStatus.PENDING
        and invitation.expires_at < timezone.now()
    ):
        return InvitationStatus.EXPIRED
    return invitation.status


class InvitationListCreateView(APIView):
    def get_throttles(self):
        # F-6: taklif yuborish rate-limit ostida; ro'yxatni o'qish emas.
        if self.request.method == "POST":
            self.throttle_scope = "invite"
            return [ScopedRateThrottle()]
        return []

    def get(self, request, workspace_id):
        require_membership_perm(request.user, workspace_id, "invitation.read")
        invitations = (
            Invitation.objects.filter(workspace_id=workspace_id)
            .select_related("invited_by")
            .order_by("-created_at")
        )
        return paginate(request, invitations, InvitationSerializer)

    def post(self, request, workspace_id):
        membership = require_membership_perm(request.user, workspace_id, "member.invite")
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = services.create_invitation(
            membership.workspace,
            request.user,
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
        )
        return Response(
            InvitationSerializer(invitation, context={"request": request}).data,
            status=http.HTTP_201_CREATED,
        )


def _get_invitation_for_admin(user, invitation_id):
    invitation = (
        Invitation.objects.select_related("workspace", "invited_by")
        .filter(pk=invitation_id)
        .first()
    )
    if invitation is None:
        raise NotFound()
    require_membership_perm(user, invitation.workspace_id, "invitation.manage")
    return invitation


class InvitationDetailView(APIView):
    def delete(self, request, invitation_id):
        invitation = _get_invitation_for_admin(request.user, invitation_id)
        if _effective_invite_status(invitation) != InvitationStatus.PENDING:
            raise Conflict("Only pending invitations can be revoked.")
        invitation.status = InvitationStatus.REVOKED
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["status", "revoked_at", "updated_at"])
        return Response(status=http.HTTP_204_NO_CONTENT)


class InvitationResendView(APIView):
    def post(self, request, invitation_id):
        invitation = _get_invitation_for_admin(request.user, invitation_id)
        if invitation.status != InvitationStatus.PENDING:
            raise Conflict("Only pending invitations can be resent.")
        if invitation.sent_count >= 5:
            raise Conflict("This invitation has reached its resend limit.")
        now = timezone.now()
        if invitation.last_sent_at and now - invitation.last_sent_at < timedelta(minutes=5):
            raise Throttled(detail="Resend is limited to once per 5 minutes.")
        from django.conf import settings

        invitation.sent_count += 1
        invitation.last_sent_at = now
        invitation.expires_at = now + timedelta(days=settings.INVITATION_TTL_DAYS)
        invitation.save(
            update_fields=["sent_count", "last_sent_at", "expires_at", "updated_at"]
        )
        return Response(InvitationSerializer(invitation, context={"request": request}).data)


class InvitationLookupView(APIView):
    permission_classes = [AllowAny]
    # F-6: public endpoint — token brute-force'ga qarshi IP bo'yicha throttle.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "invite_lookup"

    def get(self, request):
        token = request.query_params.get("token") or ""
        invitation = (
            Invitation.objects.select_related("workspace").filter(token=token).first()
        )
        if invitation is None or _effective_invite_status(invitation) != InvitationStatus.PENDING:
            raise NotFound()
        return Response(
            {
                "workspace_name": invitation.workspace.name,
                "email": invitation.email,
                "role": invitation.role,
                "expires_at": invitation.expires_at,
            }
        )


def _resolve_invitation_for_token(request):
    token = request.data.get("token") or ""
    invitation = Invitation.objects.select_related("workspace").filter(token=token).first()
    if invitation is None:
        raise NotFound()
    effective = _effective_invite_status(invitation)
    if effective in (InvitationStatus.ACCEPTED, InvitationStatus.REVOKED):
        raise Conflict("This invitation has already been used or revoked.")
    if effective == InvitationStatus.EXPIRED:
        raise NotFound()
    if request.user.email.lower() != invitation.email.lower():
        raise PermissionDenied()
    return invitation


class InvitationAcceptView(APIView):
    def post(self, request):
        invitation = _resolve_invitation_for_token(request)
        workspace = invitation.workspace
        if WorkspaceMember.objects.filter(workspace=workspace, user=request.user).exists():
            raise Conflict("You are already a member of this workspace.")
        member = WorkspaceMember.objects.create(
            workspace=workspace,
            user=request.user,
            role=invitation.role,
            invited_by=invitation.invited_by,
        )
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = timezone.now()
        invitation.accepted_by = request.user
        invitation.save(update_fields=["status", "accepted_at", "accepted_by", "updated_at"])
        services.refresh_member_count(workspace)
        return Response(
            {
                "workspace_id": str(workspace.id),
                "member": MemberSerializer(member, context={"request": request}).data,
            }
        )


class InvitationDeclineView(APIView):
    def post(self, request):
        invitation = _resolve_invitation_for_token(request)
        invitation.status = InvitationStatus.REVOKED
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["status", "revoked_at", "updated_at"])
        return Response(status=http.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- spaces


class SpaceListCreateView(APIView):
    def get(self, request, workspace_id):
        membership = require_membership(request.user, workspace_id)
        archived = parse_bool(request.query_params.get("archived"), False)
        spaces = (
            Space.objects.filter(workspace_id=workspace_id, archived=archived)
            .filter(visible_spaces_q(membership))
            .order_by("position", "name")
        )
        return paginate(request, spaces, SpaceSerializer)

    def post(self, request, workspace_id):
        membership = require_membership_perm(request.user, workspace_id, "space.create")
        serializer = SpaceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        space = services.create_space(
            membership.workspace,
            request.user,
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
            color=serializer.validated_data.get("color"),
            icon=serializer.validated_data.get("icon", ""),
            is_private=serializer.validated_data.get("is_private", False),
            space_id=request.data.get("id") or None,
        )
        return Response(
            SpaceSerializer(space, context={"request": request}).data,
            status=http.HTTP_201_CREATED,
        )


class SpaceDetailView(APIView):
    def get(self, request, space_id):
        space, _ = _get_space(request.user, space_id)
        return Response(SpaceSerializer(space, context={"request": request}).data)

    def patch(self, request, space_id):
        space, _ = _get_space(request.user, space_id, perm="space.update")
        serializer = SpaceSerializer(
            space, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        new_name = serializer.validated_data.get("name")
        if (
            new_name
            and Space.objects.filter(workspace_id=space.workspace_id, name__iexact=new_name)
            .exclude(pk=space.pk)
            .exists()
        ):
            raise Conflict("A space with this name already exists in the workspace.")
        if "archived" in request.data:
            serializer.validated_data["archived"] = parse_bool(request.data.get("archived"))
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, space_id):
        space, _ = _get_space(request.user, space_id, perm="space.delete")
        if request.data.get("confirm_name") != space.name:
            _validation_error("confirm_name", "confirm_name must exactly match the space name.")
        services.hard_delete_space(space)
        return Response(status=http.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- folders


class FolderListCreateView(APIView):
    def get(self, request, space_id):
        space, _ = _get_space(request.user, space_id)
        archived = parse_bool(request.query_params.get("archived"), False)
        folders = Folder.objects.filter(space=space, archived=archived).order_by(
            "position", "name"
        )
        return paginate(request, folders, FolderSerializer)

    def post(self, request, space_id):
        space, _ = _get_space(request.user, space_id, perm="folder.create")
        serializer = FolderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"].strip()
        if Folder.objects.filter(space=space, name__iexact=name).exists():
            raise Conflict("A folder with this name already exists in the space.")
        services.check_client_id(Folder, request.data.get("id") or None)
        folder = Folder.objects.create(
            id=request.data.get("id") or uuid.uuid4(),
            space=space,
            name=name,
            color=serializer.validated_data.get("color", "#7B68EE"),
            position=services.next_position(Folder.objects.filter(space=space)),
            created_by=request.user,
        )
        return Response(
            FolderSerializer(folder, context={"request": request}).data,
            status=http.HTTP_201_CREATED,
        )


class FolderDetailView(APIView):
    def get(self, request, folder_id):
        folder, _ = _get_folder(request.user, folder_id)
        return Response(FolderSerializer(folder, context={"request": request}).data)

    def patch(self, request, folder_id):
        folder, _ = _get_folder(request.user, folder_id, perm="folder.update")
        serializer = FolderSerializer(
            folder, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        new_name = serializer.validated_data.get("name")
        if (
            new_name
            and Folder.objects.filter(space_id=folder.space_id, name__iexact=new_name)
            .exclude(pk=folder.pk)
            .exists()
        ):
            raise Conflict("A folder with this name already exists in the space.")
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, folder_id):
        strategy = request.query_params.get("strategy", "cascade")
        if strategy not in ("cascade", "detach"):
            _validation_error("strategy", "strategy must be cascade or detach.")
        # §B.7: `?strategy=` ikki xil kodga bo'linadi.
        perm = "folder.delete_cascade" if strategy == "cascade" else "folder.delete"
        folder, _ = _get_folder(request.user, folder_id, perm=perm)
        if strategy == "detach":
            services.detach_folder_lists(folder)
            folder.delete()
        else:
            services.hard_delete_folder(folder)
        return Response(status=http.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- lists


class ListListCreateView(APIView):
    def get(self, request, space_id):
        space, _ = _get_space(request.user, space_id)
        archived = parse_bool(request.query_params.get("archived"), False)
        lists = TaskList.objects.filter(space=space, archived=archived)
        folder_param = request.query_params.get("folder")
        if folder_param == "none":
            lists = lists.filter(folder__isnull=True)
        elif folder_param:
            lists = lists.filter(folder_id=folder_param)
        return paginate(request, lists.order_by("position", "name"), ListSerializer)

    def post(self, request, space_id):
        space, _ = _get_space(request.user, space_id, perm="list.create")
        serializer = ListSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        folder = None
        folder_id = request.data.get("folder_id")
        if folder_id:
            folder = Folder.objects.filter(pk=folder_id, space=space).first()
            if folder is None:
                _validation_error("folder_id", "Folder must belong to the same space.")
        name = serializer.validated_data["name"].strip()
        scope = (
            TaskList.objects.filter(folder=folder)
            if folder
            else TaskList.objects.filter(space=space, folder__isnull=True)
        )
        if scope.filter(name__iexact=name).exists():
            raise Conflict("A list with this name already exists in this scope.")
        services.check_client_id(TaskList, request.data.get("id") or None)
        task_list = TaskList.objects.create(
            id=request.data.get("id") or uuid.uuid4(),
            space=space,
            folder=folder,
            name=name,
            description=serializer.validated_data.get("description", ""),
            color=serializer.validated_data.get("color", "#7B68EE"),
            default_view=serializer.validated_data.get("default_view", "list"),
            position=services.next_position(scope),
            created_by=request.user,
        )
        return Response(
            ListSerializer(task_list, context={"request": request}).data,
            status=http.HTTP_201_CREATED,
        )


class ListDetailView(APIView):
    def get(self, request, list_id):
        task_list, _ = get_list(request.user, list_id)
        return Response(ListSerializer(task_list, context={"request": request}).data)

    def patch(self, request, list_id):
        task_list, _ = get_list(request.user, list_id, perm="list.update")
        if "folder_id" in request.data:
            _validation_error("folder_id", "folder_id is not patchable; use move/.")
        serializer = ListSerializer(
            task_list, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        new_name = serializer.validated_data.get("name")
        if new_name:
            scope = (
                TaskList.objects.filter(folder_id=task_list.folder_id)
                if task_list.folder_id
                else TaskList.objects.filter(space_id=task_list.space_id, folder__isnull=True)
            )
            if scope.filter(name__iexact=new_name).exclude(pk=task_list.pk).exists():
                raise Conflict("A list with this name already exists in this scope.")
        serializer.save()
        events.emit_list_updated(task_list, actor=request.user, client_id=client_id_of(request))
        return Response(serializer.data)

    def delete(self, request, list_id):
        task_list, _ = get_list(request.user, list_id, perm="list.delete")
        services.hard_delete_list(task_list)
        return Response(status=http.HTTP_204_NO_CONTENT)


class ListMoveView(APIView):
    def patch(self, request, list_id):
        task_list, _ = get_list(request.user, list_id, perm="list.move")
        if "space_id" in request.data:
            _validation_error("space_id", "Lists can only move within their space.")
        if "folder_id" not in request.data:
            _validation_error("folder_id", "folder_id is required (may be null).")
        task_list = services.move_list(
            task_list,
            folder_id=request.data.get("folder_id"),
            before_id=request.data.get("before_id"),
            after_id=request.data.get("after_id"),
            actor=request.user,
            client_id=client_id_of(request),
        )
        return Response(ListSerializer(task_list, context={"request": request}).data)


# ---------------------------------------------------------------- status sets


class SpaceStatusSetView(APIView):
    def get(self, request, space_id):
        space, _ = _get_space(request.user, space_id)
        return Response(
            StatusSetSerializer(space.status_set, context={"request": request}).data
        )

    def put(self, request, space_id):
        space, _ = _get_space(request.user, space_id, perm="space.manage_statuses")
        serializer = StatusSetInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_set = services.replace_status_set(
            space=space,
            data=serializer.validated_data,
            actor=request.user,
            client_id=client_id_of(request),
        )
        return Response(StatusSetSerializer(status_set, context={"request": request}).data)


class ListStatusSetView(APIView):
    def get(self, request, list_id):
        task_list, _ = get_list(request.user, list_id)
        return Response(
            StatusSetSerializer(
                task_list.effective_status_set, context={"request": request}
            ).data
        )

    def put(self, request, list_id):
        task_list, _ = get_list(request.user, list_id, perm="list.manage_statuses")
        serializer = StatusSetInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_set = services.replace_status_set(
            task_list=task_list,
            data=serializer.validated_data,
            actor=request.user,
            client_id=client_id_of(request),
        )
        return Response(StatusSetSerializer(status_set, context={"request": request}).data)

    def delete(self, request, list_id):
        task_list, _ = get_list(request.user, list_id, perm="list.manage_statuses")
        status_set = services.remove_list_status_set(
            task_list,
            status_mapping=request.data.get("status_mapping") or {},
            actor=request.user,
            client_id=client_id_of(request),
        )
        return Response(StatusSetSerializer(status_set, context={"request": request}).data)


# ---------------------------------------------------------------- permissions
# docs/DESIGN_PERMISSIONS.md §D.1–D.5

MANAGE_PERMISSIONS = "workspace.manage_permissions"

#: Monotonlik zanjiri (AD-5): guest ⊆ member ⊆ admin ⊆ owner.
MONOTONIC_CHAIN = ("guest", "member", "admin")


def _validation_error_payload(details):
    raise ApiError(
        message="Request payload is invalid.",
        details=details,
        code="validation_error",
        status_code=http.HTTP_400_BAD_REQUEST,
    )


def _matrix_payload(workspace):
    """`GET`/`PUT`/`reset` uchun yagona javob shakli (D.2)."""
    effective = effective_permissions(workspace)
    roles = {
        # owner qulflangan va DB'da saqlanmaydi (AD-3)
        WorkspaceRole.OWNER.value: {"locked": True, "permissions": sorted(ALL_CODES)},
    }
    for role in AssignableRole.values:
        roles[role] = {"locked": False, "permissions": sorted(effective.get(role, frozenset()))}

    overrides = [
        row
        for row in RolePermission.objects.filter(workspace=workspace).order_by(
            "role", "permission"
        )
        if row.permission in PERMISSION_BY_CODE
        and row.allowed != (row.role in PERMISSION_BY_CODE[row.permission].defaults)
    ]
    return {
        "workspace_id": str(workspace.id),
        "version": workspace.permissions_version,
        "catalog_version": CATALOG_VERSION,
        "roles": roles,
        "overrides": RolePermissionRowSerializer(overrides, many=True).data,
    }


def _validate_role_changes(roles_payload):
    """F-8 whitelist: noma'lum kalit silent ignore EMAS, 400."""
    errors = {}
    changes = {}
    for role, entries in roles_payload.items():
        if role == WorkspaceRole.OWNER:
            errors["roles.owner"] = ["Owner ruxsatlarini o'zgartirib bo'lmaydi."]
            continue
        if role not in AssignableRole.values:
            errors[f"roles.{role}"] = ["Noma'lum rol."]
            continue
        if not isinstance(entries, dict):
            errors[f"roles.{role}"] = ["Obyekt kutilgan edi."]
            continue
        for code, allowed in entries.items():
            key = f"roles.{role}.{code}"
            definition = PERMISSION_BY_CODE.get(code)
            if definition is None or definition.deprecated:
                errors[key] = ["Noma'lum ruxsat kodi."]
                continue
            if not isinstance(allowed, bool):
                errors[key] = ["Qiymat true yoki false bo'lishi shart."]
                continue
            if definition.owner_only and allowed:
                errors[key] = ["Bu ruxsat faqat owner uchun."]
                continue
            changes[(role, code)] = allowed
    if errors:
        _validation_error_payload(errors)
    return changes


def _rank_guard(membership, target_roles):
    """F-1 (2-qavat): o'z roli yoki undan yuqorini o'zgartirib bo'lmaydi."""
    caller_rank = ROLE_RANK[membership.role]
    for role in sorted(target_roles, key=lambda r: -ROLE_RANK[r]):
        if ROLE_RANK[role] >= caller_rank:
            raise ApiError(
                message="You cannot change permissions for your own role or above.",
                details={"reason": "self_escalation", "role": role},
                code="permission_denied",
                status_code=http.HTTP_403_FORBIDDEN,
            )


def _check_monotonic(resulting):
    messages = []
    for lower, higher in zip(MONOTONIC_CHAIN, MONOTONIC_CHAIN[1:]):
        for code in sorted(resulting[lower] - resulting[higher]):
            messages.append(f"'{code}' {lower}'da yoqilgan, {higher}'da o'chirilgan.")
    if messages:
        _validation_error_payload({"monotonic": messages})


def _resulting_matrix(workspace, changes):
    effective = effective_permissions(workspace)
    resulting = {role: set(effective.get(role, frozenset())) for role in AssignableRole.values}
    for (role, code), allowed in changes.items():
        (resulting[role].add if allowed else resulting[role].discard)(code)
    return resulting


@transaction.atomic
def _write_matrix(workspace, changes, actor):
    """bulk_* ishlatiladi — signal chiqmaydi, version aynan bir marta oshadi."""
    existing = {
        (row.role, row.permission): row
        for row in RolePermission.objects.filter(workspace=workspace)
    }
    now = timezone.now()
    to_create, to_update = [], []
    for (role, code), allowed in changes.items():
        row = existing.get((role, code))
        if row is None:
            to_create.append(
                RolePermission(
                    workspace=workspace,
                    role=role,
                    permission=code,
                    allowed=allowed,
                    updated_by=actor,
                )
            )
        elif row.allowed != allowed:
            row.allowed = allowed
            row.updated_by = actor
            row.updated_at = now
            to_update.append(row)
    if to_create:
        RolePermission.objects.bulk_create(to_create, ignore_conflicts=True)
    if to_update:
        RolePermission.objects.bulk_update(to_update, ["allowed", "updated_by", "updated_at"])


class PermissionCatalogView(APIView):
    """`GET permissions/` — auth talab qilinadi, rol talab qilinmaydi, pagination yo'q."""

    def get(self, request):
        return Response({"catalog_version": CATALOG_VERSION, "groups": grouped_catalog()})


class RolePermissionMatrixView(APIView):
    def get(self, request, workspace_id):
        membership = require_membership_perm(request.user, workspace_id, MANAGE_PERMISSIONS)
        services.ensure_role_permissions(membership.workspace)  # §B.6 resolver fallback
        return Response(_matrix_payload(membership.workspace))

    def put(self, request, workspace_id):
        membership = require_membership_perm(request.user, workspace_id, MANAGE_PERMISSIONS)
        workspace = membership.workspace
        serializer = RolePermissionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        changes = _validate_role_changes(serializer.validated_data["roles"])
        _rank_guard(membership, {role for role, _ in changes})

        expected = serializer.validated_data["expected_version"]
        if workspace.permissions_version != expected:
            raise Conflict(
                "The permission matrix changed since you loaded it.",
                details={
                    "expected_version": expected,
                    "current_version": workspace.permissions_version,
                },
            )

        services.ensure_role_permissions(workspace)
        _check_monotonic(_resulting_matrix(workspace, changes))
        _write_matrix(workspace, changes, request.user)
        bump_permissions_version(workspace, actor=request.user)
        return Response(_matrix_payload(workspace))


class RolePermissionResetView(APIView):
    def post(self, request, workspace_id):
        membership = require_membership_perm(request.user, workspace_id, MANAGE_PERMISSIONS)
        workspace = membership.workspace
        serializer = ResetRolePermissionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data.get("role")
        roles = [role] if role else list(AssignableRole.values)
        _rank_guard(membership, set(roles))

        with transaction.atomic():
            RolePermission.objects.filter(workspace=workspace, role__in=roles).delete()
            services.ensure_role_permissions(workspace)
        bump_permissions_version(workspace, actor=request.user)
        return Response(_matrix_payload(workspace))


class MyPermissionsView(APIView):
    """`GET workspaces/{id}/my-permissions/` — har qanday a'zo (guest ham)."""

    def get(self, request, workspace_id):
        membership = require_membership(request.user, workspace_id)
        spaces = (
            SpaceMember.objects.filter(
                space__workspace_id=workspace_id, user_id=request.user.id
            )
            .order_by("space_id")
            .values_list("space_id", "access")
        )
        return Response(
            {
                "workspace_id": str(workspace_id),
                "role": membership.role,
                "version": membership.workspace.permissions_version,
                "permissions": sorted(my_permissions(membership)),
                "spaces": [
                    {"space_id": str(space_id), "access": access}
                    for space_id, access in spaces
                ],
            }
        )


# ---------------------------------------------------------------- search


class WorkspaceSearchView(APIView):
    def get(self, request, workspace_id):
        membership = require_membership(request.user, workspace_id)
        q = request.query_params.get("q")
        if q is None or q.strip() == "":
            _validation_error("q", "q is required.")
        q = q.strip()

        from apps.tasks.models import Task
        from apps.tasks.serializers import TaskSerializer

        results = []
        if len(q) >= 2:
            space_scope = Space.objects.filter(workspace_id=workspace_id).filter(
                visible_spaces_q(membership)
            )
            tasks = (
                Task.objects.filter(
                    list__space__in=space_scope,
                    archived=False,
                    list__archived=False,
                )
                .filter(Q(title__icontains=q) | Q(description_html__icontains=q))
                .select_related("status", "list", "created_by", "updated_by")
                .order_by("-updated_at")
            )
            lists = TaskList.objects.filter(
                space__in=space_scope, archived=False, name__icontains=q
            ).order_by("name")
            folders = Folder.objects.filter(
                space__in=space_scope, archived=False, name__icontains=q
            ).order_by("name")
            spaces = space_scope.filter(archived=False, name__icontains=q).order_by("name")

            ctx = {"request": request}
            results.extend(
                {"type": "task", "item": TaskSerializer(t, context=ctx).data} for t in tasks
            )
            results.extend(
                {"type": "list", "item": ListSerializer(x, context=ctx).data} for x in lists
            )
            results.extend(
                {"type": "folder", "item": FolderSerializer(f, context=ctx).data}
                for f in folders
            )
            results.extend(
                {"type": "space", "item": SpaceSerializer(s, context=ctx).data} for s in spaces
            )

        from config.pagination import StandardPagination

        paginator = StandardPagination()
        page = paginator.paginate_queryset(results, request)
        return paginator.get_paginated_response(page)
