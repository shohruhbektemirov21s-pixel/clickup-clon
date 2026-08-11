"""`Task.status`: `workspaces.Status` FK → `TaskStatus` kodi (ma'lumot yo'qotmasdan).

Uch qadam, bitta fayl (spetsifikatsiya §4):

1. `status_code` (CharField, null=True) qo'shiladi;
2. **data migration** — eski `statuses.type` bo'yicha xaritalash:
   ``open → todo``, ``active → in_progress``, ``closed → done``,
   statussiz (nazariy jihatdan bo'lmasligi kerak) qator → ``todo``;
3. eski FK o'chiriladi, `status_code` → `status` deb qayta nomlanadi va
   `null=False` qilinadi.

**`review` ga hech nima avtomatik ko'chmaydi** — eski modelda unga mos
`StatusType` yo'q edi. Bu ma'lumot yo'qotish EMAS: "Tekshiruvda"/"Review"
nomli eski statuslar `active` turida bo'lgan, ya'ni ular `in_progress` ga
tushadi va vazifa doskada o'z ma'nosiga eng yaqin ustunda qoladi. YO'QOLGAN
narsa — statusning **nomi, rangi va tartibi** (endi ular kodda,
`apps/core/enums.py` da yashaydi).

`uniq_task_position_per_column` va `idx_task_column_pos` DBda `status_id`
ustuniga bog'langan, shuning uchun ular oldin olib tashlanadi va oxirida
AYNAN o'sha nom bilan (endi `status` ustuni bo'yicha) qayta quriladi —
mantiq o'zgarmaydi, faqat ustun turi o'zgaradi.
"""

from django.db import migrations, models

#: Eski `statuses.type` → yangi kod.
TYPE_TO_CODE = {
    "open": "todo",
    "active": "in_progress",
    "closed": "done",
}
FALLBACK = "todo"


def fill_status_code(apps, schema_editor):
    Status = apps.get_model("workspaces", "Status")
    Task = apps.get_model("tasks", "Task")

    # Har bir eski status uchun bitta UPDATE — vazifa soniga qarab so'rov
    # ko'paymaydi (status to'plami har doim kichik).
    for status_id, status_type in Status.objects.values_list("id", "type"):
        Task.objects.filter(status_id=status_id).update(
            status_code=TYPE_TO_CODE.get(status_type, FALLBACK)
        )
    # Xarita tashqarisida qolgan (yoki statussiz) hech bir qator statussiz
    # qolmasin — qabul mezoni aynan shu.
    Task.objects.filter(status_code__isnull=True).update(status_code=FALLBACK)


def unfill_status_code(apps, schema_editor):
    """Orqaga qaytarish ma'lumotni tiklamaydi.

    Eski status to'plamlari (nom/rang/tartib) o'chirilgan bo'ladi, ya'ni FK
    ni qayta tiklashning yagona to'g'ri yo'li — bazadan nusxa. Migratsiyani
    "muvaffaqiyatli qaytardim" deb ko'rsatib, vazifalarni statussiz qoldirib
    ketmaslik uchun ataylab yiqiladi.
    """
    raise RuntimeError(
        "0005_task_status_code orqaga qaytarilmaydi — eski status to'plamlari "
        "tiklanmaydi. Bazani zaxiradan tiklang."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0004_alter_taskactivity_verb"),
        ("workspaces", "0005_resync_role_permissions"),
    ]

    operations = [
        # 0) `status_id` ga bog'langan cheklov va indeks vaqtincha olinadi.
        migrations.RemoveConstraint(
            model_name="task",
            name="uniq_task_position_per_column",
        ),
        migrations.RemoveIndex(
            model_name="task",
            name="idx_task_column_pos",
        ),
        # 1) yangi ustun
        migrations.AddField(
            model_name="task",
            name="status_code",
            field=models.CharField(max_length=16, null=True),
        ),
        # 2) ma'lumotni ko'chirish
        migrations.RunPython(fill_status_code, unfill_status_code),
        # 3) eski FK o'chadi, yangisi o'z nomini oladi
        migrations.RemoveField(
            model_name="task",
            name="status",
        ),
        migrations.RenameField(
            model_name="task",
            old_name="status_code",
            new_name="status",
        ),
        migrations.AlterField(
            model_name="task",
            name="status",
            field=models.CharField(
                choices=[
                    ("todo", "Boshlanmagan"),
                    ("in_progress", "Jarayonda"),
                    ("review", "Tekshirilmoqda"),
                    ("done", "Bajarildi"),
                ],
                db_index=True,
                default="todo",
                max_length=16,
            ),
        ),
        # 4) cheklov/indeks o'sha nom bilan, endi `status` ustuni bo'yicha
        migrations.AddIndex(
            model_name="task",
            index=models.Index(
                fields=["list", "status", "position"], name="idx_task_column_pos"
            ),
        ),
        migrations.AddConstraint(
            model_name="task",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("list", "status", "position"),
                name="uniq_task_position_per_column",
            ),
        ),
    ]
