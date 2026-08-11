import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status as http
from rest_framework.exceptions import NotFound, PermissionDenied, Throttled, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
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
from apps.core.enums import (
    CLOSED_STATUSES,
    AssignableRole,
    InvitationStatus,
    ROLE_RANK,
    WorkspaceRole,
)
from apps.core.exceptions import ApiError, Conflict
from apps.core.permissions import (
    ALL_CODES,
    CATALOG_VERSION,
    PERMISSION_BY_CODE,
    grouped_catalog,
)
from apps.workspaces import services
from apps.workspaces.models import (
    Folder,
    Invitation,
    RolePermission,
    Space,
    SpaceMember,
    TaskList,
    Workspace,
    WorkspaceMember,
)
from apps.workspaces.serializers import (
    AddMemberSerializer,
    FolderSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    ListSerializer,
    MemberProfileSerializer,
    MemberSerializer,
    ResetRolePermissionsSerializer,
    RolePermissionRowSerializer,
    RolePermissionUpdateSerializer,
    SpaceSerializer,
    UserSearchResultSerializer,
    WorkspaceSerializer,
)
from config.pagination import StandardPagination

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
        # `workspace.read` matritsada bor va uni o'chirib bo'ladi — demak u
        # ISHLASHI shart. Faqat `require_membership` chaqirilsa kod soxta
        # boshqaruv bo'lib qolardi: matritsada o'chirasan, hech narsa
        # o'zgarmaydi. Tartib §C.4 bo'yicha saqlanadi — `require_membership_perm`
        # avval a'zolikni tekshiradi (404), keyin ruxsatni (403).
        membership = require_membership_perm(request.user, workspace_id, "workspace.read")
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
        membership = require_membership_perm(request.user, workspace_id, "workspace.read")
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


#: A'zoni chiqarish servis qatlamiga ko'chdi (bitta tranzaksiya + haqiqiy
#: `on_commit`) — `apps/core/tests/test_access.py` import qiladigan nom
#: o'zgarishsiz qoldi.
_remove_member = services.remove_workspace_member


ROSTER_RANK = Case(
    When(role=WorkspaceRole.OWNER, then=Value(0)),
    When(role=WorkspaceRole.ADMIN, then=Value(1)),
    When(role=WorkspaceRole.MEMBER, then=Value(2)),
    default=Value(3),
    output_field=IntegerField(),
)


class MemberListView(APIView):
    def get_throttles(self):
        # F-6 bilan bir xil mantiq: to'g'ridan-to'g'ri qo'shish ham a'zolik
        # yaratadi, ya'ni taklif bilan bir xil narxda turadi. Ro'yxatni
        # o'qish throttle ostida emas.
        if self.request.method == "POST":
            self.throttle_scope = "invite"
            return [ScopedRateThrottle()]
        return []

    def get(self, request, workspace_id):
        require_membership_perm(request.user, workspace_id, "member.read")
        members = (
            WorkspaceMember.objects.filter(workspace_id=workspace_id)
            .select_related("user")
            .annotate(rank=ROSTER_RANK)
            .order_by("rank", "user__email")
        )
        return paginate(request, members, MemberSerializer)

    def post(self, request, workspace_id):
        """Ro'yxatdan o'tgan foydalanuvchini email taklifisiz qo'shish.

        Ruxsat `member.invite` — bu aynan «jamoaga odam qo'shish» huquqi;
        alohida kod kiritilmadi, chunki ikkala yo'l ham bir xil natijaga
        (yangi a'zolik) olib keladi va ularni ajratish matritsada "taklif
        yubora oladi, lekin qo'sha olmaydi" degan ma'nosiz holat yaratardi.
        """
        membership = require_membership_perm(request.user, workspace_id, "member.invite")
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(pk=serializer.validated_data["user_id"]).first()
        if user is None or not user.is_active:
            # `404` EMAS: chaqiruvchi ish maydonini ko'rmoqda, xato esa
            # yuborilgan `user_id` da. Mavjudlik orakuli ham ochilmaydi —
            # javob ikkala holatda bir xil.
            _validation_error("user_id", "Bunday foydalanuvchi topilmadi.")

        member = services.add_workspace_member(
            membership.workspace,
            request.user,
            user=user,
            role=serializer.validated_data["role"],
        )
        return Response(
            MemberSerializer(member, context={"request": request}).data,
            status=http.HTTP_201_CREATED,
        )


