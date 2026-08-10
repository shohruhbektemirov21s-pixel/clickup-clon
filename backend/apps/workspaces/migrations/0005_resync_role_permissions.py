"""Mavjud ish maydonlarini yangi standart ruxsat siyosatiga keltirish.

Migratsiya 0003 har bir workspace uchun 3 rol x har bir kod bo'yicha TO'LIQ
`RolePermission` jadvalini materializatsiya qilgan. `_build_matrix` esa
`DEFAULT_MATRIX` ustiga o'sha qatorlarni yopishtiradi — ya'ni **materializatsiya
qilingan eski default yangi defaultni bosib ketadi**. Natijada 2026-08 siyosati
(`member` endi begona vazifani tahrirlay/o'chira olmaydi, `guest` esa jamoa
ro'yxatini ko'radi) faqat YANGI yaratilgan workspace'larda ishlardi.

Bu migratsiya barcha mavjud qatorlarni quyidagi snapshot bo'yicha qayta yozadi.

TRADE-OFF, ochiq aytilgan: admin qo'lda kiritgan **ataylab** o'zgartirishlar ham
qaytariladi — saqlangan qator "eski default" mi yoki "ongli override" mi ekanini
ajratib bo'lmaydi. Mahsulot hali bu sozlamani hech kimga chiqarmagan, xavfsizlik
siyosati esa jimgina qo'llanmay qolishidan ko'ra qaytarilgani afzal.

Snapshot ataylab shu faylning ichida: katalog evolyutsiya qiladi, migratsiya esa
tarixiy holatni takrorlashi kerak (0003 dagi bilan bir xil qoida).
"""

from django.db import migrations

ROLE_DEFAULTS = {
    "admin": [
        "attachment.create", "attachment.delete_any", "attachment.delete_own",
        "attachment.read", "comment.create", "comment.delete_any",
        "comment.delete_own", "comment.update_own", "folder.create",
        "folder.delete", "folder.delete_cascade", "folder.update",
        "invitation.manage", "invitation.read", "list.create", "list.delete",
        "list.manage_statuses", "list.move", "list.update", "member.invite",
        "member.read", "member.remove", "member.role_change", "space.create",
        "space.delete", "space.manage_members", "space.manage_statuses",
        "space.read", "space.read_private", "space.update", "tag.create",
        "tag.delete", "tag.update", "task.assign", "task.create", "task.delete",
        "task.move", "task.read", "task.restore", "task.update",
        "task.update_assigned", "task.view_deleted", "task.watch",
        "workspace.read",
    ],
    "member": [
        "attachment.create", "attachment.delete_own", "attachment.read",
        "comment.create", "comment.delete_own", "comment.update_own",
        "member.read", "space.read", "tag.create", "task.create", "task.read",
        "task.update_assigned", "task.watch", "workspace.read",
    ],
    "guest": [
        "attachment.read", "comment.create", "comment.delete_own",
        "comment.update_own", "member.read", "space.read", "task.read",
        "task.update_assigned", "task.watch", "workspace.read",
    ],
}


def forward(apps, schema_editor):
    RolePermission = apps.get_model("workspaces", "RolePermission")
    Workspace = apps.get_model("workspaces", "Workspace")

    for role, codes in ROLE_DEFAULTS.items():
        allowed = set(codes)
        rows = RolePermission.objects.filter(role=role)
        # Ikkita `update()` — qator-ma-qator saqlashdan ko'ra ancha tez.
        rows.filter(permission__in=allowed).exclude(allowed=True).update(allowed=True)
        rows.exclude(permission__in=allowed).exclude(allowed=False).update(allowed=False)

    # Kesh kaliti `permissions_version` ni o'z ichiga oladi — oshirmasak,
    # ishlab turgan process eski matritsani TTL tugagunicha ko'rsatib turadi.
    for workspace in Workspace.objects.all().iterator(chunk_size=500):
        Workspace.objects.filter(pk=workspace.pk).update(
            permissions_version=workspace.permissions_version + 1
        )


def backward(apps, schema_editor):
    """Qaytarib bo'lmaydi: oldingi qiymatlar hech qayerda saqlanmagan.

    Bu no-op — orqaga migratsiya sxemani buzmaydi, faqat ruxsat qatorlari
    yangi siyosatda qolaveradi.
    """


class Migration(migrations.Migration):
    dependencies = [("workspaces", "0004_backfill_space_members")]
    operations = [migrations.RunPython(forward, backward)]
