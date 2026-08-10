"""Seed a demo user + a fully populated workspace for local development.

    ../.venv/Scripts/python.exe manage.py seed_demo
    ../.venv/Scripts/python.exe manage.py seed_demo --email you@example.com
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.comments.models import Comment
from apps.comments.services import create_comment
from apps.core.enums import Priority, WatcherSource, WorkspaceRole
from apps.core.ordering import evenly_spaced, midstring
from apps.tasks.models import Tag, Task, TaskAssignee, TaskWatcher, TaskTag
from apps.workspaces.models import Folder, TaskList, WorkspaceMember
from apps.workspaces.services import (
    bootstrap_workspace,
    create_space,
    next_position,
    refresh_list_counts,
    refresh_member_count,
)

DEMO_EMAIL = "demo@clickish.dev"
DEMO_PASSWORD = "clickish-demo-2026"

#: (email, ism, rol, rang, kasb). Kasb — profil yorlig'i, ruxsat EMAS: PM
#: loyihaga odam tanlaganda shu bo'yicha saralaydi.
DEMO_TEAM = [
    ("aziz@clickish.dev", "Aziz Karimov", WorkspaceRole.ADMIN, "#E44343", "project_manager"),
    ("malika@clickish.dev", "Malika Yusupova", WorkspaceRole.MEMBER, "#2ECD6F", "designer"),
    ("jasur@clickish.dev", "Jasur Rahimov", WorkspaceRole.MEMBER, "#49CCF9", "developer"),
    ("sarvar@clickish.dev", "Sarvar Aliyev", WorkspaceRole.MEMBER, "#F2C94C", "developer"),
    ("kamola@clickish.dev", "Kamola Rasulova", WorkspaceRole.MEMBER, "#9B51E0", "qa"),
    ("bekzod@clickish.dev", "Bekzod Ismoilov", WorkspaceRole.MEMBER, "#56CCF2", "analyst"),
    ("nodira@clickish.dev", "Nodira Tosheva", WorkspaceRole.GUEST, "#FD71AF", "marketing"),
]

#: "Demo rejimda kirish" tugmasi shu hisobga kiritadi. U ataylab `demo@` dan
#: ALOHIDA: `demo@` ish maydonining egasi bo'lib qoladi (testlar va qo'lda
#: boshqarish uchun), bu hisob esa `is_readonly=True` — hech narsani
#: o'zgartira ham, o'chira ham olmaydi.
DEMO_VIEWER = ("mehmon@clickish.dev", "Demo mehmon", WorkspaceRole.MEMBER, "#8C7CF0")

TEAM_COMMENTS = [
    ("aziz@clickish.dev", "<p>Men bu vazifani ko'rib chiqdim — tuzatish tayyor.</p>"),
    ("malika@clickish.dev", "<p>Rahmat! Testdan o'tkazib, tasdiqlayman.</p>"),
]


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
                email=email, password=password, full_name="Demo foydalanuvchi"
            )
            self.stdout.write(f"Created user {email}")
        else:
            user.set_password(password)
            user.save(update_fields=["password", "updated_at"])
            self.stdout.write(f"User {email} already existed; password reset.")

        membership = user.workspace_memberships.filter(
            workspace__name="Clickish Demo"
        ).first()
        if membership is not None:
            self.stdout.write("Demo workspace already exists; ensuring demo team.")
            self._ensure_team(user, membership.workspace)
            self._print_credentials(email, password)
            return

        workspace = bootstrap_workspace(
            user, name="Clickish Demo", description="Namuna sifatida yaratilgan demo ish maydoni"
        )

        # A second space with a folder, extra lists, tags, tasks and comments.
        space = create_space(
            workspace, user, name="Mahsulot", color="#2ECD6F", icon="rocket"
        )
        statuses = list(space.status_set.statuses.order_by("order"))
        by_type = {s.type: s for s in statuses}

        folder = Folder.objects.create(
            space=space,
            name="3-chorak yo'l xaritasi",
            color="#7B68EE",
            position="n",
            created_by=user,
        )
        sprint = TaskList.objects.create(
            space=space, folder=folder, name="24-sprint", position="n", created_by=user
        )
        backlog = TaskList.objects.create(
            space=space,
            folder=None,
            name="Navbatdagi ishlar",
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
                ("xatolik", "#E44343"),
            ]
        }

        sprint_tasks = [
            ("Kirishdagi yo'naltirishni tuzatish", "open", Priority.URGENT, ["xatolik", "backend"]),
            ("Doskada sudrab ko'chirishni sayqallash", "active", Priority.HIGH, ["frontend"]),
            ("Real vaqtdagi ishtirok avatarlari", "active", Priority.NORMAL, ["frontend"]),
            ("Status to'plami muharririni chiqarish", "closed", Priority.HIGH, ["backend"]),
        ]
        positions = evenly_spaced(len(sprint_tasks))
        created_tasks = []
        for (title, stype, priority, tag_names), pos in zip(sprint_tasks, positions):
            status = by_type[stype]
            task = Task.objects.create(
                list=sprint,
                status=status,
                title=title,
                description_html=f"<p>{title} — namunaviy demo vazifa.</p>",
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
        for title in ["Tungi rejim", "Ochiq API", "Mobil ko'rinish tahlili"]:
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
                "body_html": "<p>Xatolik staging muhitida tasdiqlandi — tuzatish yo'lda.</p>",
                "body_json": {"type": "doc", "content": []},
            },
        )
        create_comment(
            created_tasks[0],
            user,
            {
                "body_html": "<p>Funksiya bayrog'i ostida ishga tushirildi.</p>",
                "body_json": {"type": "doc", "content": []},
            },
        )

        for tag in tags.values():
            tag.usage_count = TaskTag.objects.filter(tag=tag).count()
            tag.save(update_fields=["usage_count"])
        refresh_list_counts(sprint)
        refresh_list_counts(backlog)
        self._ensure_team(user, workspace)

        self.stdout.write(self.style.SUCCESS(f"Workspace '{workspace.name}' seeded."))
        self._print_credentials(email, password)

    def _ensure_team(self, owner, workspace):
        """Idempotent: extra demo members + a few assignments and comments so
        multi-user UI (avatar stack, assignee picker, threads) is populated."""
        team = {}
        for member_email, full_name, role, color, profession in DEMO_TEAM:
            member = User.objects.filter(email__iexact=member_email).first()
            if member is None:
                member = User.objects.create_user(
                    email=member_email, password=DEMO_PASSWORD, full_name=full_name
                )
                self.stdout.write(f"Created user {member_email}")
            # Rang va kasb har safar majburlanadi — demo ma'lumoti izchil qolsin.
            member.avatar_color = color
            member.profession = profession
            member.save(update_fields=["avatar_color", "profession", "updated_at"])
            team[member_email] = member
            _, added = WorkspaceMember.objects.get_or_create(
                workspace=workspace, user=member, defaults={"role": role}
            )
            if added:
                self.stdout.write(f"Added {member_email} to '{workspace.name}' as {role}")

        viewer_email, viewer_name, viewer_role, viewer_color = DEMO_VIEWER
        viewer = User.objects.filter(email__iexact=viewer_email).first()
        if viewer is None:
            viewer = User.objects.create_user(
                email=viewer_email, password=DEMO_PASSWORD, full_name=viewer_name
            )
            viewer.avatar_color = viewer_color
            self.stdout.write(f"Created user {viewer_email}")
        # Har safar majburlanadi: bu hisob hech qachon yozish huquqiga ega
        # bo'lmasligi kerak, hatto kimdir uni qo'lda o'zgartirgan bo'lsa ham.
        viewer.is_readonly = True
        viewer.save(update_fields=["avatar_color", "is_readonly", "updated_at"])
        team[viewer_email] = viewer
        _, added = WorkspaceMember.objects.get_or_create(
            workspace=workspace, user=viewer, defaults={"role": viewer_role}
        )
        if added:
            self.stdout.write(
                f"Added {viewer_email} to '{workspace.name}' as {viewer_role} (faqat o'qish)"
            )
        refresh_member_count(workspace)

        tasks = list(
            Task.objects.filter(list__space__workspace=workspace)
            .order_by("created_at")[:3]
        )
        assignment_plan = [
            ["aziz@clickish.dev", "malika@clickish.dev"],
            ["jasur@clickish.dev"],
            ["malika@clickish.dev"],
        ]
        for task, emails in zip(tasks, assignment_plan):
            for member_email in emails:
                TaskAssignee.objects.get_or_create(
                    task=task,
                    user=team[member_email],
                    defaults={"assigned_by": owner},
                )

        if tasks:
            for member_email, body_html in TEAM_COMMENTS:
                author = team[member_email]
                if not Comment.objects.filter(task=tasks[0], author=author).exists():
                    create_comment(
                        tasks[0],
                        author,
                        {
                            "body_html": body_html,
                            "body_json": {"type": "doc", "content": []},
                        },
                    )

    def _print_credentials(self, email, password):
        self.stdout.write(self.style.SUCCESS(f"Login:    {email}"))
        self.stdout.write(self.style.SUCCESS(f"Password: {password}"))
