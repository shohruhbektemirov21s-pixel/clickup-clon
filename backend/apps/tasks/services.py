"""Task services — the write path. Realtime events are emitted from here only."""

import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.enums import (
    CLOSED_STATUSES,
    ActivityVerb,
    SpaceAccess,
    SpaceMemberSource,
    TaskStatus,
    WatcherSource,
)
from apps.core.exceptions import Conflict, PositionConflict
from apps.core.ordering import MAX_LEN_BEFORE_REBALANCE, evenly_spaced, midstring
from apps.realtime import events
from apps.tasks.models import (
    Tag,
    Task,
    TaskActivity,
    TaskAssignee,
    TaskAttachment,
    TaskTag,
    TaskWatcher,
)
from apps.workspaces.models import TaskList, WorkspaceMember
from apps.workspaces.services import check_client_id, ensure_space_member, refresh_list_counts

# ------------------------------------------------------------------ activity log


def display_name(user) -> str | None:
    """Human-readable snapshot of a user, frozen into the history row."""
    if user is None:
        return None
    return user.full_name.strip() or user.email


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def activity(task, actor, verb, *, from_value=None, to_value=None, **metadata):
    """Build (do NOT save) one history row; callers bulk_create the batch."""
    return TaskActivity(
        task=task,
        actor=actor,
        verb=verb,
        from_value=from_value,
        to_value=to_value,
        metadata=metadata,
    )


def log_activities(rows):
    """One INSERT for the whole batch — several verbs often fire together."""
    if rows:
        TaskActivity.objects.bulk_create(rows)
    return rows


def resolve_status(value) -> str:
    """Status kodini tekshiradi; `None` → sukut (`todo`).

    Status endi ro'yxatga bog'liq emas, shuning uchun "bu status shu
    ro'yxatga tegishli emas" holati YO'Q. Noma'lum kod — oddiy 400
    (`validation_error`), aynan serializer bergan shakl bilan bir xil, ya'ni
    `PATCH tasks/{id}/` va `PATCH tasks/{id}/move/` bir xil javob beradi.
    """
    if value is None:
        return TaskStatus.TODO.value
    value = str(value)
    if value not in TaskStatus.values:
        allowed = ", ".join(TaskStatus.values)
        raise ValidationError(
            {"status": [f"Noma'lum status kodi: {value}. Ruxsat etilganlari: {allowed}."]}
        )
    return value


def _validate_assignees(task_list, assignee_ids):
    workspace_id = task_list.space.workspace_id
    member_ids = set(
        str(u)
        for u in WorkspaceMember.objects.filter(
            workspace_id=workspace_id, user_id__in=assignee_ids
        ).values_list("user_id", flat=True)
    )
    bad = [str(a) for a in assignee_ids if str(a) not in member_ids]
    if bad:
        raise ValidationError(
            {"assignee_ids": [f"Users are not members of this workspace: {', '.join(bad)}."]}
        )


def _validate_tags(task_list, tag_ids):
    workspace_id = task_list.space.workspace_id
    found = set(
        str(t)
        for t in Tag.objects.filter(workspace_id=workspace_id, id__in=tag_ids).values_list(
            "id", flat=True
        )
    )
    bad = [str(t) for t in tag_ids if str(t) not in found]
    if bad:
        raise ValidationError(
            {"tag_ids": [f"Tags do not belong to this workspace: {', '.join(bad)}."]}
        )


def add_watcher(task, user, source):
    _, created = TaskWatcher.objects.get_or_create(
        task=task, user=user, defaults={"source": source}
    )
    return created


