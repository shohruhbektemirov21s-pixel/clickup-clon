"""`GET /api/v1/public/showcase/` — landing sahifasi uchun bazadan olingan ma'lumot.

Landing (`/`) faqat tizimga KIRMAGAN mehmonga ko'rinadi (kirgan foydalanuvchini
`HomeRedirect` o'z ish maydoniga yuboradi), shuning uchun u `Authorization`
header'i yo'q holda o'qiladigan yagona ma'lumot manbaiga muhtoj.

**Nima oshkor bo'ladi — ataylab tor:**

1. `stats` va `matrix` har doim qaytadi. Ruxsat katalogi va uning standart
   matritsasi maxfiy emas: u `docs/DESIGN_PERMISSIONS.md` da ochiq
   hujjatlashtirilgan va `GET permissions/` orqali har bir a'zoga ko'rinadi.
   Statistikalar — faqat jamlangan sonlar, birorta yozuv mazmuni emas.

2. `workspace` bloki (vazifa sarlavhalari, bo'lim nomlari, faoliyat tasmasi)
   FAQAT `SHOWCASE_WORKSPACE_ID` sozlangan bo'lsa qaytadi. Sozlanmagan bo'lsa
   `null` — ya'ni default holat "hech kimning ma'lumoti internetga chiqmaydi".
   Bu ataylab opt-in: bu endpoint anonim, shuning uchun ko'rsatilgan ish
   maydonining mazmuni **butun internetga ochiq** deb hisoblanishi kerak.
   Faqat shu maqsad uchun ajratilgan namoyish ish maydonini ko'rsating.

3. Ko'rsatilgan ish maydonida ham: foydalanuvchi emaili HECH QACHON
   chiqmaydi — faqat bosh harflar (`AK`) va avatar rangi. Yopiq (private)
   bo'limlarning nomi ham, mazmuni ham chiqmaydi; ular faqat "N ta yopiq
   bo'lim bor" sifatida sanaladi.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from apps.core.enums import ActivityVerb, AssignableRole, WorkspaceRole
from apps.core.permissions import ALL_CODES, DEFAULT_MATRIX, PERMISSION_BY_CODE


class ShowcaseThrottle(SimpleRateThrottle):
    """Anonim, keshlanmagan va bir nechta COUNT(*) qiluvchi endpoint uchun bo'g'iq.

    Scope'ni `throttle_scope` atributi orqali emas, alohida sinf bilan
    belgilaymiz: `@api_view` funksiyani `WrappedAPIView` ga o'raydi va
    dekoratordan keyin funksiyaga qo'yilgan atribut `ScopedRateThrottle`
    o'qiydigan view instansiyasiga yetib bormaydi.
    """

    scope = "showcase"
    DEFAULT_RATE = "60/min"

    def get_rate(self):
        return self.THROTTLE_RATES.get(self.scope) or self.DEFAULT_RATE

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


#: Landing'dagi matritsa vizuali shu kodlarni ko'rsatadi — har bir rol darajasi
#: uchun bittadan, "yuqoridan pastga toraytirish"ni ko'rsatish uchun tanlangan.
SHOWCASE_CODES = (
    "task.create",
    "task.delete",
    "member.invite",
    "workspace.manage_permissions",
)

#: Faoliyat tasmasidagi fe'l → o'zbekcha ibora. `{title}` vazifa sarlavhasi.
VERB_PHRASE = {
    ActivityVerb.CREATED: "«{title}» vazifasini yaratdi",
    ActivityVerb.STATUS_CHANGED: "«{title}» statusini {to} ga o'tkazdi",
    ActivityVerb.ASSIGNEE_ADDED: "«{title}» vazifasiga odam biriktirdi",
    ActivityVerb.ASSIGNEE_REMOVED: "«{title}» vazifasidan biriktirilganni oldi",
    ActivityVerb.PRIORITY_CHANGED: "«{title}» ustuvorligini o'zgartirdi",
    ActivityVerb.DUE_DATE_CHANGED: "«{title}» muddatini o'zgartirdi",
    ActivityVerb.RENAMED: "vazifa nomini «{title}» ga o'zgartirdi",
    ActivityVerb.MOVED: "«{title}» vazifasini ko'chirdi",
    ActivityVerb.COMPLETED: "«{title}» vazifasini yakunladi",
    ActivityVerb.DELETED: "«{title}» vazifasini o'chirdi",
    ActivityVerb.RESTORED: "«{title}» vazifasini tikladi",
    ActivityVerb.ATTACHMENT_ADDED: "«{title}» vazifasiga fayl biriktirdi",
    ActivityVerb.ATTACHMENT_REMOVED: "«{title}» vazifasidan faylni oldi",
}

#: Faoliyat nuqtasining rangi — status turi bilan bir xil palitra.
VERB_TONE = {
    ActivityVerb.CREATED: "open",
    ActivityVerb.STATUS_CHANGED: "active",
    ActivityVerb.COMPLETED: "closed",
    ActivityVerb.ATTACHMENT_ADDED: "accent",
}

MAX_PREVIEW_TASKS = 5
MAX_PREVIEW_SPACES = 4
MAX_FEED_ITEMS = 4
MAX_ORDER_ROWS = 3


def _initials(user) -> str:
    """`Aziz Karimov` → `AK`. Email HECH QACHON manba sifatida ishlatilmaydi."""
    parts = [p for p in (user.full_name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def _person(user) -> dict:
    return {"initials": _initials(user), "color": user.avatar_color}


def _relative(moment) -> str:
    """`2026-08-11T09:12Z` → `12 daq`. Faqat qo'pol aniqlik — vizual uchun."""
    seconds = int((timezone.now() - moment).total_seconds())
    if seconds < 10:
        return "hozir"
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} daq"
    if seconds < 86400:
        return f"{seconds // 3600} soat"
    return f"{seconds // 86400} kun"