#: Qidiruv natijasining yuqori chegarasi. Ro'yxat "kimni qo'shaman" savoliga
#: javob beradi, katalogni ko'chirib olish uchun emas — shuning uchun
#: sahifalash ham yo'q.
USER_SEARCH_LIMIT = 10


@extend_schema(
    summary="Ro'yxatdan o'tgan foydalanuvchilarni qidirish",
    parameters=[OpenApiParameter("q", str, description="Kamida 2 belgi.")],
    responses=UserSearchResultSerializer(many=True),
)
class WorkspaceUserSearchView(APIView):
    """`GET workspaces/{id}/user-search/?q=` — ro'yxatdan o'tgan foydalanuvchilar.

    XAVFSIZLIK. Bu yagona endpoint bo'lib, ish maydoni tashqarisidagi
    hisoblarni ko'rsatadi, shuning uchun uchta chegara qo'yilgan:

    1. **Ruxsat** — `member.invite` (standartda faqat admin/owner). Oddiy
       a'zo yoki mehmon butun foydalanuvchilar bazasini varaqlay olmaydi.
    2. **Minimal so'rov** — kamida 2 belgi va bo'sh `q` bilan hech narsa
       qaytmaydi, ya'ni "hammasini ber" so'rovi yo'q.
    3. **Chegara va throttle** — 10 ta natija, `invite` scope'idagi rate
       limit (yaratish bilan bir xil byudjet).

    Nomsiz hisoblar ham topilishi uchun email bo'yicha qidiriladi; natijadagi
    `email` `UserSummarySerializer` qoidalari bo'yicha maskalanadi.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "invite"

    def get(self, request, workspace_id):
        require_membership_perm(request.user, workspace_id, "member.invite")
        query = (request.query_params.get("q") or "").strip()
        if len(query) < 2:
            return Response({"results": []})

        users = list(
            User.objects.filter(is_active=True)
            .filter(Q(email__icontains=query) | Q(full_name__icontains=query))
            .order_by("full_name", "email")[:USER_SEARCH_LIMIT]
        )
        roles = dict(
            WorkspaceMember.objects.filter(
                workspace_id=workspace_id, user__in=users
            ).values_list("user_id", "role")
        )
        pending = {
            email.lower()
            for email in Invitation.objects.filter(
                workspace_id=workspace_id, status=InvitationStatus.PENDING
            ).values_list("email", flat=True)
        }
        rows = [
            {
                "user": user,
                "is_member": user.id in roles,
                "role": roles.get(user.id),
                "has_pending_invitation": user.email.lower() in pending,
            }
            for user in users
        ]
        return Response(
            {
                "results": UserSearchResultSerializer(
                    rows, many=True, context={"request": request}
                ).data
            }
        )


class MemberProfileView(APIView):
    """`GET workspaces/{id}/members/{user_id}/profile/` — docs/API_CONTRACT.md §4.1.

    "Bu odam nima qilyapti" savoliga bitta javob: rol, qo'shilgan sana,
    statistika va bo'limlar kesimi.

    XAVFSIZLIK (binding). Har bir raqam **chaqiruvchining** ko'rish doirasida
    hisoblanadi — `visible_spaces_q(caller_membership)`. Mehmon yopiq
    bo'limdagi vazifalarni ko'rmaydi, demak ular hisobga ham kirmaydi; aks
    holda profil sahifasi yopiq bo'lim mavjudligini raqam orqali oshkor
    qilardi. A'zo bo'lmagan `user_id` (yoki boshqa workspace a'zosi) → 404.

    UNUMDORLIK. Barcha agregatlar `annotate`/`aggregate` bilan olinadi:
    a'zoga yoki bo'limga qarab so'rov ko'paymaydi (N+1 yo'q).
    """

    def get(self, request, workspace_id, user_id):
        membership = require_membership_perm(request.user, workspace_id, "member.read")
        target = (
            WorkspaceMember.objects.select_related("user")
            .filter(workspace_id=workspace_id, user_id=user_id)
            .first()
        )
        if target is None:
            raise NotFound()

        # Bitta so'rov: ko'rinadigan bo'limlar + a'zoning har biridagi ochiq
        # vazifalari. `distinct=True` — `visible_spaces_q` qo'shadigan
        # `space_members` JOIN'i sanoqni shishirmasligi uchun.
        space_open = Q(
            lists__tasks__deleted_at__isnull=True,
            lists__tasks__archived=False,
            lists__tasks__task_assignees__user_id=user_id,
        ) & ~Q(lists__tasks__status__in=CLOSED_STATUSES)
        spaces = list(
            Space.objects.filter(workspace_id=workspace_id)
            .filter(visible_spaces_q(membership))
            .annotate(open_tasks=Count("lists__tasks", filter=space_open, distinct=True))
            .order_by("position", "name")
        )
        space_ids = {space.id for space in spaces}

        stats = _member_stats(space_ids, user_id, caller=request.user)
        payload = {
            "user": target.user,
            "role": target.role,
            "joined_at": target.joined_at,
            "last_active_at": target.last_active_at,
            "stats": stats,
            "spaces": spaces,
        }
        return Response(MemberProfileSerializer(payload, context={"request": request}).data)


def _member_stats(space_ids, user_id, *, caller):
    """§4.1 statistikalari — 3 ta so'rov, a'zolar soniga bog'liq emas.

    `due_today` va `overdue_tasks` ATAYLAB kesishmaydi: bugun soat 09:00 ga
    qo'yilgan va allaqachon o'tib ketgan vazifa faqat "muddati o'tgan" bo'lib
    sanaladi — bosh sahifadagi guruhlash bilan bir xil qoida (§10.5).
    Kun chegarasi chaqiruvchining vaqt mintaqasida hisoblanadi.
    """
    import zoneinfo

    from apps.comments.models import Comment
    from apps.tasks.models import Task

    now = timezone.now()
    try:
        tz = zoneinfo.ZoneInfo(getattr(caller, "timezone", None) or "UTC")
    except Exception:  # noqa: BLE001 — noto'g'ri saqlangan tz profilni buzmasin
        tz = zoneinfo.ZoneInfo("UTC")
    local_now = now.astimezone(tz)
    day_end = (local_now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    base = Task.objects.filter(list__space_id__in=space_ids)
    open_q = ~Q(status__in=CLOSED_STATUSES) & Q(archived=False)
    agg = base.filter(task_assignees__user_id=user_id).aggregate(
        open_tasks=Count("id", filter=open_q, distinct=True),
        overdue_tasks=Count("id", filter=open_q & Q(due_date__lt=now), distinct=True),
        due_today=Count(
            "id",
            filter=open_q & Q(due_date__gte=now, due_date__lt=day_end),
            distinct=True,
        ),
        completed_tasks=Count("id", filter=Q(completed_at__isnull=False), distinct=True),
    )
    agg["created_tasks"] = base.filter(created_by_id=user_id).count()
    agg["comments"] = Comment.objects.filter(
        author_id=user_id, task__list__space_id__in=space_ids
    ).count()
    return agg


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

        previous_role = target.role
        target.role = new_role
        target.save(update_fields=["role", "updated_at"])
        workspace = target.workspace
        if previous_role != new_role:
            from apps.core.enums import WorkspaceRole as _Role
            from apps.notifications.services import NotificationKind, notify

            notify(
                user=target.user,
                actor=request.user,
                workspace=workspace,
                kind=NotificationKind.ROLE_CHANGED,
                title=f"«{workspace.name}»dagi rolingiz o'zgardi",
                body=f"Yangi rol: {_Role(new_role).label}.",
                url=f"/w/{workspace.id}",
            )
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
        services.remove_workspace_member(target, actor=request.user)
        return Response(status=http.HTTP_204_NO_CONTENT)


class MemberLeaveView(APIView):
    def post(self, request, workspace_id):
        membership = require_membership(request.user, workspace_id)
        if membership.role == WorkspaceRole.OWNER and _owner_count(workspace_id) == 1:
            raise Conflict("The last owner cannot leave; transfer ownership first.")
        # `actor` = chiquvchining o'zi → `notify()` xabarni tashlab yuboradi.
        # Aks holda odam o'zi bosgan tugma haqida bildirishnoma olardi.
        services.remove_workspace_member(membership, actor=request.user)
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
        member = services.accept_invitation(invitation, request.user)
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
        space, membership = _get_space(request.user, space_id, perm="space.update")
        # AppSec: `is_private` — bo'limning ish maydoniga nisbatan CHEGARASI,
        # oddiy atribut emas. `space.update` (PM `SPACE_MANAGER_GRANTS` orqali
        # oladi) uni o'zgartirishga yetmaydi, aks holda bo'lim menejeri yopiq
        # loyihani butun jamoaga ocha olardi. Tekshiruv validatsiyadan OLDIN
        # (§1.7 "permission before validation") va faqat qiymat HAQIQATAN
        # o'zgarayotgan bo'lsa — aks holda nomni o'zgartirayotgan PM ning
        # to'liq obyekt yuboradigan PATCH'i buzilardi.
        if "is_private" in request.data:
            wanted = parse_bool(request.data.get("is_private"), space.is_private)
            if wanted != space.is_private:
                require_space_perm(membership, space, "space.change_visibility")
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
        # `is_private` alohida yo'ldan boradi: u atribut emas, CHEGARA.
        # `serializer.save()` uni jimgina yozib qo'ysa backfill,
        # `permissions_version` va `access.revoked` tushib qolardi — ochiq
        # soket endi yopiq bo'lgan bo'limning freymlarini oqizishda davom
        # etardi. Bitta tranzaksiya: nom/rang va ko'rinish birga yoziladi.
        wanted_private = serializer.validated_data.pop("is_private", None)
        with transaction.atomic():
            serializer.save()
            if wanted_private is not None and wanted_private != space.is_private:
                services.set_space_visibility(
                    space, is_private=wanted_private, actor=request.user
                )
        return Response(SpaceSerializer(space, context={"request": request}).data)

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
        folder_id = services.check_client_id(
            Folder,
            request.data.get("id") or None,
            scope=Folder.objects.filter(space=space),
        )
        folder = Folder.objects.create(
            id=folder_id or uuid.uuid4(),
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
            services.detach_folder(folder)
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
        list_id = services.check_client_id(
            TaskList,
            request.data.get("id") or None,
            scope=TaskList.objects.filter(space=space),
        )
        task_list = TaskList.objects.create(
            id=list_id or uuid.uuid4(),
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
        services.update_list(
            task_list,
            serializer.validated_data,
            actor=request.user,
            client_id=client_id_of(request),
        )
        return Response(ListSerializer(task_list, context={"request": request}).data)

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

        # `expected_version` — optimistik qulf, va u FAQAT qatorni band qilgan
        # holda o'qilsa ma'noga ega. Tekshiruv tranzaksiyadan tashqarida
        # bo'lsa, bir xil `expected_version` bilan kelgan ikkita PUT ham
        # o'tib ketadi va ikkinchisi birinchisini jimgina bosib ketadi —
        # ya'ni "matritsa siz yuklaganidan keyin o'zgardi" xatosi hech qachon
        # chiqmaydi. `select_for_update()` SQLite'da no-op (Django uni
        # tashlab yuboradi), PostgreSQL'da esa ikkinchi PUT birinchisining
        # commit'ini kutadi va 409 oladi.
        with transaction.atomic():
            locked = Workspace.objects.select_for_update().get(pk=workspace.pk)
            if locked.permissions_version != expected:
                raise Conflict(
                    "The permission matrix changed since you loaded it.",
                    details={
                        "expected_version": expected,
                        "current_version": locked.permissions_version,
                    },
                )
            services.ensure_role_permissions(locked)
            _check_monotonic(_resulting_matrix(locked, changes))
            _write_matrix(locked, changes, request.user)
            bump_permissions_version(locked, actor=request.user)
        return Response(_matrix_payload(locked))


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
                # IKKI XIL HISOBLAGICH, ATAYLAB ALOHIDA:
                #   `version`          — SHU ish maydonining matritsa/ko'rinish
                #                        hisoblagichi, har tahrirda oshadi;
                #   `catalog_version`  — KOD bilan birga keladigan ruxsat
                #                        katalogining versiyasi, faqat deploy
                #                        bilan o'zgaradi.
                # Ularni solishtirish yoki birlashtirish xato bo'lardi. Katalog
                # `staleTime/gcTime: Infinity` bilan keshlanadi, shuning uchun
                # deploy'dan keyin ochiq qolgan tab uni faqat shu maydon orqali
                # bekor qila oladi. `role-permissions/` da ham bor, lekin u
                # `workspace.manage_permissions` talab qiladi (default: owner) —
                # `my-permissions/` esa har bir a'zoda, har ekranda o'qiladi.
                "version": membership.workspace.permissions_version,
                "catalog_version": CATALOG_VERSION,
                "permissions": sorted(my_permissions(membership)),
                "spaces": [
                    {"space_id": str(space_id), "access": access}
                    for space_id, access in spaces
                ],
            }
        )


# ---------------------------------------------------------------- search


#: `q` shu uzunlikdan qisqa bo'lsa qidiruv umuman ishga tushmaydi (§13):
#: bitta harf butun ish maydonini skanerlashga arziydigan so'rov emas.
SEARCH_MIN_LENGTH = 2


class _SearchBucket:
    """Bitta natija turi: queryset + uni `{"type", "item"}` ga aylantirish."""

    __slots__ = ("type", "queryset", "serializer_class", "_count")

    def __init__(self, type_name, queryset, serializer_class):
        self.type = type_name
        self.queryset = queryset
        self.serializer_class = serializer_class
        self._count = None

    def count(self) -> int:
        if self._count is None:
            self._count = self.queryset.count()
        return self._count

    def window(self, start, stop, context):
        rows = list(self.queryset[start:stop])
        serializer = self.serializer_class(rows, many=True, context=context)
        return [{"type": self.type, "item": item} for item in serializer.data]


class _SearchResults:
    """Bir necha queryset'ning DANGASA, chegaralangan ketma-ketligi.

    `Paginator` bu obyektdan faqat ikki narsa so'raydi: `count()` va BITTA
    kesma. Shuning uchun bu yerda hech qachon butun natija to'plami xotiraga
    olinmaydi: `count` — har bir turdan bittadan `COUNT(*)`, kesma esa faqat
    joriy sahifadagi qatorlarni `LIMIT/OFFSET` bilan oladi.

    Turlar ketma-ketligi qat'iy (vazifa → ro'yxat → jild → bo'lim), har bir
    queryset esa yakuniy `id` bo'yicha tartiblangan — aks holda bir xil
    `updated_at`/`name` li qatorlar sahifalar orasida sakrab, ba'zilari
    ikki marta, ba'zilari umuman ko'rinmasdi.
    """

    def __init__(self, buckets, context):
        self._buckets = buckets
        self._context = context

    def count(self) -> int:
        return sum(bucket.count() for bucket in self._buckets)

    def __len__(self) -> int:
        return self.count()

    def __getitem__(self, window):
        start, stop = window.start or 0, window.stop
        results = []
        offset = 0
        for bucket in self._buckets:
            size = bucket.count()
            lo, hi = max(start - offset, 0), min(stop - offset, size)
            if lo < hi:
                results.extend(bucket.window(lo, hi, self._context))
            offset += size
            if offset >= stop:
                break
        return results


class WorkspaceSearchView(APIView):
    """`GET workspaces/{id}/search/?q=` — docs/API_CONTRACT.md §13.

    UNUMDORLIK (bu endpoint ilgari ish maydoni o'sishi bilan chiziqli edi).
    Uch narsa qat'iy:

    1. **Sahifalash DB'da.** Ilgari to'rttala queryset to'liq Python
       ro'yxatiga aylantirilib, keyin `StandardPagination` undan 50 tasini
       kesib olardi: 50 000 mos vazifa 50 tasini qaytarish uchun 50 000 dict
       quriladi. Endi `_SearchResults` faqat `COUNT(*)` va bitta
       `LIMIT/OFFSET` kesmasini ishlatadi.
    2. **Prefetch.** `TaskSerializer` biriktirilganlar / teglar /
       kuzatuvchilarni o'qiydi — prefetch'siz bu har bir vazifa uchun 4 ta
       so'rov (`ListTasksView` buni to'g'ri qiladi, qidiruv qilmasdi).
    3. **Doira o'zgarmaydi.** `visible_spaces_q(membership)` — mehmon yopiq
       bo'limni ham, undagi vazifalarni ham, hatto ularning NOMINI ham
       ko'rmaydi. `count` sahifalashdan oldin filtrlangan (§13).

    FTS haqida (§13 "PostgreSQL full-text"). `Q(title__icontains=q)` —
    oldingi joker belgili LIKE, uni hech qanday indeks tutolmaydi. To'g'ri
    yechim `SearchVector`ni GIN indeksli `SearchVectorField` ustida ishlatish,
    ammo bu `apps/tasks/models.py` ga migratsiya talab qiladi (boshqa
    muhandisning fayli); indekssiz FTS esa aynan shu sekvensial skanerlashni
    beradi, ustiga natija TO'PLAMINI ham o'zgartiradi (stemming + so'z
    chegarasi: "Bosh" endi "Boshlash" ni topmaydi), bu esa §13 dagi "result
    sets must be equivalent" bandini buzardi. Shuning uchun bu yerda ikkala
    DB uchun bir xil, chegaralangan `icontains` yo'li qoldi.
    """

    def get(self, request, workspace_id):
        membership = require_membership_perm(request.user, workspace_id, "workspace.read")
        q = request.query_params.get("q")
        if q is None or q.strip() == "":
            _validation_error("q", "q is required.")
        q = q.strip()

        context = {"request": request}
        buckets = (
            self._buckets(membership, workspace_id, q)
            if len(q) >= SEARCH_MIN_LENGTH
            else []
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(_SearchResults(buckets, context), request)
        return paginator.get_paginated_response(page)

    def _buckets(self, membership, workspace_id, q):
        from apps.tasks.models import Task
        from apps.tasks.serializers import TaskSerializer
        from apps.tasks.views import TASK_PREFETCH, TASK_SELECT

        # `visible_spaces_q` mehmon uchun `space_members` ga JOIN qo'shadi,
        # ya'ni bir bo'lim uning a'zolari soniga qarab takrorlanishi mumkin —
        # `distinct()` bo'lmasa "Bo'lim" natijasi ro'yxatda bir necha marta
        # chiqar va `count` ham shishardi.
        space_scope = (
            Space.objects.filter(workspace_id=workspace_id)
            .filter(visible_spaces_q(membership))
            .distinct()
        )
        tasks = (
            Task.objects.filter(
                list__space__in=space_scope,
                archived=False,
                list__archived=False,
            )
            .filter(Q(title__icontains=q) | Q(description_html__icontains=q))
            .select_related(*TASK_SELECT)
            .prefetch_related(*TASK_PREFETCH)
            .order_by("-updated_at", "id")
        )
        lists = TaskList.objects.filter(
            space__in=space_scope, archived=False, name__icontains=q
        ).order_by("name", "id")
        folders = Folder.objects.filter(
            space__in=space_scope, archived=False, name__icontains=q
        ).order_by("name", "id")
        spaces = space_scope.filter(archived=False, name__icontains=q).order_by("name", "id")
        return [
            _SearchBucket("task", tasks, TaskSerializer),
            _SearchBucket("list", lists, ListSerializer),
            _SearchBucket("folder", folders, FolderSerializer),
            _SearchBucket("space", spaces, SpaceSerializer),
        ]