def _grant_assignee_space_access(space, users, actor):
    """AD-7 — biriktirilgan odam o'z ishini KO'RA olishi shart.

    Yopiq bo'limda `SpaceMember` qatorisiz vazifa unga `404` bo'lardi, shuning
    uchun qator avtomatik yaratiladi (`source=auto_assignee`, migratsiya 0004
    dagi backfill qoidasi bilan bir xil).

    **Nega faqat ko'rmayotganlarga?** `viewer` §B.5 bo'yicha "eng past huquq
    g'olib": qator bo'lim ichidagi HAR QANDAY yozishni kesadi. Uni bo'limni
    allaqachon ko'rayotgan odamga yozish AD-7 ni maqsadiga qarshi ishlatgan
    bo'lardi — o'ziga biriktirilgan vazifani tahrirlay olmay qolardi
    (`task.update_assigned` → 403). Shuning uchun grant faqat kirish
    YETISHMAYOTGAN odamga beriladi: u yutadi, hech kim yo'qotmaydi.

    **AppSec cheklovi.** `SpaceMember` qatorini yozish — bu aslida
    `space.manage_members` amali (§D.6). Uni biriktirishning yon ta'siri
    sifatida HAR QANDAY chaqiruvchiga ochib qo'yish yopiq bo'limga kirishni
    tarqatish kanaliga aylanardi: biriktira olgan odam istalganini bo'lim
    o'quvchisiga aylantirib, `space.manage_members` (admin-only) ni chetlab
    o'tardi. Shuning uchun grant faqat aktyorning o'zi `space.manage_members`
    ga ega bo'lganda yoziladi; aks holda `400` — "avval odamni bo'limga
    qo'shing" (fail-closed, kirish jimgina kengaymaydi).
    """
    from apps.core.access import get_membership, has_space_perm, space_is_visible

    if not users:
        return
    memberships = WorkspaceMember.objects.select_related("user", "workspace").filter(
        workspace_id=space.workspace_id, user_id__in=[u.id for u in users]
    )
    actor_membership = None
    for membership in memberships:
        # `space_is_visible` mavjud `SpaceMember` qatorini ham hisobga oladi,
        # ya'ni bu tekshiruv idempotentlikni ham ta'minlaydi.
        if space_is_visible(membership, space):
            continue
        if actor_membership is None and actor is not None:
            actor_membership = get_membership(actor, space.workspace_id)
        if actor_membership is None or not has_space_perm(
            actor_membership, space, "space.manage_members"
        ):
            raise ValidationError(
                {
                    "assignee_ids": [
                        "Bu foydalanuvchi bo'limni ko'rmaydi; avval uni bo'limga qo'shing."
                    ]
                }
            )
        ensure_space_member(
            space,
            membership.user,
            access=SpaceAccess.VIEWER,
            source=SpaceMemberSource.AUTO_ASSIGNEE,
            added_by=actor,
        )


def _set_assignees(task, assignee_ids, actor):
    """Returns (added, removed) User rows so the caller can log the history."""
    wanted = [uuid.UUID(str(a)) for a in assignee_ids]
    current = set(task.task_assignees.values_list("user_id", flat=True))
    to_add = [a for a in wanted if a not in current]
    to_remove = [c for c in current if c not in set(wanted)]
    users = {u.id: u for u in User.objects.filter(id__in=set(to_add) | set(to_remove))}
    if to_remove:
        TaskAssignee.objects.filter(task=task, user_id__in=to_remove).delete()
    for user_id in to_add:
        TaskAssignee.objects.create(task=task, user_id=user_id, assigned_by=actor)
        # assignment always (re-)adds the watcher
        TaskWatcher.objects.get_or_create(
            task=task, user_id=user_id, defaults={"source": WatcherSource.AUTO_ASSIGNEE}
        )
    _grant_assignee_space_access(task.list.space, [users[u] for u in to_add if u in users], actor)
    added = [users[u] for u in to_add if u in users]
    removed = [users[u] for u in to_remove if u in users]
    _notify_assigned(task, added, actor)
    return added, removed


def _notify_assigned(task, added, actor):
    """Yangi biriktirilganlarga bildirishnoma (o'zini biriktirgan odam bundan mustasno).

    Faqat QO'SHILGANLAR uchun: biriktirishni olib tashlash "endi sizga
    tegishli emas" degan xabarni talab qilmaydi va ro'yxatni shovqinga
    to'ldirardi.
    """
    if not added:
        return
    from apps.notifications.services import NotificationKind, notify_many

    workspace = task.list.space.workspace
    notify_many(
        added,
        actor=actor,
        workspace=workspace,
        kind=NotificationKind.TASK_ASSIGNED,
        title="Sizga yangi vazifa biriktirildi",
        body=task.title,
        url=f"/w/{workspace.id}/l/{task.list_id}?task={task.id}",
    )


