"""Workspace-hierarchy services. All realtime events are emitted from here,
never from views (CLAUDE.md convention)."""

import secrets
import uuid
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from apps.core.enums import (
    AssignableRole,
    InvitationStatus,
    SpaceAccess,
    SpaceMemberSource,
    StatusType,
    WorkspaceRole,
)
from apps.core.exceptions import Conflict, PositionConflict
from apps.core.ordering import midstring
from apps.realtime import events
from apps.workspaces.models import (
    Folder,
    Invitation,
    RolePermission,
    Space,
    SpaceMember,
    Status,
    StatusSet,
    TaskList,
    Workspace,
    WorkspaceMember,
)

DEFAULT_STATUSES = [
    {"name": "BAJARILADI", "type": StatusType.OPEN, "color": "#87909E", "is_default": True},
    {"name": "JARAYONDA", "type": StatusType.ACTIVE, "color": "#4194F6", "is_default": False},
    {"name": "BAJARILDI", "type": StatusType.CLOSED, "color": "#6BC950", "is_default": False},
]


def check_client_id(model, supplied_id, *, scope=None):
    """Client-generated ids (API_CONTRACT.md §1.4) — returns the id to persist.

    Kontrakt talabi: klient o'ylab topgan `id` allaqachon band bo'lsa `409`,
    shunda tarmoq uzilgandan keyingi qayta urinish "men buni yaratganman"
    ekanini bilib oladi.

    XAVFSIZLIK. Tekshiruv jadval bo'ylab bo'lsa, `POST /workspaces/` ga
    begona UUID yuborish `409` yoki `201` qaytaradi va bu **global mavjudlik
    orakuli** bo'lib qoladi: chaqiruvchi ko'ra olmaydigan resurs haqida
    ma'lumot sizadi (§1.7 buni taqiqlaydi). Shuning uchun `scope=` — bu
    chaqiruvchi allaqachon ko'rayotgan idish (workspace, bo'lim, status
    to'plami) bo'yicha toraytirilgan queryset:

    * id shu doirada band  → `409` (qayta urinish semantikasi saqlanadi);
    * id doiradan TASHQARIDA band → oshkor qilinmaydi, `None` qaytadi va
      chaqiruvchi server tomonda yangi UUID ajratadi (javob tanasi baribir
      haqiqiy `id` ni olib keladi);
    * bo'sh                → `supplied_id`.

    `scope=None` — eski, jadval bo'ylab xatti-harakat. Boshqa app'lardagi
    chaqiruvchilar (tasks, comments) shu yo'lda qoladi.
    """
    if supplied_id in (None, ""):
        return None
    manager = getattr(model, "all_objects", model.objects)
    if scope is None:
        if manager.filter(pk=supplied_id).exists():
            raise Conflict("A resource with this id already exists.")
        return supplied_id
    if scope.filter(pk=supplied_id).exists():
        raise Conflict("A resource with this id already exists.")
    if manager.filter(pk=supplied_id).exists():
        return None
    return supplied_id


def next_position(qs) -> str:
    last = qs.order_by("-position").values_list("position", flat=True).first()
    return midstring(last, None)


def generate_slug(name: str) -> str:
    base = slugify(name) or "workspace"
    slug = base[:120]
    while Workspace.objects.filter(slug=slug).exists():
        slug = f"{base[:120]}-{secrets.token_hex(3)}"
    return slug


def seed_default_statuses(status_set: StatusSet) -> list[Status]:
    return [
        Status.objects.create(
            status_set=status_set,
            name=s["name"],
            type=s["type"],
            color=s["color"],
            order=i,
            is_default=s["is_default"],
        )
        for i, s in enumerate(DEFAULT_STATUSES)
    ]


