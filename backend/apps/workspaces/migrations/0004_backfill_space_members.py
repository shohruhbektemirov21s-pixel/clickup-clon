"""SpaceMember backfill — hech kim kirishni yo'qotmasligi uchun.

docs/DESIGN_PERMISSIONS.md §G.1 (0004) va R1:

- **Yopiq** bo'lim: barcha non-guest workspace a'zolari yoziladi —
  `owner`/`admin` → `manager`, qolganlar → `contributor`, `source="backfill"`.
- **Ochiq** bo'lim: faqat `created_by` → `manager`, `source="auto_creator"`.
- Yopiq bo'limda vazifasi biriktirilgan **guest**lar → `viewer`,
  `source="auto_assignee"` (AD-7).

Additive va idempotent: mavjud `(space, user)` juftliklari qayta yozilmaydi.
"""

from django.db import migrations

NON_GUEST_ROLES = ("owner", "admin", "member")
MANAGER_ROLES = ("owner", "admin")


def backfill(apps, schema_editor):
    Space = apps.get_model("workspaces", "Space")
    WorkspaceMember = apps.get_model("workspaces", "WorkspaceMember")
    SpaceMember = apps.get_model("workspaces", "SpaceMember")
    TaskAssignee = apps.get_model("tasks", "TaskAssignee")

    rows = []
    seen = set()

    def add(space_id, user_id, access, source):
        key = (space_id, user_id)
        if user_id is None or key in seen:
            return
        seen.add(key)
        rows.append(
            SpaceMember(space_id=space_id, user_id=user_id, access=access, source=source)
        )

    seen |= set(SpaceMember.objects.values_list("space_id", "user_id"))

    for space in Space.objects.all().iterator():
        if space.is_private:
            # Yaratuvchi har doim menejer bo'lib qoladi (roldan qat'i nazar).
            add(space.id, space.created_by_id, "manager", "backfill")
            memberships = WorkspaceMember.objects.filter(
                workspace_id=space.workspace_id, role__in=NON_GUEST_ROLES
            ).values_list("user_id", "role")
            for user_id, role in memberships:
                access = "manager" if role in MANAGER_ROLES else "contributor"
                add(space.id, user_id, access, "backfill")
            # Yopiq bo'limda vazifasi bor guestlar hech bo'lmasa ko'ruvchi qoladi.
            guest_ids = set(
                WorkspaceMember.objects.filter(
                    workspace_id=space.workspace_id, role="guest"
                ).values_list("user_id", flat=True)
            )
            if guest_ids:
                assigned = set(
                    TaskAssignee.objects.filter(
                        task__list__space_id=space.id, user_id__in=guest_ids
                    ).values_list("user_id", flat=True)
                )
                for user_id in assigned:
                    add(space.id, user_id, "viewer", "auto_assignee")
        else:
            add(space.id, space.created_by_id, "manager", "auto_creator")

    if rows:
        SpaceMember.objects.bulk_create(rows, ignore_conflicts=True, batch_size=500)


def unbackfill(apps, schema_editor):
    SpaceMember = apps.get_model("workspaces", "SpaceMember")
    SpaceMember.objects.filter(source__in=("backfill", "auto_creator", "auto_assignee")).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("workspaces", "0003_seed_role_permissions"),
        ("tasks", "0002_taskactivity"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
