import uuid as uuid_mod

from rest_framework import status as http
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.access import check_space_visible, require_membership, require_role
from apps.core.api import client_id_of, paginate
from apps.core.enums import WorkspaceRole
from apps.core.exceptions import Conflict
from apps.tasks import services
from apps.tasks.filters import apply_ordering, apply_task_filters, include_deleted_requested
from apps.tasks.models import Tag, Task
from apps.tasks.serializers import TagSerializer, TaskInputSerializer, TaskSerializer
from apps.workspaces.models import Space
from apps.workspaces.views import get_list
from config.pagination import StandardPagination

TASK_SELECT = ("status", "list", "list__space", "created_by", "updated_by")
TASK_PREFETCH = ("task_assignees__user", "task_tags__tag", "task_watchers__user")


def get_task(user, task_id, *, include_deleted=False):
    manager = Task.all_objects if include_deleted else Task.objects
    task = (
        manager.select_related(*TASK_SELECT)
        .prefetch_related(*TASK_PREFETCH)
        .filter(pk=task_id)
        .first()
    )
    if task is None:
        raise NotFound()
    membership = require_membership(user, task.list.space.workspace_id)
    check_space_visible(membership, task.list.space)
    return task, membership


def require_task_editor(task, membership):
    """member+ may edit any task; guests only tasks they are assigned to."""
    if membership.role == WorkspaceRole.GUEST:
        if not task.task_assignees.filter(user_id=membership.user_id).exists():
            raise PermissionDenied()
    else:
        require_role(membership, "member")


class ListTasksView(APIView):
    def get(self, request, list_id):
        task_list, membership = get_list(request.user, list_id)
        include_deleted = include_deleted_requested(request, membership)
        manager = Task.all_objects if include_deleted else Task.objects
        qs = (
            manager.filter(list=task_list)
            .select_related(*TASK_SELECT)
            .prefetch_related(*TASK_PREFETCH)
        )
        qs = apply_task_filters(qs, request, membership)

        if request.query_params.get("group_by") == "status":
            return self._grouped(request, task_list, qs)

        qs = apply_ordering(qs, request, default=("status__order", "position", "created_at"))
        return paginate(request, qs, TaskSerializer)

    def _grouped(self, request, task_list, qs):
        paginator = StandardPagination()
        page_size = paginator.get_page_size(request)
        groups = []
        statuses = task_list.effective_status_set.statuses.order_by("order")
        for status in statuses:
            column = apply_ordering(
                qs.filter(status=status), request, default=("position", "created_at")
            )
            groups.append(
                {
                    "status_id": str(status.id),
                    "count": column.count(),
                    "results": TaskSerializer(
                        column[:page_size], many=True, context={"request": request}
                    ).data,
                }
            )
        return Response({"group_by": "status", "groups": groups})

    def post(self, request, list_id):
        task_list, membership = get_list(request.user, list_id, min_role="member")
        serializer = TaskInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data["id"] = request.data.get("id") or None
        task = services.create_task(
            task_list, data, request.user, client_id=client_id_of(request)
        )
        task, _ = get_task(request.user, task.id)
        return Response(
            TaskSerializer(task, context={"request": request}).data,
            status=http.HTTP_201_CREATED,
        )


class TaskDetailView(APIView):
    def get(self, request, task_id):
        task, _ = get_task(request.user, task_id)
        return Response(TaskSerializer(task, context={"request": request}).data)

    def patch(self, request, task_id):
        if "deleted_at" in request.data:
            return self._restore(request, task_id)
        task, membership = get_task(request.user, task_id)
        require_task_editor(task, membership)
        serializer = TaskInputSerializer(data=request.data, partial=True)
        serializer.task_instance = task
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        task = services.update_task(task, data, request.user, client_id=client_id_of(request))
        task, _ = get_task(request.user, task.id)
        return Response(TaskSerializer(task, context={"request": request}).data)

    def _restore(self, request, task_id):
        """PATCH {"deleted_at": null} — the only accepted write of deleted_at (admin+)."""
        if request.data.get("deleted_at") is not None or len(request.data) != 1:
            raise ValidationError(
                {"deleted_at": ["Only {\"deleted_at\": null} (restore) is accepted."]}
            )
        task, membership = get_task(request.user, task_id, include_deleted=True)
        require_role(membership, "admin")
        if not task.is_deleted:
            raise Conflict("Task is not deleted.")
        from datetime import timedelta

        from django.utils import timezone

        if task.deleted_at < timezone.now() - timedelta(days=30):
            raise Conflict("Tasks can only be restored within 30 days.")
        task = services.restore_task(task, request.user, client_id=client_id_of(request))
        task, _ = get_task(request.user, task.id)
        return Response(TaskSerializer(task, context={"request": request}).data)

    def delete(self, request, task_id):
        task, membership = get_task(request.user, task_id)
        require_role(membership, "member")
        services.soft_delete_task(task, request.user, client_id=client_id_of(request))
        return Response(status=http.HTTP_204_NO_CONTENT)