def ensure_role_permissions(workspace) -> int:
    """Idempotent: yetishmayotgan (role, permission) qatorlarini defaultdan yaratadi.

    docs/DESIGN_PERMISSIONS.md §B.6. Uch nuqtadan chaqiriladi:
    (1) migratsiya 0003, (2) `bootstrap_workspace()`, (3) resolver fallback.
    `bulk_create` signal chiqarmaydi va default qiymat yozadi — shuning uchun
    bu yerda `bump_permissions_version()` chaqirilmaydi.
    """
    from apps.core.permissions import PERMISSIONS

    existing = set(
        RolePermission.objects.filter(workspace=workspace).values_list("role", "permission")
    )
    rows = [
        RolePermission(
            workspace=workspace, role=role, permission=p.code, allowed=(role in p.defaults)
        )
        for p in PERMISSIONS
        if not p.deprecated
        for role in AssignableRole.values
        if (role, p.code) not in existing
    ]
    if rows:
        RolePermission.objects.bulk_create(rows, ignore_conflicts=True)
    return len(rows)


def ensure_space_member(space, user, *, access, source, added_by=None) -> SpaceMember:
    """Idempotent `SpaceMember` yozuvi; mavjud qator darajasini pasaytirmaydi."""
    row, created = SpaceMember.objects.get_or_create(
        space=space,
        user=user,
        defaults={"access": access, "source": source, "added_by": added_by},
    )
    return row


# --- space members (PM biriktiruvi, docs/DESIGN_PERMISSIONS.md §D.6) ---------


def resolve_space_candidates(space, user_ids):
    """`user_id` → `User`, faqat shu workspace a'zolari (§B.4 invarianti).

    Bittasi ham a'zo bo'lmasa **400** — `404` EMAS: chaqiruvchi allaqachon
    bo'limni ko'rmoqda, demak "yo'q" emas "noto'g'ri" javobi to'g'ri (§D.6).
    """
    wanted = [str(uid) for uid in user_ids]
    if not wanted:
        return {}
    rows = WorkspaceMember.objects.select_related("user").filter(
        workspace_id=space.workspace_id, user_id__in=wanted
    )
    found = {str(m.user_id): m.user for m in rows}
    bad = [uid for uid in wanted if uid not in found]
    if bad:
        raise ValidationError(
            {"user_id": [f"Ish maydoni a'zosi emas: {', '.join(sorted(bad))}."]}
        )
    return found


def _guard_last_manager(space, losing_user_ids):
    """Yopiq bo'lim boshqaruvsiz qolmasin (§D.6 `last_manager`).

    Faqat **yopiq** bo'limga tegishli: ochiq bo'limni workspace admini baribir
    boshqara oladi, yopiq bo'lim esa menejersiz qolsa hech kim a'zo qo'sha
    olmaydi va bo'lim qulflanib qoladi.
    """
    if not space.is_private:
        return
    losing = {str(uid) for uid in losing_user_ids}
    managers = {
        str(uid)
        for uid in SpaceMember.objects.filter(
            space=space, access=SpaceAccess.MANAGER
        ).values_list("user_id", flat=True)
    }
    if managers and not (managers - losing):
        raise Conflict(
            "Yopiq bo'limning oxirgi menejerini olib tashlab bo'lmaydi.",
            details={"reason": "last_manager"},
        )


def _revoke(space, user_id):
    """`access.revoked` — huquq pasayganda ochiq WS soketlarini xabardor qiladi."""
    workspace_id = space.workspace_id
    transaction.on_commit(
        lambda: events.emit_access_revoked(
            user_id, workspace_id=workspace_id, space_id=space.id
        )
    )


@transaction.atomic
def add_space_member(space, *, user_id, access, actor=None) -> SpaceMember:
    user = resolve_space_candidates(space, [user_id])[str(user_id)]
    if SpaceMember.objects.filter(space=space, user=user).exists():
        raise Conflict("Bu foydalanuvchi allaqachon bo'lim a'zosi.")
    row = SpaceMember.objects.create(
        space=space,
        user=user,
        access=access,
        source=SpaceMemberSource.MANUAL,
        added_by=actor,
    )
    if access == SpaceAccess.VIEWER:
        _revoke(space, user.id)
    return row


@transaction.atomic
def update_space_member(row, *, access, actor=None) -> SpaceMember:
    space = row.space
    if row.access == SpaceAccess.MANAGER and access != SpaceAccess.MANAGER:
        _guard_last_manager(space, [row.user_id])
    if row.access == access:
        return row
    downgraded = access == SpaceAccess.VIEWER
    row.access = access
    row.added_by = row.added_by or actor
    row.save(update_fields=["access", "added_by", "updated_at"])
    if downgraded:
        _revoke(space, row.user_id)
    return row


