"""Bo'lim a'zolari API — docs/DESIGN_PERMISSIONS.md §D.6 (PM biriktiruvi).

Foydalanuvchi talabi: *"prayek menenjiri loyihaga mos userlarni tanlasin"*.
Shu besh endpoint bo'lim menejeriga (yoki `space.manage_members` ruxsatiga ega
workspace roliga) o'z bo'limiga odam qo'shish, darajasini o'zgartirish va olib
tashlash imkonini beradi.

**Ruxsat.** Yozish amallari `require_space_perm(..., "space.manage_members")`
orqali tekshiriladi — bu bitta chaqiruv **ikkala** yo'lni ham qamrab oladi
(§B.5 / F-5):

* workspace roli `space.manage_members` ga ega (default: owner/admin), yoki
* chaqiruvchi shu bo'limda lokal `manager` (`SPACE_MANAGER_GRANTS`).

`viewer` uchun "eng past huquq g'olib" qoidasi hamma yozishni kesadi.

**404 vs 403 (§C.4).** `_get_space` tartibni saqlaydi: resurs yo'q → 404,
a'zo emas → 404, bo'lim ko'rinmaydi → 404, ruxsat yo'q → 403. Shundan keyingina
payload validatsiya qilinadi (400).

Realtime `access.revoked` frame'lari servis qatlamidan chiqadi (CLAUDE.md
konvensiyasi), view'lardan emas.
"""

from django.db.models import Case, IntegerField, Value, When
from rest_framework import status as http
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api import paginate
from apps.core.enums import SpaceAccess
from apps.workspaces import services
from apps.workspaces.models import SpaceMember
from apps.workspaces.serializers import (
    AddSpaceMemberSerializer,
    BulkSpaceMembersSerializer,
    SpaceMemberSerializer,
    UpdateSpaceMemberSerializer,
)

# `views.py` ga TEGILMAYDI — resolver o'sha yerdan import qilinadi, chunki
# 404/403 tartibi bitta joyda yashashi kerak.
from apps.workspaces.views import _get_space

MANAGE = "space.manage_members"

#: Menejerlar tepada, ko'ruvchilar pastda — model `Meta.ordering` alifbo
#: bo'yicha ("contributor" < "manager" < "viewer") noto'g'ri tartib berardi.
ACCESS_RANK = Case(
    When(access=SpaceAccess.MANAGER, then=Value(0)),
    When(access=SpaceAccess.CONTRIBUTOR, then=Value(1)),
    default=Value(2),
    output_field=IntegerField(),
)


def _roster(space):
    return (
        SpaceMember.objects.filter(space=space)
        .select_related("user")
        .annotate(rank=ACCESS_RANK)
        .order_by("rank", "user__email")
    )


def _row_or_404(space, user_id):
    """Bo'lim a'zosi bo'lmagan `user_id` → 404 (§D.6 xato jadvali)."""
    row = (
        SpaceMember.objects.select_related("user", "space")
        .filter(space=space, user_id=user_id)
        .first()
    )
    if row is None:
        raise NotFound()
    return row


class SpaceMemberListCreateView(APIView):
    """`GET|POST spaces/{space_id}/members/`."""

    def get(self, request, space_id):
        # O'qish uchun alohida ruxsat kodi yo'q: bo'limni ko'ra olgan har qanday
        # a'zo uning jamoasini ham ko'radi (avatarlar read-only ko'rinadi).
        space, _ = _get_space(request.user, space_id)
        return paginate(request, _roster(space), SpaceMemberSerializer)

    def post(self, request, space_id):
        space, _ = _get_space(request.user, space_id, MANAGE)
        serializer = AddSpaceMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = services.add_space_member(
            space,
            user_id=serializer.validated_data["user_id"],
            access=serializer.validated_data["access"],
            actor=request.user,
        )
        return Response(
            SpaceMemberSerializer(row, context={"request": request}).data,
            status=http.HTTP_201_CREATED,
        )


class SpaceMemberDetailView(APIView):
    """`PATCH|DELETE spaces/{space_id}/members/{user_id}/`."""

    def patch(self, request, space_id, user_id):
        space, _ = _get_space(request.user, space_id, MANAGE)
        row = _row_or_404(space, user_id)
        serializer = UpdateSpaceMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = services.update_space_member(
            row, access=serializer.validated_data["access"], actor=request.user
        )
        return Response(SpaceMemberSerializer(row, context={"request": request}).data)

    def delete(self, request, space_id, user_id):
        space, _ = _get_space(request.user, space_id, MANAGE)
        row = _row_or_404(space, user_id)
        services.remove_space_member(row)
        return Response(status=http.HTTP_204_NO_CONTENT)


class SpaceMemberBulkView(APIView):
    """`POST spaces/{space_id}/members/bulk/` — PM panelining "Saqlash" tugmasi.

    Javob `{"added", "removed", "results"}`: `results` — tranzaksiyadan keyingi
    **to'liq** bo'lim jamoasi, shunda klient bitta javob bilan holatni almashtira
    oladi va ikkinchi `GET` qilmaydi.
    """

    def post(self, request, space_id):
        space, _ = _get_space(request.user, space_id, MANAGE)
        serializer = BulkSpaceMembersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        counts = services.bulk_space_members(
            space,
            add=serializer.validated_data["add"],
            remove=serializer.validated_data["remove"],
            actor=request.user,
        )
        results = SpaceMemberSerializer(
            _roster(space), many=True, context={"request": request}
        ).data
        return Response({**counts, "results": results})