class TaskMoveView(APIView):
    def patch(self, request, task_id):
        task, membership = get_task(request.user, task_id)
        require_task_editor(task, membership)
        list_id = request.data.get("list_id")
        if not list_id:
            raise ValidationError({"list_id": ["list_id is required."]})
        # destination list must be readable by the caller too
        get_list(request.user, list_id)
        task, rebalanced = services.move_task(
            task,
            list_id=list_id,
            status_id=request.data.get("status_id"),
            before_id=request.data.get("before_id"),
            after_id=request.data.get("after_id"),
            actor=request.user,
            client_id=client_id_of(request),
        )
        task, _ = get_task(request.user, task.id)
        data = TaskSerializer(task, context={"request": request}).data
        data["rebalanced"] = rebalanced
        return Response(data)


class TaskWatchView(APIView):
    def post(self, request, task_id):
        task, _ = get_task(request.user, task_id)
        created = services.watch_task(task, request.user)
        task, _ = get_task(request.user, task_id)
        return Response(
            TaskSerializer(task, context={"request": request}).data,
            status=http.HTTP_201_CREATED if created else http.HTTP_200_OK,
        )

    def delete(self, request, task_id):
        task, _ = get_task(request.user, task_id)
        services.unwatch_task(task, request.user)
        return Response(status=http.HTTP_204_NO_CONTENT)


class WorkspaceTasksView(APIView):
    def get(self, request, workspace_id):
        membership = require_membership(request.user, workspace_id)
        include_deleted = include_deleted_requested(request, membership)
        manager = Task.all_objects if include_deleted else Task.objects

        spaces = Space.objects.filter(workspace_id=workspace_id)
        if membership.role == WorkspaceRole.GUEST:
            spaces = spaces.filter(is_private=False)
        qs = (
            manager.filter(list__space__in=spaces)
            .select_related(*TASK_SELECT)
            .prefetch_related(*TASK_PREFETCH)
        )
        qs = apply_task_filters(qs, request, membership)
        qs = apply_ordering(qs, request, default=("position", "created_at"))
        return paginate(request, qs, TaskSerializer)


class WorkspaceTagsView(APIView):
    def get(self, request, workspace_id):
        require_membership(request.user, workspace_id)
        ordering = request.query_params.get("ordering", "name")
        if ordering not in ("name", "-name", "usage_count", "-usage_count"):
            raise ValidationError({"ordering": ["Unsupported ordering field."]})
        tags = Tag.objects.filter(workspace_id=workspace_id).order_by(ordering, "name")
        return paginate(request, tags, TagSerializer)

    def post(self, request, workspace_id):
        membership = require_membership(request.user, workspace_id, min_role="member")
        serializer = TagSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"].strip()
        if Tag.objects.filter(workspace_id=workspace_id, name__iexact=name).exists():
            raise Conflict("A tag with this name already exists in the workspace.")
        from apps.workspaces.services import check_client_id

        check_client_id(Tag, request.data.get("id") or None)
        tag = Tag.objects.create(
            id=request.data.get("id") or uuid_mod.uuid4(),
            workspace=membership.workspace,
            name=name,
            color=serializer.validated_data.get("color", "#7B68EE"),
            created_by=request.user,
        )
        return Response(
            TagSerializer(tag, context={"request": request}).data,
            status=http.HTTP_201_CREATED,
        )


class TagDetailView(APIView):
    def _get(self, user, tag_id, min_role="member"):
        tag = Tag.objects.select_related("workspace").filter(pk=tag_id).first()
        if tag is None:
            raise NotFound()
        require_membership(user, tag.workspace_id, min_role=min_role)
        return tag

    def patch(self, request, tag_id):
        tag = self._get(request.user, tag_id)
        serializer = TagSerializer(
            tag, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        new_name = serializer.validated_data.get("name")
        if (
            new_name
            and Tag.objects.filter(workspace_id=tag.workspace_id, name__iexact=new_name)
            .exclude(pk=tag.pk)
            .exists()
        ):
            raise Conflict("A tag with this name already exists in the workspace.")
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, tag_id):
        tag = self._get(request.user, tag_id)
        tag.delete()
        return Response(status=http.HTTP_204_NO_CONTENT)