@transaction.atomic
def remove_space_member(row) -> None:
    space = row.space
    _guard_last_manager(space, [row.user_id])
    user_id = row.user_id
    row.delete()
    _revoke(space, user_id)


@transaction.atomic
def bulk_space_members(space, *, add, remove, actor=None) -> dict:
    """§D.6 bulk — bitta tranzaksiya, qisman muvaffaqiyat yo'q.

    `add` upsert: mavjud qatorda faqat `access` yangilanadi (`source` saqlanadi,
    ya'ni avtomatik biriktirilgan odam qo'lda tasdiqlanganda ham tarix yo'qolmaydi).
    """
    add = list(add or [])
    remove = [str(uid) for uid in (remove or [])]

    users = resolve_space_candidates(space, [row["user_id"] for row in add])
    existing = {
        str(m.user_id): m
        for m in SpaceMember.objects.select_related("user").filter(space=space)
    }

    missing = [uid for uid in remove if uid not in existing]
    if missing:
        raise ValidationError(
            {"remove": [f"Bo'lim a'zosi emas: {', '.join(sorted(missing))}."]}
        )

    # Har ikki amal ham menejerni yo'qotishi mumkin — guard bitta yig'ma ro'yxat
    # ustidan ishlaydi, aks holda "birini tushir, ikkinchisini o'chir" teshigi qolardi.
    losing_manager = set(remove)
    for row in add:
        uid = str(row["user_id"])
        current = existing.get(uid)
        if (
            current is not None
            and current.access == SpaceAccess.MANAGER
            and row["access"] != SpaceAccess.MANAGER
        ):
            losing_manager.add(uid)
    _guard_last_manager(space, losing_manager)

    revoked = set()
    added = 0
    for payload in add:
        uid = str(payload["user_id"])
        access = payload["access"]
        current = existing.get(uid)
        if current is None:
            SpaceMember.objects.create(
                space=space,
                user=users[uid],
                access=access,
                source=SpaceMemberSource.MANUAL,
                added_by=actor,
            )
            added += 1
            if access == SpaceAccess.VIEWER:
                revoked.add(uid)
        elif current.access != access:
            if access == SpaceAccess.VIEWER:
                revoked.add(uid)
            current.access = access
            current.added_by = current.added_by or actor
            current.save(update_fields=["access", "added_by", "updated_at"])

    removed = 0
    if remove:
        SpaceMember.objects.filter(space=space, user_id__in=remove).delete()
        removed = len(remove)
        revoked.update(remove)

    for uid in revoked:
        _revoke(space, uid)
    return {"added": added, "removed": removed}


@transaction.atomic
def create_space(workspace, actor, *, name, description="", color=None, icon="",
                 is_private=False, space_id=None) -> Space:
    if Space.objects.filter(workspace=workspace, name__iexact=name.strip()).exists():
        raise Conflict("A space with this name already exists in the workspace.")
    space_id = check_client_id(
        Space, space_id, scope=Space.objects.filter(workspace=workspace)
    )
    space = Space.objects.create(
        id=space_id or uuid.uuid4(),
        workspace=workspace,
        name=name.strip(),
        description=description or "",
        color=color or "#7B68EE",
        icon=icon or "",
        is_private=is_private,
        position=next_position(Space.objects.filter(workspace=workspace)),
        created_by=actor,
    )
    status_set = StatusSet.objects.create(space=space, name="Standart")
    seed_default_statuses(status_set)
    # §B.6 — yaratuvchi bo'limning menejeri (PM) bo'ladi.
    if actor is not None:
        ensure_space_member(
            space,
            actor,
            access=SpaceAccess.MANAGER,
            source=SpaceMemberSource.AUTO_CREATOR,
            added_by=actor,
        )
    return space


