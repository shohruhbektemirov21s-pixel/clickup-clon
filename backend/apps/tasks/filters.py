"""Task filter/ordering vocabulary — closed set, docs/API_CONTRACT.md section 10.5."""

import zoneinfo
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.api import parse_bool
from apps.core.enums import Priority, StatusType

ALLOWED_ORDERING_FIELDS = {
    "position",
    "due_date",
    "priority_order",
    "created_at",
    "updated_at",
    "title",
}


def caller_tz(user):
    try:
        return zoneinfo.ZoneInfo(user.timezone or "UTC")
    except (zoneinfo.ZoneInfoNotFoundError, KeyError, ValueError):
        return zoneinfo.ZoneInfo("UTC")


def apply_task_filters(qs, request, membership):
    params = request.query_params
    user = request.user

    statuses = params.getlist("status")
    if statuses:
        qs = qs.filter(status_id__in=statuses)

    status_type = params.get("status_type")
    if status_type:
        if status_type not in StatusType.values:
            raise ValidationError({"status_type": ["Must be open, active or closed."]})
        qs = qs.filter(status__type=status_type)

    assignees = params.getlist("assignee")
    if assignees:
        q = Q()
        ids = []
        for value in assignees:
            if value == "me":
                ids.append(user.id)
            elif value == "none":
                q |= Q(task_assignees__isnull=True)
            else:
                ids.append(value)
        if ids:
            q |= Q(task_assignees__user_id__in=ids)
        qs = qs.filter(q).distinct()

    priorities = params.getlist("priority")
    if priorities:
        bad = [p for p in priorities if p not in Priority.values]
        if bad:
            raise ValidationError({"priority": [f"Invalid priority: {', '.join(bad)}."]})
        qs = qs.filter(priority__in=priorities)

    tags = params.getlist("tag")
    if tags:
        qs = qs.filter(task_tags__tag_id__in=tags).distinct()

    due = params.get("due")
    if due:
        now = timezone.now()
        tz = caller_tz(user)
        local_now = now.astimezone(tz)
        start_of_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        if due == "overdue":
            qs = qs.filter(due_date__lt=now).exclude(status__type=StatusType.CLOSED)
        elif due == "today":
            qs = qs.filter(
                due_date__gte=start_of_day, due_date__lt=start_of_day + timedelta(days=1)
            )
        elif due == "this_week":
            week_start = start_of_day - timedelta(days=start_of_day.weekday())
            qs = qs.filter(
                due_date__gte=week_start, due_date__lt=week_start + timedelta(days=7)
            )
        elif due == "none":
            qs = qs.filter(due_date__isnull=True)
        else:
            raise ValidationError({"due": ["Must be overdue, today, this_week or none."]})

    if params.get("due_before"):
        qs = qs.filter(due_date__lt=params["due_before"])
    if params.get("due_after"):
        qs = qs.filter(due_date__gt=params["due_after"])

    if params.get("created_by"):
        qs = qs.filter(created_by_id=params["created_by"])
    if params.get("watcher"):
        qs = qs.filter(task_watchers__user_id=params["watcher"]).distinct()

    q_text = params.get("q")
    if q_text is not None:
        q_text = q_text.strip()
        if len(q_text) < 2:
            return qs.none()
        qs = qs.filter(
            Q(title__icontains=q_text) | Q(description_html__icontains=q_text)
        )

    archived = parse_bool(params.get("archived"), False)
    qs = qs.filter(archived=archived)

    return qs


def apply_ordering(qs, request, default):
    ordering = request.query_params.get("ordering")
    if not ordering:
        return qs.order_by(*default)
    field = ordering.lstrip("-")
    if field not in ALLOWED_ORDERING_FIELDS:
        raise ValidationError({"ordering": [f"Unsupported ordering field: {field}."]})
    return qs.order_by(ordering, "created_at")


def include_deleted_requested(request, membership):
    """`?include_deleted=true` → `task.view_deleted` (default: admin+), else 403."""
    from apps.core.access import require_perm

    if parse_bool(request.query_params.get("include_deleted"), False):
        require_perm(membership, "task.view_deleted")
        return True
    return False