def _assignee_activities(task, actor, added, removed):
    rows = []
    for user in removed:
        rows.append(
            activity(
                task,
                actor,
                ActivityVerb.ASSIGNEE_REMOVED,
                from_value=display_name(user),
                user_id=str(user.id),
            )
        )
    for user in added:
        rows.append(
            activity(
                task,
                actor,
                ActivityVerb.ASSIGNEE_ADDED,
                to_value=display_name(user),
                user_id=str(user.id),
            )
        )
    return rows


def refresh_tag_usage(tag_ids):
    for tag in Tag.objects.filter(id__in=tag_ids):
        tag.usage_count = TaskTag.objects.filter(tag=tag).count()
        tag.save(update_fields=["usage_count", "updated_at"])


def _set_tags(task, tag_ids):
    wanted = [uuid.UUID(str(t)) for t in tag_ids]
    current = set(task.task_tags.values_list("tag_id", flat=True))
    to_add = [t for t in wanted if t not in current]
    to_remove = [c for c in current if c not in set(wanted)]
    if to_remove:
        TaskTag.objects.filter(task=task, tag_id__in=to_remove).delete()
    for tag_id in to_add:
        TaskTag.objects.create(task=task, tag_id=tag_id)
    refresh_tag_usage(list(set(wanted) | current))


def _column_qs(list_id, status, exclude_pk=None):
    qs = Task.objects.filter(list_id=list_id, status=status)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs


def _end_of_column_position(list_id, status, exclude_pk=None) -> str:
    last = (
        _column_qs(list_id, status, exclude_pk)
        .order_by("-position")
        .values_list("position", flat=True)
        .first()
    )
    return midstring(last, None)


def _apply_completed_at(task, status):
    """`completed_at` YAGONA yozuvchisi — status yopiq to'plamga kirdi/chiqdi."""
    if status in CLOSED_STATUSES:
        if task.completed_at is None:
            task.completed_at = timezone.now()
    else:
        task.completed_at = None


def _status_activities(task, actor, previous, status):
    """status_changed, plus a completed row when the task lands in a closed status.

    `from_value`/`to_value` endi KODNI saqlaydi (`todo`, `done`, ...), o'zbekcha
    nomni emas: yorliq display qatlamida (`STATUS_LABEL`) yashaydi, tarix esa
    tarjima o'zgarganda ham o'qilishi kerak.
    """
    rows = [
        activity(
            task,
            actor,
            ActivityVerb.STATUS_CHANGED,
            from_value=previous or None,
            to_value=status,
            from_status=previous or None,
            to_status=status,
        )
    ]
    closed_before = previous in CLOSED_STATUSES
    if status in CLOSED_STATUSES and not closed_before:
        rows.append(activity(task, actor, ActivityVerb.COMPLETED, to_value=status))
    return rows


def _nudged_position(list_id, status, exclude_pk, desired):
    """Keep `desired` unless it collides in the destination column; nudge one row.

    Ustun/status ATAYLAB alohida argument: ko'chirishda `task.list` xotirada
    allaqachon manzilga o'zgartirilgan bo'lishi mumkin, DB'dagi holat esa hali
    manba ustuni bo'lib turadi.
    """
    while _column_qs(list_id, status, exclude_pk=exclude_pk).filter(position=desired).exists():
        nxt = (
            _column_qs(list_id, status, exclude_pk=exclude_pk)
            .filter(position__gt=desired)
            .order_by("position")
            .values_list("position", flat=True)
            .first()
        )
        desired = midstring(desired, nxt)
    return desired


