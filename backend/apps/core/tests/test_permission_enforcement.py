"""View qatlami matritsaga haqiqatan bo'ysunadimi — §B.7 ko'chirishning isboti.

Bu fayl uch narsani qulflaydi:

* **§C.5 drift-guard** — butun ilova kodida (nafaqat `views.py` da) bironta ham
  legacy `min_role=` / `require_role(` qolmaganini tekshiradi. Qolsa, admin
  matritsani o'zgartirganda REST xatti-harakati o'zgarmaydi ("yolg'on nazorat").
* **"Yolg'on nazorat" guard'i** — katalogdagi HAR BIR faol kod kamida bitta
  enforcement joyiga ulanganini tekshiradi. Katalog 49 kod e'lon qiladi;
  agar kod hech qayerda o'qilmasa, uni matritsada yoqib/o'chirish faqat UI'ni
  o'zgartiradi va foydalanuvchi o'zini himoyalangan deb o'ylab yuradi.
* **R3 / AD-2** — matritsadan kod olib tashlanishi **darhol** REST javobini
  o'zgartiradi (`201` → `403`).
"""

import ast
import re
from collections import defaultdict
from pathlib import Path

import pytest

from conftest import assert_error

from apps.core.access import bump_permissions_version
from apps.core.permissions import ALL_CODES, PERMISSION_BY_CODE, STAGED_CODES
from apps.workspaces.models import RolePermission

pytestmark = pytest.mark.django_db


APPS_DIR = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------- fayl skaneri


def _rel(path: Path) -> str:
    return path.relative_to(APPS_DIR).as_posix()


def _is_test(path: Path) -> bool:
    return path.name == "tests.py" or path.name.startswith("test_") or "tests" in path.parts


def _source_files() -> list[Path]:
    """Ilova kodining hammasi: testlar, migratsiyalar va bo'sh `__init__` yo'q.

    Ilgari bu yerda faqat `*/views.py` + `*/filters.py` glob'i turardi. Bu
    "authz faqat view'da bo'ladi" degan noto'g'ri taxminga tayanardi va
    `workspaces/space_members.py`, `tasks/attachments.py`, `tasks/services.py`,
    `accounts/signals.py`, `core/drf_permissions.py` kabi **haqiqatan ham
    avtorizatsiya qaror qabul qiladigan** fayllarni butunlay o'tkazib yubordi:
    o'sha fayllarga qaytarilgan legacy `require_role(` jimgina o'tib ketardi.
    Endi skaner butun `apps/` daraxtini oladi, ya'ni ertaga qo'shiladigan yangi
    modul ham avtomatik qamrab olinadi.
    """
    files = [
        path
        for path in sorted(APPS_DIR.glob("**/*.py"))
        if not _is_test(path)
        and "migrations" not in path.parts
        and path.name != "__init__.py"
    ]
    assert files, "Manba fayllar topilmadi — skaner yo'li buzilgan."
    return files


#: Ilova paketlari (`accounts`, `comments`, `core`, `realtime`, `tasks`,
#: `workspaces`). Parametrlash fayl bo'yicha emas, paket bo'yicha: 50+ ta
#: bir xil test o'rniga 6 ta, xato xabari esa baribir `fayl:qator` beradi.
APP_PACKAGES = sorted({_rel(path).split("/", 1)[0] for path in _source_files()})


# ------------------------------------------------- §C.5 legacy rol tekshiruvi

#: §C.5 whitelist. `MemberDetailView` rank guard'lari (F-1) va
#: `_owner_count()` (F-2) `ROLE_RANK` ni ishlatadi, lekin `min_role=` /
#: `require_role(` ni EMAS — shuning uchun ro'yxat bo'sh bo'lishi kutiladi.
LEGACY_WHITELIST: dict[str, tuple[str, ...]] = {}

#: `apps/core/access.py` skanerdan tashqarida: `require_role` shimi va
#: `require_membership(..., min_role=)` imzosi o'sha yerda YASHAYDI (§C.1) —
#: ta'rifning o'zi buzilish emas. Boshqa hech bir fayl bunday imtiyozga ega
#: emas.
LEGACY_SCAN_EXEMPT = frozenset({"core/access.py"})

LEGACY_RE = re.compile(r"min_role\s*=|require_role\s*\(")


@pytest.mark.parametrize("package", APP_PACKAGES)
def test_no_legacy_require_role_outside_the_access_module(package):
    """§C.5 — rol darajasi bo'yicha tekshiruv ilova kodida qolmasin."""
    files = [
        path
        for path in _source_files()
        if _rel(path).startswith(f"{package}/") and _rel(path) not in LEGACY_SCAN_EXEMPT
    ]
    offenders = []
    for path in files:
        allowed = LEGACY_WHITELIST.get(_rel(path), ())
        offenders += [
            f"{_rel(path)}:{number}: {line.strip()}"
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if LEGACY_RE.search(line) and not any(token in line for token in allowed)
        ]
    assert not offenders, "Legacy rol tekshiruvi qolgan:\n" + "\n".join(offenders)