def _visibility_snapshot(space, *, is_private) -> set:
    """`is_private` shu qiymatda bo'lganda bo'limni KIM ko'radi (user id'lari).

    Ikki so'rov: bo'lim a'zolari + ish maydoni a'zolari. Ruxsat matritsasi
    keshdan keladi, shuning uchun a'zolar soniga qarab so'rov ko'paymaydi.
    `space_access_of()` ning per-membership keshi oldindan to'ldiriladi.
    """
    from apps.core.access import space_is_visible

    probe = Space(id=space.id, workspace_id=space.workspace_id, is_private=is_private)
    explicit = dict(
        SpaceMember.objects.filter(space=space).values_list("user_id", "access")
    )
    attr = f"_space_access_{space.pk}"
    seen = set()
    for member in WorkspaceMember.objects.filter(
        workspace_id=space.workspace_id
    ).select_related("workspace", "user"):
        setattr(member, attr, explicit.get(member.user_id))
        if space_is_visible(member, probe):
            seen.add(member.user_id)
    return seen


@transaction.atomic
def set_space_visibility(space, *, is_private, actor=None) -> Space:
    """`is_private` — bo'limning CHEGARASI, oddiy atribut emas (§B.5).

    Uni `queryset.update()` bilan o'zgartirish uch narsani o'tkazib yuboradi,
    va uchalasi ham shu yerda bajariladi:

    1. **Backfill.** Yopiq bo'lim menejersiz qolmasin — yaratuvchi
       `manager` sifatida biriktiriladi (§B.6), aks holda hech kim unga a'zo
       qo'sha olmaydi va bo'lim qulflanib qoladi.
    2. **`permissions_version`.** Klient `my-permissions/` javobidagi
       `spaces` ro'yxatiga tayanadi; versiya oshmasa u eskirib qoladi
       (`permission.updated` ham shu yerdan chiqadi).
    3. **`access.revoked`.** Ko'rinishni YO'QOTGAN har bir odamning ochiq
       soketi `connect()` da bir marta tekshirilgan — xabarsiz u endi yopiq
       bo'lgan bo'lim freymlarini oqizishda davom etardi (Y-1 bilan bir xil
       sinf).
    """
    if space.is_private == is_private:
        return space
    before = _visibility_snapshot(space, is_private=space.is_private)
    after = _visibility_snapshot(space, is_private=is_private)

    space.is_private = is_private
    space.save(update_fields=["is_private", "updated_at"])

    if is_private and space.created_by_id is not None:
        ensure_space_member(
            space,
            space.created_by,
            access=SpaceAccess.MANAGER,
            source=SpaceMemberSource.AUTO_CREATOR,
            added_by=actor,
        )

    from apps.core.access import bump_permissions_version

    bump_permissions_version(space.workspace, actor=actor)
    for user_id in sorted(before - after, key=str):
        _revoke(space, user_id)
    return space


@transaction.atomic
def bootstrap_workspace(user, *, name, description="", color=None, workspace_id=None) -> Workspace:
    """DATA_MODEL.md section 11: workspace + owner membership + "Jamoa bo'limi"
    space + default status set + an empty "Boshlash" list.

    The list ships empty on purpose: a brand-new account should start from zero
    rather than from placeholder tasks it has to clean up first.
    """
    # Doira = chaqiruvchi allaqachon a'zo bo'lgan ish maydonlari; begona UUID
    # 409 bermaydi (global mavjudlik orakuli), server yangi id ajratadi.
    workspace_id = check_client_id(
        Workspace, workspace_id, scope=Workspace.objects.filter(members__user=user)
    )
    workspace = Workspace.objects.create(
        id=workspace_id or uuid.uuid4(),
        name=name.strip(),
        slug=generate_slug(name),
        description=description or "",
        color=color or "#7B68EE",
        owner=user,
        created_by=user,
        member_count=1,
    )
    WorkspaceMember.objects.create(workspace=workspace, user=user, role=WorkspaceRole.OWNER)
    ensure_role_permissions(workspace)  # §B.6 — default matritsani materializatsiya

    space = Space.objects.create(
        workspace=workspace,
        name="Jamoa bo'limi",
        position="n",
        created_by=user,
    )
    ensure_space_member(
        space,
        user,
        access=SpaceAccess.MANAGER,
        source=SpaceMemberSource.AUTO_CREATOR,
        added_by=user,
    )
    status_set = StatusSet.objects.create(space=space, name="Standart")
    seed_default_statuses(status_set)

    TaskList.objects.create(
        space=space, folder=None, name="Boshlash", position="n", created_by=user
    )
    return workspace