@transaction.atomic
def create_task(task_list, data, actor, client_id=None) -> Task:
    check_client_id(Task, data.get("id"))
    status = resolve_status(data.get("status"))
    assignee_ids = data.get("assignee_ids") or []
    tag_ids = data.get("tag_ids") or []
    if assignee_ids:
        _validate_assignees(task_list, assignee_ids)
    if tag_ids:
        _validate_tags(task_list, tag_ids)

    task = Task(
        id=data.get("id") or uuid.uuid4(),
        list=task_list,
        status=status,
        title=data["title"],
        description_html=data.get("description_html", ""),
        description_json=data.get("description_json"),
        priority=data.get("priority", "none"),
        due_date=data.get("due_date"),
        start_date=data.get("start_date"),
        time_estimate_minutes=data.get("time_estimate_minutes"),
        created_by=actor,
        updated_by=actor,
    )
    _apply_completed_at(task, status)
    # `uniq_task_position_per_column` bilan poyga: boshqa yozuvchi ayni shu
    # kalitni oldindan olib qo'ygan bo'lishi mumkin. Qayta urinish oldida
    # KUTILMAYDI — bu funksiya `@transaction.atomic` ichida, ya'ni `sleep`
    # PostgreSQL'da ochiq tranzaksiya va olingan qulflarni ushlab turgan holda
    # uxlardi (boshqa yozuvchilarni bloklab). Kutishning keragi ham yo'q:
    # to'qnashuvga sabab bo'lgan qator ALLAQACHON commit qilingan (aks holda
    # `IntegrityError` bo'lmasdi), READ COMMITTED'da esa keyingi `SELECT` uni
    # ko'radi — ya'ni qayta urinish determinlashgan holda yangi kalit beradi,
    # backoff talab qiladigan tasodifiy raqobat emas.
    for attempt in range(3):
        task.position = _end_of_column_position(task_list.id, status)
        try:
            with transaction.atomic():
                task.save()
            break
        except IntegrityError:
            if attempt == 2:
                raise Conflict("Could not create the task; please retry.")

    add_watcher(task, actor, WatcherSource.AUTO_CREATOR)
    rows = [
        activity(
            task,
            actor,
            ActivityVerb.CREATED,
            to_value=task.title,
            status=status,
            list_name=task_list.name,
        )
    ]
    if assignee_ids:
        added, removed = _set_assignees(task, assignee_ids, actor)
        rows += _assignee_activities(task, actor, added, removed)
    if tag_ids:
        _set_tags(task, tag_ids)
    if status in CLOSED_STATUSES:
        rows.append(activity(task, actor, ActivityVerb.COMPLETED, to_value=status))
    log_activities(rows)

    refresh_list_counts(task_list, actor=actor, client_id=client_id, emit=True)
    events.emit_task_event("task.created", task, actor=actor, client_id=client_id)
    return task


@transaction.atomic
def update_task(task, data, actor, client_id=None) -> Task:
    task_list = task.list
    update_fields = {"updated_by", "updated_at"}
    status_changed = False
    rows = []

    if "status" in data and data["status"] is not None:
        status = resolve_status(data["status"])
        if status != task.status:
            previous = task.status
            task.status = status
            task.position = _nudged_position(
                task.list_id, status, task.pk, task.position
            )
            _apply_completed_at(task, status)
            update_fields |= {"status", "position", "completed_at"}
            status_changed = True
            rows += _status_activities(task, actor, previous, status)

    simple_fields = [
        "title",
        "description_html",
        "description_json",
        "priority",
        "due_date",
        "start_date",
        "time_estimate_minutes",
        "archived",
    ]
    logged_fields = {
        "title": (ActivityVerb.RENAMED, lambda v: v),
        "priority": (ActivityVerb.PRIORITY_CHANGED, lambda v: v),
        "due_date": (ActivityVerb.DUE_DATE_CHANGED, _iso),
    }
    for field in simple_fields:
        if field in data:
            before = getattr(task, field)
            setattr(task, field, data[field])
            update_fields.add(field)
            if field in logged_fields and before != data[field]:
                verb, render = logged_fields[field]
                rows.append(
                    activity(
                        task, actor, verb, from_value=render(before), to_value=render(data[field])
                    )
                )

    if "assignee_ids" in data:
        _validate_assignees(task_list, data["assignee_ids"])
        added, removed = _set_assignees(task, data["assignee_ids"], actor)
        rows += _assignee_activities(task, actor, added, removed)
    if "tag_ids" in data:
        _validate_tags(task_list, data["tag_ids"])
        _set_tags(task, data["tag_ids"])

    task.updated_by = actor
    task.save(update_fields=list(update_fields))
    log_activities(rows)

    if status_changed or "archived" in data:
        refresh_list_counts(task_list, actor=actor, client_id=client_id, emit=True)
    events.emit_task_event("task.updated", task, actor=actor, client_id=client_id)
    return task


