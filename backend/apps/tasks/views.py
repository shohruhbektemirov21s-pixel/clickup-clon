import uuid as uuid_mod

from django.db.models import Count, F, Window
from django.db.models.functions import RowNumber
from rest_framework import status as http
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.access import (
    check_space_visible,
    has_space_perm,
    require_membership,
    require_membership_perm,
    require_space_perm,
    visible_spaces_q,
)
from apps.core.api import client_id_of, paginate
from apps.core.enums import ActivityVerb
from apps.core.exceptions import Conflict
from apps.tasks import services
from apps.tasks.filters import (
    apply_ordering,
    apply_task_filters,
    include_deleted_requested,
    ordering_fields,
)
from apps.tasks.models import Tag, Task, TaskActivity
from apps.tasks.serializers import (
    TagSerializer,
    TaskActivitySerializer,
    TaskInputSerializer,
    TaskSerializer,
    WorkspaceActivitySerializer,
)
from apps.workspaces.models import Space
from apps.workspaces.views import get_list
from config.pagination import StandardPagination

TASK_SELECT = ("status", "list", "list__space", "created_by", "updated_by")
TASK_PREFETCH = ("task_assignees__user", "task_tags__tag", "task_watchers__user")

#: `?group_by=status` ustunidagi vazifalar soni uchun QAT'IY shift — `page_size`
#: dan MUSTAQIL. Doska javobi sahifalanmaydi (§1.5 istisnosi), shuning uchun
#: `page_size=200` × 30 status = bitta so'rovda 6000 vazifa degani edi.
#: Ustunni to'liq ko'rish yo'li o'zgarmagan: `?status=<id>&page=2` (tekis
#: konvert), §10.4 da hujjatlashtirilgan.
MAX_TASKS_PER_GROUP = 50

#: `assignee_ids` PATCH/POST payload'idagi o'zgarish turlari.
ASSIGNEES_UNCHANGED = "unchanged"
ASSIGNEES_SELF_ONLY = "self_only"
ASSIGNEES_OTHERS = "others"


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


def _payload_list(data, key):
    """`assignee_ids` ni JSON (list) va form-data (QueryDict) dan bir xil oladi."""
    if hasattr(data, "getlist"):
        return data.getlist(key)
    value = data.get(key)
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple, set)) else [value]


def assignee_change_kind(task, data, caller_id) -> str:
    """`assignee_ids` payload'i biriktirishni qanday o'zgartiradi?

    → `ASSIGNEES_UNCHANGED` — maydon yo'q yoki to'plam aynan o'sha;
    → `ASSIGNEES_SELF_ONLY` — farq FAQAT chaqiruvchining o'zi (o'zini oldi
      yoki o'zini olib tashladi);
    → `ASSIGNEES_OTHERS`    — boshqa birov qo'shildi/olib tashlandi.

    O'zgarmagan to'plamni "o'zgardi" deb hisoblamaslik ataylab: frontend
    PATCH'da ko'pincha butun obyektni qaytarib yuboradi, shuning uchun "maydon
    bor" ni "biriktirish o'zgardi" deb bilish `task.assign` siz har qanday
    tahrirni sindirardi.

    Parse qilib bo'lmasa `ASSIGNEES_OTHERS` (fail-closed): ruxsat
    validatsiyadan oldin tekshiriladi, noto'g'ri payload esa ruxsatli
    chaqiruvchida baribir 400 bo'ladi.
    """
    if "assignee_ids" not in data:
        return ASSIGNEES_UNCHANGED
    try:
        wanted = {uuid_mod.UUID(str(a)) for a in _payload_list(data, "assignee_ids")}
    except (ValueError, AttributeError, TypeError):
        return ASSIGNEES_OTHERS
    current = set(task.task_assignees.values_list("user_id", flat=True))
    delta = wanted ^ current
    if not delta:
        return ASSIGNEES_UNCHANGED
    return ASSIGNEES_SELF_ONLY if delta == {caller_id} else ASSIGNEES_OTHERS


