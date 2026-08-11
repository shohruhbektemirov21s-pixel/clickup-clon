"""`seed_demo` yaratgan yozuvlarni bazadan olib tashlaydi — `seed_demo` ning teskarisi.

    ../.venv/Scripts/python.exe manage.py purge_demo            # faqat ko'rsatadi
    ../.venv/Scripts/python.exe manage.py purge_demo --yes      # haqiqatan o'chiradi

**Standart holat — quruq yurish (dry run).** Buyruq nima o'chishini sanab
beradi va HECH NARSANI o'zgartirmaydi. O'chirish faqat `--yes` bilan bo'ladi,
chunki bu qaytarib bo'lmaydigan amal: ish maydoni o'chganda uning bo'limlari,
ro'yxatlari, vazifalari, izohlari va biriktirmalari CASCADE bilan ketadi.

Nima o'chadi — ataylab tor: faqat `seed_demo` dagi konstantalar (`Clickish
Demo` ish maydoni va `DEMO_TEAM`/`DEMO_VIEWER` hisoblari). Qo'lda yaratilgan
ish maydoni yoki haqiqiy foydalanuvchi hech qachon tegilmaydi.

`--qa` bayrog'i qo'shimcha ravishda E2E/QA testlari qoldirgan hisoblarni ham
oladi (`qa_*@`, `qa-*@`, `rt-empty-*@`, `*@testov.uz` kabi naqshlar) — ular
`seed_demo` dan emas, avtomatlashtirilgan testlardan qoladi.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.core.management.commands.seed_demo import DEMO_EMAIL, DEMO_TEAM, DEMO_VIEWER
from apps.tasks.models import Task
from apps.workspaces.models import TaskList, Workspace
from apps.workspaces.services import refresh_list_counts

DEMO_WORKSPACE_NAME = "Clickish Demo"

#: `seed_demo` yaratadigan hisoblarning to'liq ro'yxati.
DEMO_EMAILS = frozenset({DEMO_EMAIL, DEMO_VIEWER[0], *(row[0] for row in DEMO_TEAM)})

#: `bootstrap_workspace` ning ESKI versiyasi har bir yangi ish maydoniga
#: qo'yib ketgan namuna vazifalar. Hozirgi versiya ro'yxatni bo'sh qoldiradi
#: (`apps/workspaces/services.py`), shuning uchun bular faqat eski ish
#: maydonlarida qoladi. Sarlavhalar `uzbekify_defaults.py` dagi tarjimalar.
PLACEHOLDER_TITLES = (
    "Birinchi vazifangizni yarating",
    "Vazifalarni statuslar orasida ko'chiring",
    "Jamoangizni taklif qiling",
    # Tarjimadan oldingi inglizcha asllari.
    "Create your first task",
    "Drag tasks between statuses",
    "Invite your team",
)

#: Avtomatlashtirilgan testlar qoldiradigan hisoblar (`--qa` bilan).
QA_PATTERNS = (
    Q(email__startswith="qa_")
    | Q(email__startswith="qa-")
    | Q(email__startswith="rt-empty-")
    | Q(email__startswith="e2e-")
    | Q(email__endswith="@testov.uz")
    | Q(email__contains=".tester@")
)


class Command(BaseCommand):
    help = "Remove the rows created by seed_demo. Dry run unless --yes is passed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Haqiqatan o'chirish. Bu bayroqsiz buyruq faqat hisobot beradi.",
        )
        parser.add_argument(
            "--qa",
            action="store_true",
            help="E2E/QA testlari qoldirgan hisoblarni ham qo'shish.",
        )
        parser.add_argument(
            "--placeholders",
            action="store_true",
            help=(
                "Eski `bootstrap_workspace` qoldirgan namuna vazifalarni HAR QANDAY "
                "ish maydonidan olib tashlash — faqat tegilmaganlarini."
            ),
        )
        parser.add_argument(
            "--only-placeholders",
            action="store_true",
            help=(
                "FAQAT namuna vazifalar. Demo ish maydoni va demo hisoblar "
                "tegilmaydi — demo rejim ishlab turishi kerak bo'lganda shu."
            ),
        )

    def untouched_placeholders(self):
        """Hech kim tegmagan namuna vazifalar.

        "Tegilmagan" — izohi, fayli, biriktirilgani, tavsifi va faoliyat
        yozuvi yo'q. Foydalanuvchi shu qatorni o'ziniki qilib olgan bo'lsa
        (masalan tavsif yozgan), u ARTIQ namuna emas va qoldiriladi.
        `all_objects` — soft-delete qilinganlarini ham qamraydi.
        """
        return (
            Task.all_objects.filter(
                title__in=PLACEHOLDER_TITLES,
                comment_count=0,
                attachment_count=0,
                description_html="",
            )
            .exclude(task_assignees__isnull=False)
            .exclude(activities__isnull=False)
            .distinct()
        )

    def handle(self, *args, **options):
        commit = options["yes"]
        include_qa = options["qa"]
        only_placeholders = options["only_placeholders"]
        include_placeholders = options["placeholders"] or only_placeholders

        User = get_user_model()
        if only_placeholders:
            # Demo ish maydoni ham, demo hisoblar ham tegilmaydi.
            users = User.objects.none()
            workspaces = Workspace.objects.none()
            user_ids = []
        else:
            user_filter = Q(email__in=DEMO_EMAILS)
            if include_qa:
                user_filter |= QA_PATTERNS
            # Superuser/staff hech qachon o'chmaydi: demo hisobi bilan bir xil
            # emailga ega admin bo'lsa, uni yo'qotib qo'yish qimmatga tushadi.
            users = User.objects.filter(user_filter).exclude(
                Q(is_staff=True) | Q(is_superuser=True)
            )
            user_ids = list(users.values_list("id", flat=True))

            # `Workspace.owner` PROTECT: demo hisobini o'chirish uchun avval
            # uning EGALIK QILGAN har bir ish maydoni ketishi kerak. Shuning
            # uchun nishon nomi bo'yicha topilgani bilan cheklanmaydi.
            workspaces = Workspace.objects.filter(
                Q(name=DEMO_WORKSPACE_NAME) | Q(owner_id__in=user_ids)
            )

        # Namuna vazifalar demo ish maydonidan TASHQARIDA ham bo'ladi, shuning
        # uchun ular alohida nishon: ish maydoni o'chmasa ham ular ketadi.
        placeholders = (
            self.untouched_placeholders().exclude(list__space__workspace__in=workspaces)
            if include_placeholders
            else Task.all_objects.none()
        )

        self.stdout.write(self.style.MIGRATE_HEADING("O'chiriladigan yozuvlar:"))
        self._report(workspaces, users)
        for task in placeholders.select_related("list__space__workspace"):
            self.stdout.write(
                f"  namuna vazifa {task.title!r} "
                f"({task.list.space.workspace.name!r} ichida)"
            )

        # Nishondan tashqarida ish maydoniga egalik qilayotgan hisob bo'lsa,
        # uni jimgina qoldirib ketmaymiz — PROTECT baribir to'xtatardi.
        blocked = User.objects.filter(id__in=user_ids).exclude(
            Q(owned_workspaces__isnull=True) | Q(owned_workspaces__in=workspaces)
        )
        for email in blocked.values_list("email", flat=True).distinct():
            self.stdout.write(
                self.style.WARNING(f"  ! {email} nishondan tashqari ish maydoniga ega — qoladi")
            )

        if not workspaces.exists() and not users.exists() and not placeholders.exists():
            self.stdout.write(self.style.SUCCESS("Demo yozuvlar topilmadi — baza toza."))
            return

        if not commit:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Bu quruq yurish edi — hech narsa o'chirilmadi. "
                    "Haqiqatan o'chirish uchun: manage.py purge_demo --yes"
                )
            )
            return

        deletable = users.exclude(id__in=blocked.values("id"))
        # Ro'yxatni qulflab olamiz: `workspaces.delete()` dan keyin queryset
        # qayta baholansa nishonlar siljib ketardi. `list_id` lar ham hozir
        # yig'iladi — o'chirilgandan keyin ularni vazifadan tiklab bo'lmaydi.
        placeholder_ids = list(placeholders.values_list("id", flat=True))
        placeholder_list_ids = set(placeholders.values_list("list_id", flat=True))

        with transaction.atomic():
            # 1) Vazifalar AVVAL, ataylab. `all_objects` — soft-delete
            #    qilinganlari ham ketsin, va `hard_delete()` — `delete()` bu
            #    yerda faqat `deleted_at` ni qo'yardi, ya'ni qator jadvalda
            #    qolib ketardi.
            task_count, _ = Task.all_objects.filter(
                list__space__workspace__in=workspaces
            ).hard_delete()

            # 2) Ish maydoni — bo'lim, jild, ro'yxat, a'zolik, taklif, teg va
            #    izohlar CASCADE bilan ketadi.
            workspace_count, _ = workspaces.delete()

            # 3) Hisoblar — endi ularni himoya qiladigan ish maydoni qolmadi.
            user_count, _ = deletable.delete()

            # 4) Boshqa ish maydonlaridagi tegilmagan namuna vazifalar. Ro'yxat
            #    qulflangani uchun ular o'chgan ish maydoni bilan kesishmaydi.
            placeholder_count = 0
            if placeholder_ids:
                placeholder_count, _ = Task.all_objects.filter(
                    id__in=placeholder_ids
                ).hard_delete()
                # `task_count` / `open_task_count` denormallashtirilgan —
                # o'chirish ularni o'zi yangilamaydi, yon panel eski sonni
                # ko'rsatib qolardi.
                for task_list in TaskList.objects.filter(id__in=placeholder_list_ids):
                    refresh_list_counts(task_list)

        self.stdout.write(
            self.style.SUCCESS(
                f"O'chirildi: {task_count} vazifa qatori, {workspace_count} ish maydoni "
                f"qatori, {user_count} foydalanuvchi qatori, "
                f"{placeholder_count} namuna vazifa qatori."
            )
        )

    def _report(self, workspaces, users):
        for workspace in workspaces:
            tasks = Task.all_objects.filter(list__space__workspace=workspace).count()
            self.stdout.write(
                f"  ish maydoni  {workspace.name} "
                f"({workspace.spaces.count()} bo'lim, {tasks} vazifa)"
            )
        for email in users.order_by("email").values_list("email", flat=True):
            self.stdout.write(f"  foydalanuvchi {email}")