@transaction.atomic
def soft_delete_task(task, actor, client_id=None):
    task.updated_by = actor
    task.save(update_fields=["updated_by", "updated_at"])
    task.delete()  # soft
    log_activities([activity(task, actor, ActivityVerb.DELETED, from_value=task.title)])
    refresh_list_counts(task.list, actor=actor, client_id=client_id, emit=True)
    events.emit_task_deleted(task, actor=actor, client_id=client_id)


@transaction.atomic
def restore_task(task, actor, client_id=None) -> Task:
    task.deleted_at = None
    task.updated_by = actor
    # restore may collide with a live task's position
    task.position = _nudged_position(task.list_id, task.status, task.pk, task.position)
    task.save(update_fields=["deleted_at", "updated_by", "position", "updated_at"])
    log_activities([activity(task, actor, ActivityVerb.RESTORED, to_value=task.title)])
    refresh_list_counts(task.list, actor=actor, client_id=client_id, emit=True)
    events.emit_task_event("task.updated", task, actor=actor, client_id=client_id)
    return task


def _neighbour_position(list_id, status, neighbour_id, moving_pk):
    if neighbour_id is None:
        return None
    row = (
        _column_qs(list_id, status, exclude_pk=moving_pk)
        .filter(pk=neighbour_id)
        .values_list("position", flat=True)
        .first()
    )
    if row is None:
        raise PositionConflict("Neighbour task is not in the destination column.")
    return row


@transaction.atomic
def rebalance_column(task_list, status):
    """Two-pass rewrite through an out-of-band prefix ("~" > "z")."""
    qs = (
        Task.objects.select_for_update()
        .filter(list=task_list, status=status)
        .order_by("position", "created_at")
    )
    tasks = list(qs)
    keys = evenly_spaced(len(tasks))
    for task, key in zip(tasks, keys):
        task.position = "~" + key
    Task.objects.bulk_update(tasks, ["position"])
    for task, key in zip(tasks, keys):
        task.position = key
    Task.objects.bulk_update(tasks, ["position"])


