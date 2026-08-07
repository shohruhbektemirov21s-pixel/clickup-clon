"""Seed a demo user + a fully populated workspace for local development.

    ../.venv/Scripts/python.exe manage.py seed_demo
    ../.venv/Scripts/python.exe manage.py seed_demo --email you@example.com
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.comments.services import create_comment
from apps.core.enums import Priority, WatcherSource
from apps.core.ordering import evenly_spaced, midstring
from apps.tasks.models import Tag, Task, TaskAssignee, TaskWatcher, TaskTag
from apps.workspaces.models import Folder, TaskList
from apps.workspaces.services import (
    bootstrap_workspace,
    create_space,
    next_position,
    refresh_list_counts,
)

DEMO_EMAIL = "demo@clickish.dev"
DEMO_PASSWORD = "clickish-demo-2026"


class Command(BaseCommand):
    help = "Create the demo user (demo@clickish.dev) and a populated workspace."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=DEMO_EMAIL)
        parser.add_argument("--password", default=DEMO_PASSWORD)

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].lower()
        password = options["password"]

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email, password=password, full_name="Demo User"
            )
            self.stdout.write(f"Created user {email}")
        else:
            user.set_password(password)
            user.save(update_fields=["password", "updated_at"])
            self.stdout.write(f"User {email} already existed; password reset.")

        if user.workspace_memberships.filter(workspace__name="Clickish Demo").exists():
            self.stdout.write("Demo workspace already exists; nothing else to do.")
            self._print_credentials(email, password)
            return

        workspace = bootstrap_workspace(
            user, name="Clickish Demo", description="Seeded demo workspace"
        )

        # A second space with a folder, extra lists, tags, tasks and comments.
        space = create_space(
            workspace, user, name="Product", color="#2ECD6F", icon="rocket"
        )
        statuses = list(space.status_set.statuses.order_by("order"))
        by_type = {s.type: s for s in statuses}

        folder = Folder.objects.create(
            space=space,
            name="Q3 Roadmap",
            color="#7B68EE",
            position="n",
            created_by=user,
        )
        sprint = TaskList.objects.create(
            space=space, folder=folder, name="Sprint 24", position="n", created_by=user
        )
        backlog = TaskList.objects.create(
            space=space,
            folder=None,
            name="Backlog",
            position=next_position(TaskList.objects.filter(space=space, folder__isnull=True)),
            created_by=user,
        )

        tags = {
            name: Tag.objects.create(
                workspace=workspace, name=name, color=color, created_by=user
            )
            for name, color in [
                ("backend", "#FD71AF"),
                ("frontend", "#49CCF9"),
                ("bug", "#E44343"),
            ]
        }

        sprint_tasks = [
            ("Fix login redirect", "open", Priority.URGENT, ["bug", "backend"]),
            ("Board drag & drop polish", "active", Priority.HIGH, ["frontend"]),
            ("Realtime presence avatars", "active", Priority.NORMAL, ["frontend"]),
            ("Ship status-set editor", "closed", Priority.HIGH, ["backend"]),
        ]
        positions = evenly_spaced(len(sprint_tasks))
        created_tasks = []
        for (title, stype, priority, tag_names), pos in zip(sprint_tasks, positions):
            status = by_type[stype]
            task = Task.objects.create(
                list=sprint,
                status=status,
                title=title,
                description_html=f"<p>{title} — seeded demo task.</p>",
                description_json={
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": title}],
                        }
                    ],
                },
                priority=priority,
                position=pos,
                due_date=timezone.now() + timedelta(days=3),
                created_by=user,
                updated_by=user,
                completed_at=timezone.now() if stype == "closed" else None,
            )
            TaskWatcher.objects.create(task=task, user=user, source=WatcherSource.AUTO_CREATOR)
            TaskAssignee.objects.create(task=task, user=user, assigned_by=user)
            for tag_name in tag_names:
                TaskTag.objects.create(task=task, tag=tags[tag_name])
            created_tasks.append(task)

        pos = None
        for title in ["Dark mode", "Public API", "Mobile layout audit"]:
            pos = midstring(pos, None)
            Task.objects.create(
                list=backlog,
                status=by_type["open"],
                title=title,
                position=pos,
                created_by=user,
                updated_by=user,
            )

        create_comment(
            created_tasks[0],
            user,
            {
                "body_html": "<p>Repro confirmed on staging — fix incoming.</p>",
                "body_json": {"type": "doc", "content": []},
            },
        )
        create_comment(
            created_tasks[0],
            user,
            {
                "body_html": "<p>Deployed behind a feature flag.</p>",
                "body_json": {"type": "doc", "content": []},
            },
        )

        for tag in tags.values():
            tag.usage_count = TaskTag.objects.filter(tag=tag).count()
            tag.save(update_fields=["usage_count"])
        refresh_list_counts(sprint)
        refresh_list_counts(backlog)

        self.stdout.write(self.style.SUCCESS(f"Workspace '{workspace.name}' seeded."))
        self._print_credentials(email, password)

    def _print_credentials(self, email, password):
        self.stdout.write(self.style.SUCCESS(f"Login:    {email}"))
        self.stdout.write(self.style.SUCCESS(f"Password: {password}"))