def require_task_editor(task, membership, code="task.update", space=None):
    """§A "Rezolyutsiya tartibi" (BINDING).

    1. `task.update` / `task.move` bo'lsa → ruxsat;
    2. aks holda `task.update_assigned` **va** chaqiruvchi `TaskAssignee`
       qatoriga ega bo'lsa → ruxsat;
    3. aks holda `403`.

    `space` — tekshiruv qaysi bo'limga nisbatan bajarilishi. Odatda vazifaning
    o'z bo'limi; ko'chirishda MANZIL bo'limi uchun ham aynan shu tartib
    qayta ishlatiladi (pastdagi `TaskMoveView` ga qarang).
    """
    space = space or task.list.space
    if has_space_perm(membership, space, code):
        return membership
    if has_space_perm(membership, space, "task.update_assigned") and task.task_assignees.filter(
        user_id=membership.user_id
    ).exists():
        return membership
    raise PermissionDenied()


class ListTasksView(APIView):
    def get(self, request, list_id):
        task_list, membership = get_list(request.user, list_id, perm="task.read")
        include_deleted = include_deleted_requested(request, membership)
        manager = Task.all_objects if include_deleted else Task.objects
        qs = (
            manager.filter(list=task_list)
            .select_related(*TASK_SELECT)
            .prefetch_related(*TASK_PREFETCH)
        )
        qs = apply_task_filters(qs, request, membership)

        if request.query_params.get("group_by") == "status":
            return self._grouped(request, task_list, qs, manager)

        qs = apply_ordering(qs, request, default=("status__order", "position", "created_at"))
        return paginate(request, qs, TaskSerializer)

    def _grouped(self, request, task_list, qs, manager):
        """Doska payload'i — §10.4, ustunlar soniga BOG'LIQ BO'LMAGAN so'rovlar.

        Ilgari har bir status uchun alohida `COUNT(*)` + alohida `SELECT`
        ketardi (30 ta statusli doskada ~60-90 so'rov, ustiga har bir
        ustunning `prefetch` lari). Endi:

        * bitta `GROUP BY status_id` — barcha `count` lar;
        * bitta `ROW_NUMBER() OVER (PARTITION BY status_id)` oynali so'rov —
          har ustunning birinchi `limit` qatori (SQLite 3.25+ va PostgreSQL
          ikkalasida ham bor);
        * `prefetch_related` ning o'zgarmas 3 ta so'rovi.

        Filtrlar `.distinct()` qo'shishi mumkin (assignee/tag JOIN'lari), oyna
        funksiyasi esa DISTINCT'dan OLDIN hisoblanadi — shuning uchun oldin
        filtrlangan `pk` to'plami olinadi va reyting JOIN'siz toza queryset
        ustida bajariladi.
        """
        limit = self._group_limit(request)
        order = ordering_fields(request, default=("position", "created_at"))
        base = manager.filter(list=task_list, pk__in=qs.order_by().values("pk"))

        counts = dict(
            base.order_by().values_list("status_id").annotate(n=Count("id"))
        )
        ranked = (
            base.annotate(
                _rank=Window(RowNumber(), partition_by=F("status_id"), order_by=order)
            )
            .filter(_rank__lte=limit)
            .select_related(*TASK_SELECT)
            .prefetch_related(*TASK_PREFETCH)
            .order_by(*order)
        )
        by_status = {}
        for task in ranked:
            by_status.setdefault(task.status_id, []).append(task)

        groups = [
            {
                "status_id": str(status.id),
                "count": counts.get(status.id, 0),
                "results": TaskSerializer(
                    by_status.get(status.id, []), many=True, context={"request": request}
                ).data,
            }
            for status in task_list.effective_status_set.statuses.order_by("order")
        ]
        return Response({"group_by": "status", "groups": groups})

    @staticmethod
    def _group_limit(request):
        """`page_size` hali ham validatsiya qilinadi (400), lekin ustunni
        `MAX_TASKS_PER_GROUP` dan ko'p qilib ocholmaydi."""
        page_size = StandardPagination().get_page_size(request)
        return min(page_size, MAX_TASKS_PER_GROUP)

    def post(self, request, list_id):
        task_list, membership = get_list(request.user, list_id, perm="task.create")
        # AppSec: `task.assign` katalogda admin-only, lekin yaratishda
        # `assignee_ids` ilgari faqat `task.create` bilan o'tib ketardi —
        # ya'ni kod REST darajasida chetlab o'tilardi. Bo'sh ro'yxat (yoki
        # maydonning yo'qligi) hech narsani o'zgartirmaydi → tekshirilmaydi.
        #
        # MAHSULOT QARORI: "o'ziga vazifa ochish" `task.assign` talab qilmaydi.
        # Chaqiruvchi bu ro'yxatda `task.create` ga allaqachon ega va o'zini
        # biriktirish hech kimga yangi kirish bermaydi — `SpaceMember` granti
        # (`_grant_assignee_space_access`) faqat bo'limni KO'RMAYOTGAN odamga
        # yoziladi, chaqiruvchi esa uni ko'rib turibdi. Ro'yxatda o'zidan
        # boshqa (yoki umuman UUID bo'lmagan) qiymat bo'lsa — to'liq tekshiruv.
        wanted = {str(a) for a in _payload_list(request.data, "assignee_ids")}
        if wanted - {str(request.user.id)}:
            require_space_perm(membership, task_list.space, "task.assign")
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
        task, membership = get_task(request.user, task_id)
        require_space_perm(membership, task.list.space, "task.read")
        return Response(TaskSerializer(task, context={"request": request}).data)

    def patch(self, request, task_id):
        if "deleted_at" in request.data:
            return self._restore(request, task_id)
        task, membership = get_task(request.user, task_id)
        require_task_editor(task, membership)
        # AppSec: `require_task_editor` `task.update_assigned` bilan ham
        # o'tadi (guest darajasi). Biriktirishni o'zgartirish esa alohida,
        # admin-only `task.assign` kodi — aks holda yopiq bo'limdagi vazifaga
        # biriktirilgan guest hamkasbini assignee qilib qo'yib, unga
        # `SpaceMember` yozdirib butun bo'limni ocha olardi
        # (`space.manage_members` ni `task.update_assigned` orqali aylanib
        # o'tish). U yana barcha hamkasblarini jimgina yechib tashlay olardi.
        #
        # MAHSULOT QARORI (ataylab o'yilgan teshik): faqat O'ZINI qo'shish /
        # o'zini yechish `task.assign` talab qilmaydi — "vazifani olaman" va
        # "vazifani tashlab ketaman" oqimlari admin aralashuvisiz ishlashi
        # kerak. Bu kengaytma emas: chaqiruvchi shu nuqtada vazifani ko'rib va
        # tahrirlay olib turibdi (`require_task_editor` yuqorida o'tgan),
        # `_grant_assignee_space_access` esa bo'limni allaqachon ko'rayotgan
        # odamga `SpaceMember` yozmaydi. Farq o'zidan tashqariga chiqishi
        # bilan (yoki payload parse qilinmasa) to'liq tekshiruv qaytadi.
        if assignee_change_kind(task, request.data, membership.user_id) == ASSIGNEES_OTHERS:
            require_space_perm(membership, task.list.space, "task.assign")
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
        require_space_perm(membership, task.list.space, "task.restore")
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
        require_space_perm(membership, task.list.space, "task.delete")
        services.soft_delete_task(task, request.user, client_id=client_id_of(request))
        return Response(status=http.HTTP_204_NO_CONTENT)


