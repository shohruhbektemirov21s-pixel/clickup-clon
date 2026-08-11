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
from apps.core.enums import (
    ActivityVerb,
    Priority,
    TaskStatus,
    WatcherSource,
    WorkspaceRole,
)
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
            (
                "Kirishdagi yo'naltirishni tuzatish",
                TaskStatus.TODO,
                Priority.URGENT,
                ["xatolik", "backend"],
            ),
            (
                "Doskada sudrab ko'chirishni sayqallash",
                TaskStatus.IN_PROGRESS,
                Priority.HIGH,
                ["frontend"],
            ),
            (
                "Real vaqtdagi ishtirok avatarlari",
                TaskStatus.REVIEW,
                Priority.MEDIUM,
                ["frontend"],
            ),
            (
                "Statuslarni kodga o'tkazish",
                TaskStatus.DONE,
                Priority.HIGH,
                ["backend"],
            ),
        ]
        positions = evenly_spaced(len(sprint_tasks))
        created_tasks = []
        for (title, status, priority, tag_names), pos in zip(sprint_tasks, positions):
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
                completed_at=timezone.now() if status == TaskStatus.DONE else None,
            )
            TaskWatcher.objects.create(task=task, user=user, source=WatcherSource.AUTO_CREATOR)
            TaskAssignee.objects.create(task=task, user=user, assigned_by=user)
            for tag_name in tag_names:
                TaskTag.objects.create(task=task, tag=tags[tag_name])
            created_tasks.append(task)

        # Yuqoridagi sikl `pos` nomini `str` sifatida band qilgan; bu yerdagi
        # kursor esa `None` dan boshlanadi, shuning uchun alohida nom.
        backlog_pos: str | None = None
        for title in ["Tungi rejim", "Ochiq API", "Mobil ko'rinish tahlili"]:
            backlog_pos = midstring(backlog_pos, None)
            Task.objects.create(
                list=backlog,
                status=TaskStatus.TODO,
                title=title,
                position=backlog_pos,
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

        self._seed_starter_list(workspace, user)

        for tag in tags.values():
            tag.usage_count = TaskTag.objects.filter(tag=tag).count()
            tag.save(update_fields=["usage_count"])
        refresh_list_counts(sprint)
        refresh_list_counts(backlog)
        self._ensure_team(user, workspace)
        # Jamoadan KEYIN: aktorlar shu a'zolardan tanlanadi, aks holda
        # tasmadagi har bir qator `owner` nomidan chiqardi.
        self._seed_activity(created_tasks, user, workspace)

        self.stdout.write(self.style.SUCCESS(f"Workspace '{workspace.name}' seeded."))
        self._print_credentials(email, password)

    def _seed_starter_list(self, workspace, owner):
        """`Jamoa bo'limi / Boshlash` ro'yxatini ham to'ldiradi.

        `bootstrap_workspace` bu ro'yxatni ATAYLAB bo'sh qoldiradi — yangi
        hisob nolinchi holatdan boshlashi kerak. Lekin demo uchun buning
        aksi kerak: demo hisob kirganda aynan shu ro'yxatga tushadi (u
        daraxtdagi birinchisi), va u bo'sh bo'lsa butun demo "ma'lumot yo'q"
        bo'lib ko'rinadi — mazmun esa `Mahsulot` bo'limida yashiringan
        bo'ladi.
        """
        space = workspace.spaces.get(name="Jamoa bo'limi")
        task_list = space.lists.get(name="Boshlash")

        starter = [
            ("Haftalik rejani tasdiqlash", TaskStatus.IN_PROGRESS, Priority.HIGH),
            ("Mijoz uchun taqdimot tayyorlash", TaskStatus.TODO, Priority.MEDIUM),
            ("Yangi a'zolarni ish maydoniga qo'shish", TaskStatus.TODO, Priority.LOW),
            ("O'tgan sprint yakunini yozish", TaskStatus.DONE, Priority.MEDIUM),
        ]
        positions = evenly_spaced(len(starter))
        for (title, status, priority), pos in zip(starter, positions):
            task = Task.objects.create(
                list=task_list,
                status=status,
                title=title,
                description_html=f"<p>{title}.</p>",
                priority=priority,
                position=pos,
                due_date=timezone.now() + timedelta(days=2),
                created_by=owner,
                updated_by=owner,
                completed_at=timezone.now() if status == TaskStatus.DONE else None,
            )
            TaskWatcher.objects.create(task=task, user=owner, source=WatcherSource.AUTO_CREATOR)
            TaskAssignee.objects.create(task=task, user=owner, assigned_by=owner)

        refresh_list_counts(task_list)

    def _seed_activity(self, tasks, owner, workspace):
        """Demo vazifalar uchun faoliyat tarixini yozadi.

        Vazifalar yuqorida `Task.objects.create()` bilan to'g'ridan-to'g'ri
        yaratiladi — tez, lekin servis qatlamini chetlab o'tadi, ya'ni
        `TaskActivity` yozilmaydi. Natijada demo ish maydonining faoliyat
        tasmasi bo'sh bo'lib qolardi va landing'dagi «Real vaqt» bloki hech
        narsa ko'rsatmasdi. Bu yerda tarix ataylab yoziladi.

        Aktorlar jamoadan olinadi, hammasi `owner` bo'lib qolmasin: tasma
        bir nechta odam ishlayotganini ko'rsatishi kerak.
        """
        from apps.tasks.models import TaskActivity

        actors = list(
            WorkspaceMember.objects.filter(workspace=workspace)
            .exclude(user=owner)
            .select_related("user")
            .order_by("joined_at")[:3]
        )
        actor_users = [m.user for m in actors] or [owner]

        now = timezone.now()
        rows = []
        #: `(row, kerakli_vaqt)`. Vaqt ALOHIDA saqlanadi: `created_at` da
        #: `auto_now_add=True` bor va u INSERT oldidan instansiyadagi qiymatni
        #: ham bosib ketadi, ya'ni `row.created_at` ni keyin o'qib bo'lmaydi —
        #: u "hozir" bo'lib qolgan bo'lardi va hamma qator bir xil vaqtda
        #: turardi.
        stamps = []

        def add(task, actor, verb, moment, **extra):
            row = TaskActivity(task=task, actor=actor, verb=verb, **extra)
            rows.append(row)
            stamps.append(moment)

        for index, task in enumerate(tasks):
            actor = actor_users[index % len(actor_users)]
            # Ro'yxatdagi birinchi vazifa eng yangi bo'lsin.
            base = now - timedelta(minutes=7 * index)
            add(task, actor, ActivityVerb.CREATED, base - timedelta(minutes=4))
            add(
                task,
                actor,
                ActivityVerb.STATUS_CHANGED,
                base - timedelta(minutes=2),
                from_value=TaskStatus.TODO.value,
                to_value=task.status,
            )
            if task.completed_at:
                add(task, actor, ActivityVerb.COMPLETED, base)

        TaskActivity.objects.bulk_create(rows)
        for row, moment in zip(rows, stamps):
            TaskActivity.objects.filter(pk=row.pk).update(created_at=moment)

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