def test_the_legacy_scanner_actually_reaches_the_authz_surface():
    """Skaner yo'li buzilsa, yuqoridagi test JIMGINA yashil bo'lib qoladi.

    Shuning uchun avtorizatsiya mantig'i yashaydigan fayllar ro'yxatdaligini
    alohida tekshiramiz — aynan shular eski `*/views.py` glob'idan tushib
    qolgan edi.
    """
    scanned = {_rel(path) for path in _source_files()}
    for path in (
        "accounts/signals.py",
        "comments/views.py",
        "core/drf_permissions.py",
        "realtime/consumers.py",
        "tasks/attachments.py",
        "tasks/filters.py",
        "tasks/services.py",
        "tasks/views.py",
        "workspaces/space_members.py",
        "workspaces/views.py",
    ):
        assert path in scanned, path


# ------------------------------------------- "yolg'on nazorat" (fake controls)

#: Kod ruxsat qaroriga aynan shu funksiyalar orqali ta'sir qiladi.
ENFORCEMENT_CALLS = frozenset(
    {
        "has_perm",
        "require_perm",
        "require_membership_perm",
        "has_space_perm",
        "require_space_perm",
    }
)

#: Enforcement joyi sanaladigan fayllar: katalogning o'zi va ruxsat MOTORI
#: hisobga olinmaydi.
#:
#: * `core/permissions.py` — kodlar ta'rifi (o'zini o'zi tasdiqlab qo'ymasin);
#: * `core/access.py` — `has_perm` ta'rifi, `SPACE_VIEWER_GRANTS` /
#:   `SPACE_MANAGER_GRANTS` / `READONLY_ALLOWED_CODES` jadvallari va §G.2
#:   Faza 4 uchun oldindan yozilgan `_acl_enabled()` shoxlari. Motor ichida
#:   kodning nomini aytish — uni ISHLATISH emas: `space.read` aynan shu
#:   sababdan bugun inert (pastdagi `STAGED_REASONS` ga qarang).
ENFORCEMENT_EXEMPT = frozenset({"core/permissions.py", "core/access.py"})

#: Nega kod hali ulanmagan — sabab test bilan birga yashaydi, ya'ni kelajakda
#: kimdir "shunchaki ro'yxatga qo'shib qo'yish" bilan qutulmaydi.
STAGED_REASONS = {
    "space.read": (
        "§G.2 Faza 4 — yagona o'quvchi `apps/core/access.py::space_is_visible()` / "
        "`visible_spaces_q()`, ikkalasi ham `_acl_enabled()` shoxida. "
        "`SPACE_ACL_ENABLED` esa `config/settings.py` da UMUMAN e'lon qilinmagan, "
        "ya'ni bayroq doim o'chiq va kod inert."
    ),
    "space.read_private": (
        "§G.2 Faza 4 — `space.read` bilan bir xil sabab: faqat `_acl_enabled()` "
        "ostida o'qiladi."
    ),
    "workspace.transfer_ownership": (
        "Alohida endpoint yo'q — egalik `PATCH members/{user_id}/` (`role=owner`) "
        "orqali o'tadi va `member.role_change` + `MemberDetailView` F-1 rank "
        "guard bilan himoyalanadi. `owner_only=True` bo'lgani uchun uni "
        "matritsada yoqib bo'lmaydi."
    ),
}


def _wired_constants(tree: ast.AST):
    """Kod satri ISHLATILGAN joylar (ta'rif ro'yxatlari emas).

    Faqat quyidagi shakllar hisobga olinadi, ya'ni `frozenset({...})` ichidagi
    grant jadvallari yoki docstring'dagi eslatma "ulangan" deb qaralmaydi:

    * chaqiruv argumenti — `require_perm(m, "task.create")`,
      `get_list(user, id, perm="task.create")`;
    * o'zlashtirish — `MANAGE_PERMISSIONS = "workspace.manage_permissions"`;
    * shartli ifoda — `"comment.delete_own" if own else "comment.delete_any"`;
    * funksiya imzosidagi sukut qiymati —
      `def require_task_editor(..., code="task.update")`.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield from node.args
            yield from (keyword.value for keyword in node.keywords)
        elif isinstance(node, ast.Assign):
            yield node.value
        elif isinstance(node, ast.IfExp):
            yield node.body
            yield node.orelse
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            yield from node.args.defaults
            yield from (default for default in node.args.kw_defaults if default is not None)


def _enforcement_index() -> dict[str, list[str]]:
    """Kod → uni ishlatadigan `fayl:qator` ro'yxati."""
    index: dict[str, list[str]] = defaultdict(list)
    for path in _source_files():
        if _rel(path) in ENFORCEMENT_EXEMPT:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _wired_constants(tree):
            if isinstance(node, ast.Constant) and node.value in ALL_CODES:
                index[node.value].append(f"{_rel(path)}:{node.lineno}")
    return index