class TaskMoveView(APIView):
    def patch(self, request, task_id):
        task, membership = get_task(request.user, task_id)
        require_task_editor(task, membership, "task.move")
        list_id = request.data.get("list_id")
        if not list_id:
            raise ValidationError({"list_id": ["list_id is required."]})
        # destination list must be readable by the caller too (404 if not)
        target_list, _ = get_list(request.user, list_id)
        # AppSec: `require_task_editor` yuqorida MANBA bo'limiga nisbatan
        # baholanadi. Boshqa bo'limga ko'chirishda bu yetarli emas edi — A
        # bo'limining menejeri (yoki oddiy `task.move` egasi) vazifani o'zi
        # faqat `viewer` bo'lgan B bo'limiga surib qo'ya olardi: yozish
        # huquqi manbadan olinib, natija manzilda paydo bo'lardi. Manzil
        # uchun AYNAN o'sha §A rezolyutsiya tartibi qayta ishlatiladi, ya'ni
        # biriktirilgan odam o'z vazifasini ko'chirish qobiliyatini
        # yo'qotmaydi.
        #
        # Ish maydonlari HAR XIL bo'lsa tekshiruv o'tkazib yuboriladi: u holda
        # `membership` boshqa maydonniki bo'lib, uning matritsasi bu bo'limga
        # taalluqli emas — `move_task` bunday ko'chirishni 400 bilan rad etadi.
        same_workspace = (
            target_list.space.workspace_id == task.list.space.workspace_id
        )
        if same_workspace and target_list.space_id != task.list.space_id:
            require_task_editor(task, membership, "task.move", space=target_list.space)
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
    """Kuzatuvchi bo'lish / bekor qilish.

    `task.watch` kodi katalogda va grant to'plamlarida bor edi, lekin bu yerda
    hech qachon tekshirilmasdi — ya'ni matritsadan uni olib tashlash REST
    xatti-harakatiga ta'sir qilmasdi ("yolg'on nazorat").
    """

    def post(self, request, task_id):
        task, membership = get_task(request.user, task_id)
        require_space_perm(membership, task.list.space, "task.watch")
        created = services.watch_task(task, request.user)
        task, _ = get_task(request.user, task_id)
        return Response(
            TaskSerializer(task, context={"request": request}).data,
            status=http.HTTP_201_CREATED if created else http.HTTP_200_OK,
        )

    def delete(self, request, task_id):
        task, membership = get_task(request.user, task_id)
        require_space_perm(membership, task.list.space, "task.watch")
        services.unwatch_task(task, request.user)
        return Response(status=http.HTTP_204_NO_CONTENT)