def refresh_member_count(workspace):
    workspace.member_count = WorkspaceMember.objects.filter(workspace=workspace).count()
    workspace.save(update_fields=["member_count", "updated_at"])


@transaction.atomic
def remove_workspace_member(membership) -> None:
    """A'zolikni + shu ish maydonidagi biriktirilgan/kuzatuvchi qatorlarini o'chiradi.

    HAMMASI BITTA TRANZAKSIYADA. Bu yerda beshta yozish bor (assignee, watcher,
    SpaceMember, membership, `member_count`); ular alohida commit bo'lsa
    o'rtada yiqilish yarim o'chirilgan a'zoni qoldiradi — masalan `SpaceMember`
    yashab qolib, §B.4 invariantini buzadi ("SpaceMember hech qachon o'zi
    bog'liq bo'lgan WorkspaceMember'dan uzoq yashamaydi").

    Ochiq `atomic` bloki `transaction.on_commit` uchun ham SHART: blok
    bo'lmasa callback DARHOL ishlaydi, ya'ni hali commit bo'lmagan o'chirish
    haqida `access.revoked` yuboriladi.
    """
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
    SpaceMember.objects.filter(user=membership.user, space__workspace=workspace).delete()
    user_id = membership.user_id
    workspace_id = workspace.id
    membership.delete()
    refresh_member_count(workspace)
    # REST endi 404 qaytaradi, lekin ochiq WebSocket soketi a'zolikni faqat
    # `connect()` da bir marta tekshirgan — xabarsiz u chiqarilgan odamga
    # `task.*`/`comment.*` freymlarini oqizishda davom etardi. `space_id=None`
    # ikkala consumer'ni ham (workspace va list) 4403 bilan yopadi.
    transaction.on_commit(
        lambda: events.emit_access_revoked(user_id, workspace_id=workspace_id, space_id=None)
    )


def _emit_list_updated_on_commit(task_list, *, actor=None, client_id=None):
    """`list.updated` FAQAT commit'dan keyin — rollback bo'lgan o'zgarish
    hech qachon e'lon qilinmasin."""
    transaction.on_commit(
        lambda: events.emit_list_updated(task_list, actor=actor, client_id=client_id)
    )


def refresh_list_counts(task_list, *, actor=None, client_id=None, emit=False):
    from apps.tasks.models import Task

    old = (task_list.task_count, task_list.open_task_count)
    task_list.task_count = Task.objects.filter(list=task_list, archived=False).count()
    task_list.open_task_count = (
        Task.objects.filter(list=task_list, archived=False)
        .exclude(status__type=StatusType.CLOSED)
        .count()
    )
    task_list.save(update_fields=["task_count", "open_task_count", "updated_at"])
    if emit and old != (task_list.task_count, task_list.open_task_count):
        _emit_list_updated_on_commit(task_list, actor=actor, client_id=client_id)


# --- hard deletes ------------------------------------------------------------
# Django's deletion collector raises ProtectedError for Task.status even when
# the tasks are part of the same cascade, so container deletes hard-delete the
# tasks first (docs/DATA_MODEL.md section 10 deletion matrix).


def _hard_delete_tasks(task_filter):
    from apps.tasks.models import Task

    Task.all_objects.filter(**task_filter).hard_delete()


@transaction.atomic
def hard_delete_workspace(workspace):
    _hard_delete_tasks({"list__space__workspace": workspace})
    workspace.delete()


@transaction.atomic
def hard_delete_space(space):
    _hard_delete_tasks({"list__space": space})
    space.delete()


@transaction.atomic
def hard_delete_folder(folder):
    _hard_delete_tasks({"list__folder": folder})
    folder.delete()


@transaction.atomic
def hard_delete_list(task_list):
    _hard_delete_tasks({"list": task_list})
    task_list.delete()


# --- invitations ------------------------------------------------------------