ENFORCEMENT_INDEX = _enforcement_index()

#: Guard tekshiradigan kodlar — `staged` bo'lmagan barcha faol kodlar.
LIVE_CODES = sorted(ALL_CODES - STAGED_CODES)


@pytest.mark.parametrize("code", LIVE_CODES)
def test_every_live_permission_code_has_an_enforcement_site(code):
    """Katalogdagi har bir kod haqiqatan biror qarorga ta'sir qiladi.

    Bu — butun bir sinf xatoning oldini oladigan yagona test. Katalog 49 kod
    e'lon qiladi va ularning hammasi ruxsat matritsasi UI'sida toggle bo'lib
    turadi. Agar kod hech qayerda o'qilmasa, admin uni o'chirib qo'yadi,
    interfeys "o'chirildi" deydi, REST esa avvalgidek javob berishda davom
    etadi — bu ruxsat tizimining eng xavfli buzilish turi, chunki u XATO
    emas, YOLG'ON XAVFSIZLIK HISSI beradi.

    Kod ataylab hali ulanmagan bo'lsa, uni `PermissionDef(staged=True)` bilan
    belgilash va `STAGED_REASONS` ga sabab yozish kerak — o'shanda niyat
    hujjatlashadi.
    """
    sites = ENFORCEMENT_INDEX.get(code, [])
    assert sites, (
        f"`{code}` katalogda e'lon qilingan, lekin uni hech bir enforcement "
        f"joyi o'qimaydi — matritsadagi toggle faqat UI'ni o'zgartiradi. "
        f"Uni {sorted(ENFORCEMENT_CALLS)} chaqiruvlaridan biriga ulang yoki "
        f"`PermissionDef(staged=True)` + `STAGED_REASONS` bilan hujjatlang."
    )


def test_staged_codes_are_declared_and_explained():
    """`staged` ro'yxatiga jimgina kod qo'shib bo'lmaydi."""
    assert set(STAGED_REASONS) == set(STAGED_CODES), sorted(
        set(STAGED_REASONS) ^ set(STAGED_CODES)
    )
    for code in STAGED_CODES:
        assert code in PERMISSION_BY_CODE, code
        assert PERMISSION_BY_CODE[code].staged is True
        assert STAGED_REASONS[code].strip()


def test_staged_codes_really_are_unenforced():
    """Kod ulangandan keyin `staged` bayrog'i olib tashlanishi shart.

    Aks holda `staged` "guard'dan qutulish" tugmasiga aylanadi va bugungi
    muammo ertaga boshqa nom bilan qaytadi.
    """
    still_dead = {code: ENFORCEMENT_INDEX.get(code, []) for code in STAGED_CODES}
    wired = {code: sites for code, sites in still_dead.items() if sites}
    assert not wired, (
        "Bu kodlar endi haqiqatan ishlatilyapti — katalogdagi `staged=True` ni "
        f"va `STAGED_REASONS` yozuvini olib tashlang: {wired}"
    )


def test_space_acl_codes_stay_inert_while_the_flag_is_undefined():
    """`space.read*` nega inert — sabab kodda ko'rinib tursin.

    `_acl_enabled()` `SPACE_ACL_ENABLED` ni `getattr(..., False)` bilan
    o'qiydi, sozlama esa `config/settings.py` da yo'q. Ya'ni ikkala kod ham
    faqat o'chiq shoxda yashaydi. Sozlama qo'shilib bayroq yoqilganda bu test
    ataylab yiqiladi — o'sha paytda `staged` olib tashlanishi kerak.
    """
    from django.conf import settings

    from apps.core.access import _acl_enabled

    assert getattr(settings, "SPACE_ACL_ENABLED", None) in (None, False)
    assert _acl_enabled() is False
    assert {"space.read", "space.read_private"} <= STAGED_CODES


def test_no_enforcement_site_names_an_unknown_code():
    """Xato yozilgan kod (`task.updat`) `has_perm` da faqat DEBUG'da yiqiladi."""
    from apps.core.permissions import CODE_RE

    unknown: dict[str, list[str]] = defaultdict(list)
    for path in _source_files():
        if _rel(path) in ENFORCEMENT_EXEMPT:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name not in ENFORCEMENT_CALLS:
                continue
            for argument in [*node.args, *(kw.value for kw in node.keywords)]:
                if (
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    and CODE_RE.match(argument.value)
                    and argument.value not in ALL_CODES
                ):
                    unknown[argument.value].append(f"{_rel(path)}:{argument.lineno}")
    assert not unknown, f"Katalogda yo'q ruxsat kodlari: {dict(unknown)}"


