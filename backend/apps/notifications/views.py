"""Bildirishnoma endpointlari — docs/API_CONTRACT.md §19.

Barcha so'rovlar `request.user` bilan **qattiq** chegaralangan: queryset hech
qachon `user` filtrisiz qurilmaydi, shuning uchun begona bildirishnoma na
ro'yxatda, na o'qilgan deb belgilashda ko'rinadi (begona `id` → 404, 403
emas: mavjudligini oshkor qilmaymiz).
"""

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status as http
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api import paginate, parse_bool
from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer
from apps.notifications.services import unread_count


def _own_queryset(request):
    rows = Notification.objects.filter(user=request.user).select_related(
        "actor", "workspace"
    )
    workspace_id = request.query_params.get("workspace")
    if workspace_id:
        rows = rows.filter(workspace_id=workspace_id)
    if parse_bool(request.query_params.get("unread")):
        rows = rows.filter(read_at__isnull=True)
    return rows


#: Sxema uchun yagona javob shakli. `drf-spectacular` APIView'dan serializer'ni
#: taxmin qila olmaydi (§9 — `api/openapi.json` shartnomasi), shuning uchun har
#: bir endpoint javobini ANIQ e'lon qiladi. Annotatsiya yo'q endpoint sxemada
#: umuman ko'rinmaydi, ya'ni klient uni shartnomadan o'qiy olmaydi.
COUNT_RESPONSE = inline_serializer(
    name="NotificationUnreadCount", fields={"count": serializers.IntegerField()}
)
UPDATED_RESPONSE = inline_serializer(
    name="NotificationReadAll", fields={"updated": serializers.IntegerField()}
)


@extend_schema(
    summary="Bildirishnomalar ro'yxati",
    parameters=[
        OpenApiParameter("workspace", str, description="Ish maydoni bo'yicha filtr."),
        OpenApiParameter("unread", bool, description="Faqat o'qilmaganlar."),
    ],
    responses=NotificationSerializer(many=True),
)
class NotificationListView(APIView):
    """`GET notifications/?workspace=&unread=&page_size=` — yangi birinchi."""

    def get(self, request):
        return paginate(request, _own_queryset(request), NotificationSerializer)


@extend_schema(
    summary="O'qilmaganlar soni",
    parameters=[OpenApiParameter("workspace", str)],
    responses=COUNT_RESPONSE,
)
class NotificationUnreadCountView(APIView):
    """`GET notifications/unread-count/?workspace=` — qo'ng'iroqcha nishoni.

    Alohida endpoint: nishon har bir `notification.created` freymidan keyin
    yangilanadi, ro'yxatning o'zi esa faqat menyu ochilganda kerak.
    """

    def get(self, request):
        return Response(
            {"count": unread_count(request.user, request.query_params.get("workspace"))}
        )


@extend_schema(summary="Bittasini o'qilgan deb belgilash", request=None, responses=NotificationSerializer)
class NotificationReadView(APIView):
    """`POST notifications/{id}/read/` — idempotent, allaqachon o'qilgan bo'lsa ham 200."""

    def post(self, request, notification_id):
        notification = (
            Notification.objects.select_related("actor", "workspace")
            .filter(pk=notification_id, user=request.user)
            .first()
        )
        if notification is None:
            raise NotFound()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at", "updated_at"])
        return Response(
            NotificationSerializer(notification, context={"request": request}).data
        )


@extend_schema(summary="Hammasini o'qilgan deb belgilash", request=None, responses=UPDATED_RESPONSE)
class NotificationReadAllView(APIView):
    """`POST notifications/read-all/` — `?workspace=` bilan bitta ish maydoni."""

    def post(self, request):
        rows = Notification.objects.filter(user=request.user, read_at__isnull=True)
        workspace_id = request.data.get("workspace") or request.query_params.get(
            "workspace"
        )
        if workspace_id:
            rows = rows.filter(workspace_id=workspace_id)
        updated = rows.update(read_at=timezone.now(), updated_at=timezone.now())
        return Response({"updated": updated}, status=http.HTTP_200_OK)