def create_invitation(workspace, actor, *, email, role) -> Invitation:
    from django.conf import settings

    email = email.lower()
    if WorkspaceMember.objects.filter(workspace=workspace, user__email__iexact=email).exists():
        raise Conflict("This user is already a member of the workspace.")
    if Invitation.objects.filter(
        workspace=workspace, email__iexact=email, status="pending"
    ).exists():
        raise Conflict("A pending invitation for this email already exists.")
    now = timezone.now()
    return Invitation.objects.create(
        workspace=workspace,
        email=email,
        role=role,
        token=secrets.token_urlsafe(32),
        invited_by=actor,
        expires_at=now + timedelta(days=settings.INVITATION_TTL_DAYS),
        sent_count=1,
        last_sent_at=now,
    )


@transaction.atomic
def accept_invitation(invitation, user):
    """`POST invitations/accept/` — a'zolik + taklif holati BITTA tranzaksiyada.

    Ikkiga bo'linsa: a'zolik yaratilib taklif `pending` qolsa token qayta
    ishlatilardi; teskarisida esa taklif "qabul qilindi" bo'lib a'zolik
    yaratilmasdi va odam hech qachon kira olmasdi.
    """
    if WorkspaceMember.objects.filter(workspace=invitation.workspace, user=user).exists():
        raise Conflict("You are already a member of this workspace.")
    member = WorkspaceMember.objects.create(
        workspace=invitation.workspace,
        user=user,
        role=invitation.role,
        invited_by=invitation.invited_by,
    )
    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.accepted_by = user
    invitation.save(update_fields=["status", "accepted_at", "accepted_by", "updated_at"])
    refresh_member_count(invitation.workspace)
    return member


# --- list move (fractional position) ----------------------------------------


def _list_scope_qs(space, folder):
    if folder is not None:
        return TaskList.objects.filter(folder=folder)
    return TaskList.objects.filter(space=space, folder__isnull=True)


def _sibling_position(qs, sibling_id, exclude_pk):
    if sibling_id is None:
        return None
    sibling = qs.exclude(pk=exclude_pk).filter(pk=sibling_id).first()
    if sibling is None:
        raise PositionConflict("Neighbour list is not in the destination scope.")
    return sibling.position


@transaction.atomic
def move_list(task_list, *, folder_id, before_id, after_id, actor, client_id=None) -> TaskList:
    folder = None
    if folder_id is not None:
        folder = Folder.objects.filter(pk=folder_id, space_id=task_list.space_id).first()
        if folder is None:
            raise ValidationError({"folder_id": ["Folder must belong to the same space."]})

    scope = _list_scope_qs(task_list.space, folder)
    for attempt in range(3):
        prev_pos = _sibling_position(scope, before_id, task_list.pk)
        next_pos = _sibling_position(scope, after_id, task_list.pk)
        if prev_pos is not None and next_pos is not None and prev_pos >= next_pos:
            raise PositionConflict()
        if prev_pos is None and next_pos is None:
            others = scope.exclude(pk=task_list.pk)
            new_pos = next_position(others) if others.exists() else "n"
        else:
            new_pos = midstring(prev_pos, next_pos)
        try:
            with transaction.atomic():
                task_list.folder = folder
                task_list.position = new_pos
                task_list.save(update_fields=["folder", "position", "updated_at"])
            break
        except IntegrityError:
            if attempt == 2:
                raise PositionConflict("Could not obtain a stable position after 3 attempts.")
            continue
    _emit_list_updated_on_commit(task_list, actor=actor, client_id=client_id)
    return task_list


@transaction.atomic
def update_list(task_list, validated_data, *, actor, client_id=None) -> TaskList:
    """`PATCH lists/{id}/` — yozish + `list.updated`, bitta tranzaksiyada.

    Nega view'da emas (CLAUDE.md / `apps/realtime/events.py` qoidasi): view
    hech qanday `atomic` ochmagani uchun u yerdagi emit commit'dan OLDIN
    ketardi. Keyingi commit yiqilsa mijozlar hech qachon sodir bo'lmagan
    nomni ko'rsatib turaverardi. `on_commit` esa faqat haqiqatan yozilgan
    o'zgarishni e'lon qiladi.
    """
    for field, value in validated_data.items():
        setattr(task_list, field, value)
    task_list.save()
    _emit_list_updated_on_commit(task_list, actor=actor, client_id=client_id)
    return task_list