class TaskActivityView(APIView):
    """GET tasks/{id}/activity/ — the task's history, newest first."""

    def get(self, request, task_id):
        task, membership = get_task(request.user, task_id)
        require_space_perm(membership, task.list.space, "task.read")
        activities = (
            TaskActivity.objects.filter(task=task)
            .select_related("actor")
            .order_by("-created_at")
        )
        return paginate(request, activities, TaskActivitySerializer)


class WorkspaceActivityView(APIView):
    """`GET workspaces/{id}/activity/` — docs/API_CONTRACT.md §10.8.

    Ish maydoni bo'yicha faoliyat tasmasi, yangisidan eskisiga. Filtrlar:
    `?actor=<user uuid>` va `?verb=<ActivityVerb>`; ikkalasi ham ixtiyoriy va
    AND bilan birlashadi. Sahifalash — standart §1.5 konverti.

    XAVFSIZLIK: `visible_spaces_q` — tasma faqat chaqiruvchi ko'ra oladigan
    bo'limlardagi vazifalar tarixini beradi. O'chirilgan (soft-delete)
    vazifalar yozuvlari ham chiqmaydi: vazifaning o'zi 404 bo'lsa, uning
    tarixi ham ko'rinmasligi kerak.
    """

    def get(self, request, workspace_id):
        membership = require_membership_perm(request.user, workspace_id, "task.read")
        spaces = Space.objects.filter(workspace_id=workspace_id).filter(
            visible_spaces_q(membership)
        )
        qs = TaskActivity.objects.filter(
            task__list__space__in=spaces, task__deleted_at__isnull=True
        )

        actor = request.query_params.get("actor")
        if actor:
            try:
                uuid_mod.UUID(str(actor))
            except (ValueError, AttributeError, TypeError):
                raise ValidationError({"actor": ["actor must be a UUID."]})
            qs = qs.filter(actor_id=actor)

        verb = request.query_params.get("verb")
        if verb:
            if verb not in ActivityVerb.values:
                raise ValidationError({"verb": ["Unsupported activity verb."]})
            qs = qs.filter(verb=verb)

        qs = qs.select_related("actor", "task", "task__list").order_by("-created_at")
        return paginate(request, qs, WorkspaceActivitySerializer)


class WorkspaceTasksView(APIView):
    def get(self, request, workspace_id):
        membership = require_membership_perm(request.user, workspace_id, "task.read")
        include_deleted = include_deleted_requested(request, membership)
        manager = Task.all_objects if include_deleted else Task.objects

        # §C.5: bitta helper — bu view avval o'z visibility mantiqini
        # takrorlardi (F-3 teshigi).
        spaces = Space.objects.filter(workspace_id=workspace_id).filter(
            visible_spaces_q(membership)
        )
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
        membership = require_membership_perm(request.user, workspace_id, "tag.create")
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
    def _get(self, user, tag_id, perm):
        tag = Tag.objects.select_related("workspace").filter(pk=tag_id).first()
        if tag is None:
            raise NotFound()
        require_membership_perm(user, tag.workspace_id, perm)
        return tag

    def patch(self, request, tag_id):
        tag = self._get(request.user, tag_id, "tag.update")
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
        tag = self._get(request.user, tag_id, "tag.delete")
        tag.delete()
        return Response(status=http.HTTP_204_NO_CONTENT)