@transaction.atomic
def move_task(task, *, list_id, status, before_id, after_id, actor, client_id=None):
    """docs/DATA_MODEL.md section 8.5 — exactly one row is written, never a renumber
    (except an explicit rebalance, flagged in the response)."""
    target_list = (
        TaskList.objects.select_related("space").filter(pk=list_id).first()
    )
    if target_list is None or target_list.space.workspace_id != task.list.space.workspace_id:
        raise ValidationError({"list_id": ["Destination list is not in this workspace."]})
    if status is None:
        raise ValidationError({"status": ["status is required."]})
    status = resolve_status(status)

    source_list = task.list
    previous_status = task.status
    rebalanced = False
    collided = False
    for attempt in range(3):
        prev_pos = _neighbour_position(target_list.id, status, before_id, task.pk)
        next_pos = _neighbour_position(target_list.id, status, after_id, task.pk)

        if prev_pos is not None and next_pos is not None and prev_pos >= next_pos:
            raise PositionConflict()

        if prev_pos is None and next_pos is None:
            # empty column (or "only item"); fall back to end-of-column when the
            # client's view was stale, instead of a spurious conflict
            new_pos = _end_of_column_position(target_list.id, status, exclude_pk=task.pk)
        else:
            new_pos = midstring(prev_pos, next_pos)

        if collided:
            # Oldingi urinish `uniq_task_position_per_column` ga urildi: aynan
            # shu qo'shni juftlik orasiga parallel yozuvchi allaqachon
            # joylashgan. `midstring(prev, next)` yana O'SHA kalitni beradi,
            # ya'ni takroriy urinishlar hech qachon yaqinlashmasdi (3 ta
            # urinish → 409, garchi bo'sh joy bor bo'lsa ham). G'olibning
            # ustidan bir qadam bosib o'tamiz — natija baribir `prev` bilan
            # `next` orasida qoladi.
            new_pos = _nudged_position(target_list.id, status, task.pk, new_pos)

        if len(new_pos) > MAX_LEN_BEFORE_REBALANCE:
            rebalance_column(target_list, status)
            rebalanced = True
            collided = False
            continue

        try:
            with transaction.atomic():
                task.list = target_list
                task.status = status
                task.position = new_pos
                task.updated_by = actor
                _apply_completed_at(task, status)
                task.save(
                    update_fields=[
                        "list",
                        "status",
                        "position",
                        "completed_at",
                        "updated_by",
                        "updated_at",
                    ]
                )
            break
        except IntegrityError:
            if attempt == 2:
                raise PositionConflict("Could not obtain a stable position after 3 attempts.")
            # Backoff YO'Q — `create_task` dagi bilan bir xil sabab: bu blok
            # ochiq tranzaksiya ichida, `sleep` esa qulflarni ushlab turardi.
            collided = True
            continue

    rows = []
    if source_list.id != target_list.id:
        rows.append(
            activity(
                task,
                actor,
                ActivityVerb.MOVED,
                from_value=source_list.name,
                to_value=target_list.name,
                from_list_id=str(source_list.id),
                to_list_id=str(target_list.id),
            )
        )
    if previous_status != status:
        rows += _status_activities(task, actor, previous_status, status)
    log_activities(rows)

    refresh_list_counts(target_list, actor=actor, client_id=client_id, emit=True)
    if source_list.id != target_list.id:
        refresh_list_counts(source_list, actor=actor, client_id=client_id, emit=True)
    events.emit_task_event(
        "task.moved", task, actor=actor, client_id=client_id, rebalanced=rebalanced
    )
    return task, rebalanced


def watch_task(task, user) -> bool:
    created = add_watcher(task, user, WatcherSource.MANUAL)
    return created


def unwatch_task(task, user):
    TaskWatcher.objects.filter(task=task, user=user).delete()


# ---------------------------------------------------------------- attachments


def _refresh_attachment_count(task):
    task.attachment_count = TaskAttachment.objects.filter(task=task).count()
    task.save(update_fields=["attachment_count", "updated_at"])


@transaction.atomic
def create_attachment(
    task, actor, *, upload, original_name, content_type, extension, client_id=None
) -> TaskAttachment:
    """Biriktirmani saqlaydi — §10.7.

    Chaqiruvchi (`apps.tasks.attachments.validate_upload`) hajm/kengaytma/MIME
    tekshiruvini allaqachon bajargan bo'lishi SHART. Diskdagi nom shu yerda,
    serverda generatsiya qilinadi: mijoz nomi hech qachon yo'lga tushmaydi.

    **Vazifa bajarilgan (`status.type == "closed"`) bo'lsa ham ishlaydi** —
    biriktirish holatga bog'liq emas (foydalanuvchi talabi).
    """
    attachment = TaskAttachment(
        task=task,
        original_name=original_name,
        content_type=content_type,
        size_bytes=upload.size,
        uploaded_by=actor,
    )
    attachment.file.save(f"{uuid.uuid4().hex}{extension}", upload, save=False)
    attachment.save()
    _refresh_attachment_count(task)
    events.emit_attachment_added(attachment, actor=actor, client_id=client_id)
    return attachment


@transaction.atomic
def delete_attachment(attachment, actor, client_id=None):
    """Qatorni va diskdagi faylni o'chiradi (hard delete — soft delete yo'q)."""
    task = attachment.task
    stored = attachment.file
    # Django `delete()` dan keyin pk ni tozalaydi — event uchun snapshot olamiz.
    snapshot = TaskAttachment(id=attachment.id, task=task)
    attachment.delete()
    _refresh_attachment_count(task)
    # Tranzaksiya qaytsa fayl diskda qolishi kerak, shuning uchun commit'dan keyin.
    transaction.on_commit(lambda: stored.delete(save=False))
    events.emit_attachment_removed(snapshot, actor=actor, client_id=client_id)