@transaction.atomic
def detach_folder(folder):
    """`DELETE folders/{id}/?strategy=detach` — ko'chirish + o'chirish, atomik.

    Ikki qadam alohida commit bo'lsa, ikkinchisi yiqilganda ro'yxatlar bo'lim
    ildizida, jild esa hali o'rnida qolardi — ya'ni "detach" yarim bajarilgan
    holat. `CASCADE` tufayli teskari tartib esa ro'yxatlarni butunlay
    yo'qotadi, shuning uchun tartib ham muhim.
    """
    detach_folder_lists(folder)
    folder.delete()


@transaction.atomic
def detach_folder_lists(folder):
    """Move the folder's lists to the space root with fresh end-of-scope positions."""
    root = TaskList.objects.filter(space=folder.space, folder__isnull=True)
    last = root.order_by("-position").values_list("position", flat=True).first()
    for task_list in folder.lists.order_by("position", "name"):
        last = midstring(last, None)
        task_list.folder = None
        task_list.position = last
        task_list.save(update_fields=["folder", "position", "updated_at"])


# --- status sets -------------------------------------------------------------


def _repoint_tasks(tasks_by_old_status, mapping, new_statuses_by_id, *, actor, client_id):
    """Re-point tasks whose status disappeared. One task.updated per task.
    Positions are kept; only a directly-colliding key is nudged (never a renumber)."""
    from apps.tasks.models import Task

    touched_lists = set()
    for old_status_id, tasks in tasks_by_old_status.items():
        target = new_statuses_by_id[str(mapping[str(old_status_id)])]
        for task in tasks:
            desired = task.position
            while (
                Task.objects.filter(
                    list_id=task.list_id, status=target, position=desired
                )
                .exclude(pk=task.pk)
                .exists()
            ):
                nxt = (
                    Task.objects.filter(
                        list_id=task.list_id, status=target, position__gt=desired
                    )
                    .exclude(pk=task.pk)
                    .order_by("position")
                    .values_list("position", flat=True)
                    .first()
                )
                desired = midstring(desired, nxt)
            task.status = target
            task.position = desired
            if target.type == StatusType.CLOSED:
                if task.completed_at is None:
                    task.completed_at = timezone.now()
            else:
                task.completed_at = None
            task.save(update_fields=["status", "position", "completed_at", "updated_at"])
            touched_lists.add(task.list_id)
            if not task.is_deleted:
                events.emit_task_event("task.updated", task, actor=actor, client_id=client_id)
    for list_id in touched_lists:
        refresh_list_counts(TaskList.objects.get(pk=list_id))


def _validate_mapping(referenced_old, new_ids, mapping):
    missing = [str(s.id) for s in referenced_old if str(s.id) not in mapping]
    bad_targets = [
        str(old_id) for old_id, new_id in mapping.items() if str(new_id) not in new_ids
    ]
    if missing or bad_targets:
        raise Conflict(
            "status_mapping must cover every status still referenced by tasks.",
            details={
                "status_mapping": {
                    "missing": missing,
                    "invalid_targets": bad_targets,
                }
            },
        )


