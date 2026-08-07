from rest_framework import status as http
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.comments import services
from apps.comments.models import Comment
from apps.comments.serializers import CommentInputSerializer, CommentSerializer
from apps.core.access import check_space_visible, require_membership
from apps.core.api import client_id_of, paginate
from apps.core.enums import WorkspaceRole
from apps.tasks.views import get_task


def _get_comment(user, comment_id):
    comment = (
        Comment.objects.select_related("task", "task__list", "task__list__space", "author")
        .filter(pk=comment_id)
        .first()
    )
    if comment is None:
        raise NotFound()
    membership = require_membership(user, comment.task.list.space.workspace_id)
    check_space_visible(membership, comment.task.list.space)
    return comment, membership


class TaskCommentsView(APIView):
    def get_throttles(self):
        if self.request.method == "POST":
            throttle = ScopedRateThrottle()
            self.throttle_scope = "comments"
            return [throttle]
        return []

    def get(self, request, task_id):
        task, _ = get_task(request.user, task_id)
        comments = (
            Comment.objects.filter(task=task)
            .select_related("author")
            .order_by("created_at")
        )
        return paginate(request, comments, CommentSerializer)

    def post(self, request, task_id):
        task, _ = get_task(request.user, task_id)  # any member incl. guest
        serializer = CommentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data["id"] = request.data.get("id") or None
        comment = services.create_comment(
            task, request.user, data, client_id=client_id_of(request)
        )
        return Response(
            CommentSerializer(comment, context={"request": request}).data,
            status=http.HTTP_201_CREATED,
        )


class CommentDetailView(APIView):
    def patch(self, request, comment_id):
        comment, _ = _get_comment(request.user, comment_id)
        if comment.author_id != request.user.id:
            raise PermissionDenied()  # admins may NOT edit others' comments
        serializer = CommentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = services.edit_comment(
            comment, serializer.validated_data, request.user, client_id=client_id_of(request)
        )
        return Response(CommentSerializer(comment, context={"request": request}).data)

    def delete(self, request, comment_id):
        comment, membership = _get_comment(request.user, comment_id)
        is_author = comment.author_id == request.user.id
        is_admin = membership.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
        if not (is_author or is_admin):
            raise PermissionDenied()
        services.delete_comment(comment, request.user, client_id=client_id_of(request))
        return Response(status=http.HTTP_204_NO_CONTENT)
