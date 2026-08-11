"""`StatusSet` / `Status` jadvallarini tashlash (spetsifikatsiya §2, §4.3).

`tasks.0005_task_status_code` dan KEYIN ishlashi shart: o'sha migratsiya
`Task.status` FK sini kodga aylantirmaguncha bu jadvallarga tayanuvchi qator
bor va o'chirish `ProtectedError` beradi.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("workspaces", "0005_resync_role_permissions"),
        ("tasks", "0005_task_status_code"),
    ]

    # `RemoveField` ATAYLAB ishlatilmaydi: SQLite ustunni olib tashlash uchun
    # jadvalni qaytadan quradi va `uniq_status_name_per_set`
    # (`"status_set", Lower("name")`) hali holatda turgani uchun endi mavjud
    # bo'lmagan ustunga tayanadi → `FieldError`. Jadvalni butunlay tashlash bu
    # muammoni chetlab o'tadi va natija ham aynan shu.
    operations = [
        migrations.DeleteModel(name="Status"),
        migrations.DeleteModel(name="StatusSet"),
    ]