@transaction.atomic
def replace_status_set(*, space=None, task_list=None, data, actor, client_id=None) -> StatusSet:
    """PUT spaces/{id}/status-set/ or PUT lists/{id}/status-set/ (contract section 9)."""
    from apps.tasks.models import Task

    statuses_data = data["statuses"]
    mapping = {str(k): str(v) for k, v in (data.get("status_mapping") or {}).items()}

    creating_override = False
    if task_list is not None:
        status_set = StatusSet.objects.filter(list=task_list).first()
        if status_set is None:
            creating_override = True
            status_set = StatusSet.objects.create(
                list=task_list, name=data.get("name") or "Standart"
            )
        affected_tasks = Task.all_objects.filter(list=task_list)
        old_reference_statuses = (
            list(task_list.space.status_set.statuses.all())
            if creating_override
            else list(status_set.statuses.all())
        )
    else:
        status_set = space.status_set
        affected_tasks = Task.all_objects.filter(
            list__space=space, list__status_set__isnull=True
        )
        old_reference_statuses = list(status_set.statuses.all())

    if data.get("name"):
        status_set.name = data["name"]
        status_set.save(update_fields=["name", "updated_at"])

    existing = {str(s.id): s for s in status_set.statuses.all()}
    sent_ids = {str(s["id"]) for s in statuses_data if s.get("id")}
    kept = [existing[i] for i in sent_ids if i in existing]
    removed = [s for i, s in existing.items() if i not in sent_ids]

    # Which old statuses are still referenced by tasks but absent from the new set?
    referenced = [
        s
        for s in old_reference_statuses
        if (str(s.id) not in sent_ids or creating_override)
        and affected_tasks.filter(status=s).exists()
    ]
    # Pass 1: park kept rows out of the way (order offset, temp names, clear default).
    for i, status in enumerate(kept):
        status.order = 1000 + i
        status.is_default = False
        status.name = f"__tmp_{i}_{uuid.uuid4().hex[:8]}"
        status.save(update_fields=["order", "is_default", "name", "updated_at"])

    # Create brand-new statuses (final order assigned from array index).
    new_statuses_by_id = {}
    final_rows = []
    for index, sdata in enumerate(statuses_data):
        sid = str(sdata["id"]) if sdata.get("id") else None
        if sid and sid in existing:
            row = existing[sid]
        else:
            if sid:
                sid = check_client_id(
                    Status, sid, scope=Status.objects.filter(status_set=status_set)
                )
            row = Status(id=sid or uuid.uuid4(), status_set=status_set)
        row.name = sdata["name"].strip()
        row.color = sdata.get("color") or "#87909E"
        row.type = sdata["type"]
        row.order = index
        row.is_default = bool(sdata.get("is_default"))
        final_rows.append(row)
        new_statuses_by_id[str(row.id)] = row

    _validate_mapping(referenced, set(new_statuses_by_id), mapping)

    # Re-point tasks off removed/foreign statuses BEFORE deleting (Task.status is PROTECT).
    # Targets must exist in the DB first, so save created rows with parked order.
    for i, row in enumerate(final_rows):
        if row._state.adding:
            row.order = 2000 + i
            row.is_default = False
            row.save()

    tasks_by_old = {
        str(s.id): list(affected_tasks.filter(status=s)) for s in referenced
    }
    if tasks_by_old:
        _repoint_tasks(tasks_by_old, mapping, new_statuses_by_id, actor=actor, client_id=client_id)

    for status in removed:
        status.delete()

    # Pass 2: final order / names / flags.
    for index, sdata in enumerate(statuses_data):
        row = final_rows[index]
        row.name = sdata["name"].strip()
        row.color = sdata.get("color") or "#87909E"
        row.type = sdata["type"]
        row.order = index
        row.is_default = bool(sdata.get("is_default"))
        row.save(update_fields=["name", "color", "type", "order", "is_default", "updated_at"])

    status_set.refresh_from_db()
    return status_set


@transaction.atomic
def remove_list_status_set(task_list, *, status_mapping, actor, client_id=None) -> StatusSet:
    """DELETE lists/{id}/status-set/ — map override statuses back to the space's."""
    from apps.tasks.models import Task

    override = StatusSet.objects.filter(list=task_list).first()
    if override is None:
        raise Conflict("This list has no status-set override.")
    space_set = task_list.space.status_set
    mapping = {str(k): str(v) for k, v in (status_mapping or {}).items()}
    space_statuses = {str(s.id): s for s in space_set.statuses.all()}

    affected_tasks = Task.all_objects.filter(list=task_list)
    referenced = [
        s for s in override.statuses.all() if affected_tasks.filter(status=s).exists()
    ]
    _validate_mapping(referenced, set(space_statuses), mapping)

    tasks_by_old = {str(s.id): list(affected_tasks.filter(status=s)) for s in referenced}
    if tasks_by_old:
        _repoint_tasks(tasks_by_old, mapping, space_statuses, actor=actor, client_id=client_id)

    override.delete()
    task_list.refresh_from_db()
    return space_set
