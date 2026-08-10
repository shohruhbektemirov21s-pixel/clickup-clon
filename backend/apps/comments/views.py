from rest_framework import status as http
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.comments import services
from apps.comments.models import Comment
from apps.comments.serializers import CommentInputSerializer, CommentSerializer
from apps.core.access import check_space_visible, require_membership, require_space_perm
from apps.core.api import client_id_of, paginate
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
        task, membership = get_task(request.user, task_id)
        require_space_perm(membership, task.list.space, "comment.create")
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
        comment, membership = _get_comment(request.user, comment_id)
        # Muallif invarianti permission'dan USTUN: `comment.update_any` kodi
        # ataylab mavjud emas — hech kim, owner ham, boshqaning izohini
        # tahrirlay olmaydi (kontrakt §12).
        if comment.author_id != request.user.id:
            raise PermissionDenied()
        require_space_perm(membership, comment.task.list.space, "comment.update_own")
        serializer = CommentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = services.edit_comment(
            comment, serializer.validated_data, request.user, client_id=client_id_of(request)
        )
        return Response(CommentSerializer(comment, context={"request": request}).data)

    def delete(self, request, comment_id):
        comment, membership = _get_comment(request.user, comment_id)
        code = (
            "comment.delete_own"
            if comment.author_id == request.user.id
            else "comment.delete_any"
        )
        require_space_perm(membership, comment.task.list.space, code)
        services.delete_comment(comment, request.user, client_id=client_id_of(request))
        return Response(status=http.HTTP_204_NO_CONTENT)
