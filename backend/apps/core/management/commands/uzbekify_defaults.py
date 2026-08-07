"""Rename rows still carrying the old English bootstrap default names to the
new Uzbek defaults. Idempotent — exact matches only, safe to run repeatedly.

    ../.venv/Scripts/python.exe manage.py uzbekify_defaults
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.tasks.models import Task
from apps.workspaces.models import Space, Status, TaskList

SPACE_RENAMES = {"Team Space": "Jamoa bo'limi"}
LIST_RENAMES = {"Getting Started": "Boshlash"}
STATUS_RENAMES = {
    "TO DO": "BAJARILADI",
    "IN PROGRESS": "JARAYONDA",
    "COMPLETE": "BAJARILDI",
}
TASK_RENAMES = {
    "Create your first task": "Birinchi vazifangizni yarating",
    "Drag tasks between statuses": "Vazifalarni statuslar orasida ko'chiring",
    "Invite your team": "Jamoangizni taklif qiling",
}


class Command(BaseCommand):
    help = "Rename old English default names (Team Space, Getting Started, ...) to Uzbek."

    @transaction.atomic
    def handle(self, *args, **options):
        total = 0
        plans = [
            (Space.objects, "name", SPACE_RENAMES, "spaces"),
            (TaskList.objects, "name", LIST_RENAMES, "lists"),
            (Status.objects, "name", STATUS_RENAMES, "statuses"),
            (getattr(Task, "all_objects", Task.objects), "title", TASK_RENAMES, "tasks"),
        ]
        for manager, field, renames, label in plans:
            updated = 0
            for old, new in renames.items():
                updated += manager.filter(**{field: old}).update(**{field: new})
            total += updated
            self.stdout.write(f"{label}: {updated} row(s) renamed")
        self.stdout.write(self.style.SUCCESS(f"Done. {total} row(s) updated in total."))
