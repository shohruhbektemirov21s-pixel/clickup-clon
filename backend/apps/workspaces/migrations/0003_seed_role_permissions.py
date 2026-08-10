"""Mavjud ish maydonlariga default ruxsat matritsasini yozadi.

docs/DESIGN_PERMISSIONS.md §G.1 (0003): katalog snapshot'i shu faylning
**ichida** literal dict sifatida turadi va `apps.core.permissions` dan
**import qilinmaydi** — katalog vaqt o'tishi bilan evolyutsiya qiladi, bu
migratsiya esa 2026-08-10 dagi tarixiy holatni takrorlashi shart.

`bulk_create(..., ignore_conflicts=True)` → to'liq idempotent.
"""

from django.db import migrations

# --- KATALOG SNAPSHOT (2026-08-10, catalog_version = 1, 44 kod) --------------
# kod -> shu kod default'da yoqilgan rollar. owner HECH QACHON bu yerda emas.
CATALOG_SNAPSHOT = {
    # workspace
    "workspace.read": ["admin", "member", "guest"],
    "workspace.update": [],
    "workspace.delete": [],
    "workspace.manage_permissions": [],
    "workspace.transfer_ownership": [],
    # member
    "member.read": ["admin", "member"],
    "member.invite": ["admin"],
    "member.remove": ["admin"],
    "member.role_change": ["admin"],
    "invitation.read": ["admin"],
    "invitation.manage": ["admin"],
    # space
    "space.read": ["admin", "member", "guest"],
    "space.read_private": ["admin"],
    "space.create": ["admin"],
    "space.update": ["admin"],
    "space.delete": ["admin"],
    "space.manage_members": ["admin"],
    "space.manage_statuses": ["admin"],
    # folder
    "folder.create": ["admin", "member"],
    "folder.update": ["admin", "member"],
    "folder.delete": ["admin", "member"],
    "folder.delete_cascade": ["admin"],
    # list
    "list.create": ["admin", "member"],
    "list.update": ["admin", "member"],
    "list.delete": ["admin", "member"],
    "list.move": ["admin", "member"],
    "list.manage_statuses": ["admin"],
    # task
    "task.read": ["admin", "member", "guest"],
    "task.create": ["admin", "member"],
    "task.update": ["admin", "member"],
    "task.update_assigned": ["admin", "member", "guest"],
    "task.delete": ["admin", "member"],
    "task.move": ["admin", "member"],
    "task.assign": ["admin", "member"],
    "task.watch": ["admin", "member", "guest"],
    "task.restore": ["admin"],
    "task.view_deleted": ["admin"],
    # comment
    "comment.create": ["admin", "member", "guest"],
    "comment.update_own": ["admin", "member", "guest"],
    "comment.delete_own": ["admin", "member", "guest"],
    "comment.delete_any": ["admin"],
    # tag
    "tag.create": ["admin", "member"],
    "tag.update": ["admin", "member"],
    "tag.delete": ["admin", "member"],
}

ASSIGNABLE_ROLES = ("admin", "member", "guest")


def seed(apps, schema_editor):
    Workspace = apps.get_model("workspaces", "Workspace")
    RolePermission = apps.get_model("workspaces", "RolePermission")

    for workspace_id in Workspace.objects.values_list("id", flat=True).iterator():
        existing = set(
            RolePermission.objects.filter(workspace_id=workspace_id).values_list(
                "role", "permission"
            )
        )
        rows = [
            RolePermission(
                workspace_id=workspace_id,
                role=role,
                permission=code,
                allowed=role in default_roles,
            )
            for code, default_roles in CATALOG_SNAPSHOT.items()
            for role in ASSIGNABLE_ROLES
            if (role, code) not in existing
        ]
        if rows:
            RolePermission.objects.bulk_create(rows, ignore_conflicts=True)


def unseed(apps, schema_editor):
    """Reverse: faqat snapshot kodlarini olib tashlaydi (jadval 0002 da tushadi)."""
    RolePermission = apps.get_model("workspaces", "RolePermission")
    RolePermission.objects.filter(permission__in=list(CATALOG_SNAPSHOT)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("workspaces", "0002_permissions_and_space_members"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
