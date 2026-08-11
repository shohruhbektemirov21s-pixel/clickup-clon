"""`Priority.NORMAL = "normal"` → `MEDIUM = "medium"` (spetsifikatsiya §6.1).

`NONE = "none"` SAQLANADI — u "muhimlik belgilanmagan" degani va `medium`
bilan bir xil emas. `priority_order` o'zgarmaydi (ikkalasi ham 3-o'rin),
shuning uchun tartiblash natijasi ham o'zgarmaydi.
"""

from django.db import migrations, models

PRIORITY_CHOICES = [
    ("urgent", "Urgent"),
    ("high", "High"),
    ("medium", "Medium"),
    ("low", "Low"),
    ("none", "No priority"),
]


def normal_to_medium(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    Task.objects.filter(priority="normal").update(priority="medium")


def medium_to_normal(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    Task.objects.filter(priority="medium").update(priority="normal")


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0005_task_status_code"),
    ]

    operations = [
        migrations.RunPython(normal_to_medium, medium_to_normal),
        migrations.AlterField(
            model_name="task",
            name="priority",
            field=models.CharField(
                choices=PRIORITY_CHOICES, db_index=True, default="none", max_length=7
            ),
        ),
    ]
