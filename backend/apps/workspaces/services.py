"""Workspace-hierarchy services. All realtime events are emitted from here,
never from views (CLAUDE.md convention)."""

import secrets
import uuid
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from apps.core.enums import StatusType, WorkspaceRole
from apps.core.exceptions import Conflict, PositionConflict
from apps.core.ordering import evenly_spaced, midstring
from apps.realtime import events
from apps.workspaces.models import (
    Folder,
    Invitation,
    Space,
    Status,
    StatusSet,
    TaskList,
    Workspace,
    WorkspaceMember,
)

DEFAULT_STATUSES = [
    {"name": "TO DO", "type": StatusType.OPEN, "color": "#87909E", "is_default": True},
    {"name": "IN PROGRESS", "type": StatusType.ACTIVE, "color": "#4194F6", "is_default": False},
    {"name": "COMPLETE", "type": StatusType.CLOSED, "color": "#6BC950", "is_default": False},
]

SAMPLE_TASKS = [
    ("Create your first task", 0),
    ("Drag tasks between statuses", 1),
    ("Invite your team", 2),
]


def check_client_id(model, supplied_id):
    """Client-generated ids: 409 conflict when the id is already in use."""
    if supplied_id in (None, ""):
        return None
    manager = getattr(model, "all_objects", model.objects)
    if manager.filter(pk=supplied_id).exists():
        raise Conflict("A resource with this id already exists.")
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


@transaction.atomic
def create_space(workspace, actor, *, name, description="", color=None, icon="",
                 is_private=False, space_id=None) -> Space:
    if Space.objects.filter(workspace=workspace, name__iexact=name.strip()).exists():
        raise Conflict("A space with this name already exists in the workspace.")
    check_client_id(Space, space_id)
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
    status_set = StatusSet.objects.create(space=space, name="Default")
    seed_default_statuses(status_set)
    return space


@transaction.atomic
def bootstrap_workspace(user, *, name, description="", color=None, workspace_id=None) -> Workspace:
    """DATA_MODEL.md section 11: workspace + owner membership + Team Space +
    default status set + Getting Started list + 3 sample tasks."""
    from apps.tasks.models import Task, TaskWatcher

    check_client_id(Workspace, workspace_id)
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

    space = Space.objects.create(
        workspace=workspace,
        name="Team Space",
        position="n",
        created_by=user,
    )
    status_set = StatusSet.objects.create(space=space, name="Default")
    statuses = seed_default_statuses(status_set)

    task_list = TaskList.objects.create(
        space=space, folder=None, name="Getting Started", position="n", created_by=user
    )
    positions = evenly_spaced(len(SAMPLE_TASKS))
    for (title, status_idx), pos in zip(SAMPLE_TASKS, positions):
        task = Task.objects.create(
            list=task_list,
            status=statuses[status_idx],
            title=title,
            position=pos,
            created_by=user,
            updated_by=user,
            completed_at=timezone.now()
            if statuses[status_idx].type == StatusType.CLOSED
            else None,
        )
        TaskWatcher.objects.create(task=task, user=user, source="auto_creator")
    refresh_list_counts(task_list)
    return workspace


def refresh_member_count(workspace):
    workspace.member_count = WorkspaceMember.objects.filter(workspace=workspace).count()
    workspace.save(update_fields=["member_count", "updated_at"])


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
        events.emit_list_updated(task_list, actor=actor, client_id=client_id)


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
    events.emit_list_updated(task_list, actor=actor, client_id=client_id)
    return task_list


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
                list=task_list, name=data.get("name") or "Default"
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
                check_client_id(Status, sid)
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