def _stats() -> dict:
    from apps.accounts.models import User
    from apps.tasks.models import Task
    from apps.workspaces.models import Space, Workspace

    return {
        "permission_codes": len(ALL_CODES),
        "roles": len(WorkspaceRole.choices),
        "workspaces": Workspace.objects.count(),
        "spaces": Space.objects.filter(archived=False).count(),
        "tasks": Task.objects.count(),  # `objects` = soft-delete'dan tirik qatorlar
        "members": User.objects.filter(is_active=True).count(),
    }


def _matrix() -> dict:
    """Ruxsat katalogining standart matritsasi — owner ustuni har doim to'liq."""
    rows = []
    for code in SHOWCASE_CODES:
        definition = PERMISSION_BY_CODE.get(code)
        if definition is None:  # katalogdan olib tashlangan kod
            continue
        rows.append(
            {
                "code": code,
                "label": definition.label,
                # owner har doim True (AD-3: owner qatori DB'da saqlanmaydi).
                "allow": [True, *(code in DEFAULT_MATRIX[r] for r in AssignableRole.values)],
            }
        )
    return {
        # Ustun tartibi `allow` massivining tartibi bilan bir xil.
        "roles": ["Egasi", *(AssignableRole(r).label for r in AssignableRole.values)],
        "rows": rows,
    }


def _workspace_block(workspace_id: str) -> dict | None:
    from apps.tasks.models import Task, TaskActivity
    from apps.workspaces.models import Space, TaskList, Workspace

    workspace = Workspace.objects.filter(pk=workspace_id).first()
    if workspace is None:
        return None

    # Yopiq bo'limlar nomi bilan chiqmaydi — faqat sanaladi.
    open_spaces = list(
        Space.objects.filter(workspace=workspace, archived=False, is_private=False).order_by(
            "position"
        )[:MAX_PREVIEW_SPACES]
    )
    private_count = Space.objects.filter(
        workspace=workspace, archived=False, is_private=True
    ).count()

    space_rows = [
        {
            "name": space.name,
            "color": space.color,
            "locked": False,
            "count": TaskList.objects.filter(space=space, archived=False).count(),
        }
        for space in open_spaces
    ]
    if private_count:
        space_rows.append(
            {
                "name": f"{private_count} ta yopiq bo'lim",
                "color": "#87909E",
                "locked": True,
                "count": private_count,
            }
        )

    # Eng band ro'yxat — namoyish uchun eng ko'p to'ldirilgani.
    task_list = (
        TaskList.objects.filter(space__workspace=workspace, space__is_private=False, archived=False)
        .order_by("-task_count")
        .first()
    )

    tasks = []
    if task_list is not None:
        queryset = (
            Task.objects.filter(list=task_list, archived=False)
            .select_related("status")
            .prefetch_related("assignees")
            .order_by("position")[:MAX_PREVIEW_TASKS]
        )
        for task in queryset:
            tasks.append(
                {
                    "title": task.title,
                    "status": task.status.type if task.status_id else "open",
                    "priority": task.priority,
                    "due": task.due_date.strftime("%d-%m") if task.due_date else None,
                    "done": task.completed_at is not None,
                    "people": [_person(u) for u in task.assignees.all()[:3]],
                }
            )

    feed = []
    activities = (
        TaskActivity.objects.filter(
            task__list__space__workspace=workspace, task__list__space__is_private=False
        )
        .select_related("actor", "task")
        .order_by("-created_at")[:MAX_FEED_ITEMS]
    )
    for activity in activities:
        template = VERB_PHRASE.get(activity.verb)
        if template is None:
            continue
        actor = activity.actor
        feed.append(
            {
                "who": (actor.full_name.split()[0] if actor and actor.full_name else "Kimdir"),
                "what": template.format(title=activity.task.title, to=activity.to_value or "—"),
                "when": _relative(activity.created_at),
                "tone": VERB_TONE.get(activity.verb, "muted"),
            }
        )

    ordering = [
        {"title": task.title, "position": task.position}
        for task in Task.objects.filter(
            list__space__workspace=workspace, list__space__is_private=False, archived=False
        ).order_by("position")[:MAX_ORDER_ROWS]
    ]

    return {
        "name": workspace.name,
        "list_name": task_list.name if task_list else None,
        "member_count": workspace.member_count,
        "spaces": space_rows,
        "tasks": tasks,
        "activity": feed,
        "ordering": ordering,
    }


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([ShowcaseThrottle])
def showcase(request):
    workspace_id = getattr(settings, "SHOWCASE_WORKSPACE_ID", "")
    block = None
    if workspace_id:
        # Yaroqsiz UUID sozlangan bo'lsa 500 emas, "namoyish yo'q" bo'lsin.
        try:
            block = _workspace_block(workspace_id)
        except ValueError, ValidationError:
            block = None
    return Response({"stats": _stats(), "matrix": _matrix(), "workspace": block})