# ------------------------------------------------------- R3 / AD-2 xulq-atvor


def _revoke(env, role, code):
    """Matritsadan bitta kodni olib tashlaydi va versiyani oshiradi (R3)."""
    RolePermission.objects.update_or_create(
        workspace=env.workspace,
        role=role,
        permission=code,
        defaults={"allowed": False},
    )
    bump_permissions_version(env.workspace)


def test_permission_revocation_changes_rest_behaviour(env):
    """Matritsadan `task.create` olib tashlansa — `201` darhol `403` bo'ladi."""
    url = f"/api/v1/lists/{env.list.id}/tasks/"

    before = env.member_client.post(url, {"title": "Avvalgi vazifa"}, format="json")
    assert before.status_code == 201, before.content

    _revoke(env, "member", "task.create")

    after = env.member_client.post(url, {"title": "Keyingi vazifa"}, format="json")
    assert_error(after, 403, "permission_denied")

    # Faqat `member` roli ta'sirlanadi — admin va owner tegilmagan.
    assert env.admin_client.post(url, {"title": "Admin"}, format="json").status_code == 201
    assert env.owner_client.post(url, {"title": "Owner"}, format="json").status_code == 201


def test_revoking_folder_cascade_leaves_detach_working(env):
    """§B.7 — `?strategy=` ikki xil kodga bo'lingani REST'da ko'rinadi."""
    created = env.admin_client.post(
        f"/api/v1/spaces/{env.space.id}/folders/", {"name": "Jild A"}, format="json"
    )
    assert created.status_code == 201, created.content
    folder_id = created.json()["id"]

    _revoke(env, "admin", "folder.delete_cascade")

    cascade = env.admin_client.delete(f"/api/v1/folders/{folder_id}/?strategy=cascade")
    assert_error(cascade, 403, "permission_denied")

    detach = env.admin_client.delete(f"/api/v1/folders/{folder_id}/?strategy=detach")
    assert detach.status_code == 204, detach.content


def test_granting_a_code_to_guest_opens_the_endpoint(env):
    """AD-2 — grant ham darhol ishlaydi (nafaqat revoke)."""
    url = f"/api/v1/lists/{env.list.id}/tasks/"
    assert_error(env.guest_client.post(url, {"title": "Yo'q"}, format="json"), 403,
                 "permission_denied")

    RolePermission.objects.update_or_create(
        workspace=env.workspace,
        role="guest",
        permission="task.create",
        defaults={"allowed": True},
    )
    bump_permissions_version(env.workspace)

    opened = env.guest_client.post(url, {"title": "Endi mumkin"}, format="json")
    assert opened.status_code == 201, opened.content


# ------------------------------------------------------------------ F-6 throttle


@pytest.fixture
def throttle_rate(monkeypatch):
    """DRF `SimpleRateThrottle.THROTTLE_RATES` klass atributiga bog'langan —
    `settings.REST_FRAMEWORK` ni almashtirish unga yetib bormaydi."""
    from rest_framework.throttling import SimpleRateThrottle

    def apply(**overrides):
        monkeypatch.setattr(
            SimpleRateThrottle,
            "THROTTLE_RATES",
            {**SimpleRateThrottle.THROTTLE_RATES, **overrides},
        )

    return apply


def test_invite_creation_is_throttled(env, throttle_rate):
    """F-6 — `InvitationListCreateView.post` `invite` scope'iga ulangan."""
    throttle_rate(invite="1/min")
    url = f"/api/v1/workspaces/{env.workspace.id}/invitations/"

    first = env.owner_client.post(url, {"email": "a@client.com", "role": "member"},
                                  format="json")
    assert first.status_code == 201, first.content

    second = env.owner_client.post(url, {"email": "b@client.com", "role": "member"},
                                   format="json")
    assert_error(second, 429, "throttled")

    # GET (invitation.read) throttle ostida emas
    assert env.owner_client.get(url).status_code == 200


def test_invite_lookup_is_throttled(api, throttle_rate):
    """F-6 — public `lookup/` token brute-force'dan himoyalangan."""
    throttle_rate(invite_lookup="1/min")

    first = api.get("/api/v1/invitations/lookup/?token=nope")
    assert first.status_code == 404

    second = api.get("/api/v1/invitations/lookup/?token=nope2")
    assert_error(second, 429, "throttled")
