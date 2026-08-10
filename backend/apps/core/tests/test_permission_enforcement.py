"""View qatlami matritsaga haqiqatan bo'ysunadimi — §B.7 ko'chirishning isboti.

Bu fayl ikki narsani qulflaydi:

* **§C.5 drift-guard** — `apps/*/views.py` da bironta ham legacy `min_role=` /
  `require_role(` qolmaganini tekshiradi. Qolsa, admin matritsani
  o'zgartirganda REST xatti-harakati o'zgarmaydi ("yolg'on nazorat").
* **R3 / AD-2** — matritsadan kod olib tashlanishi **darhol** REST javobini
  o'zgartiradi (`201` → `403`).
"""

import re
from pathlib import Path

import pytest

from conftest import assert_error

from apps.core.access import bump_permissions_version
from apps.workspaces.models import RolePermission

pytestmark = pytest.mark.django_db


APPS_DIR = Path(__file__).resolve().parents[2]

#: §C.5 whitelist. `MemberDetailView` rank guard'lari (F-1) va
#: `_owner_count()` (F-2) `ROLE_RANK` ni ishlatadi, lekin `min_role=` /
#: `require_role(` ni EMAS — shuning uchun ro'yxat bo'sh bo'lishi kutiladi.
#: `apps/core/access.py` skanerdan tashqarida: `require_role` shimi va
#: `require_membership(..., min_role=)` imzosi o'sha yerda yashaydi (§C.1).
LEGACY_WHITELIST: dict[str, tuple[str, ...]] = {}

LEGACY_RE = re.compile(r"min_role\s*=|require_role\s*\(")


def _scanned_files():
    files = sorted(APPS_DIR.glob("*/views.py"))
    files += sorted(APPS_DIR.glob("*/filters.py"))
    assert files, "views.py fayllari topilmadi — skaner yo'li buzilgan."
    return files


@pytest.mark.parametrize(
    "path", _scanned_files(), ids=lambda p: f"{p.parent.name}/{p.name}"
)
def test_no_legacy_require_role_in_views(path):
    """§C.5 — rol darajasi bo'yicha tekshiruv view'larda qolmasin."""
    allowed = LEGACY_WHITELIST.get(f"{path.parent.name}/{path.name}", ())
    offenders = [
        f"{path.parent.name}/{path.name}:{number}: {line.strip()}"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if LEGACY_RE.search(line) and not any(token in line for token in allowed)
    ]
    assert not offenders, "Legacy rol tekshiruvi qolgan:\n" + "\n".join(offenders)


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


def _rates(settings, **overrides):
    config = dict(settings.REST_FRAMEWORK)
    config["DEFAULT_THROTTLE_RATES"] = {**config["DEFAULT_THROTTLE_RATES"], **overrides}
    settings.REST_FRAMEWORK = config


def test_invite_creation_is_throttled(env, settings):
    """F-6 — `InvitationListCreateView.post` `invite` scope'iga ulangan."""
    _rates(settings, invite="1/min")
    url = f"/api/v1/workspaces/{env.workspace.id}/invitations/"

    first = env.owner_client.post(url, {"email": "a@client.com", "role": "member"},
                                  format="json")
    assert first.status_code == 201, first.content

    second = env.owner_client.post(url, {"email": "b@client.com", "role": "member"},
                                   format="json")
    assert_error(second, 429, "throttled")

    # GET (invitation.read) throttle ostida emas
    assert env.owner_client.get(url).status_code == 200


def test_invite_lookup_is_throttled(env, api, settings):
    """F-6 — public `lookup/` token brute-force'dan himoyalangan."""
    _rates(settings, invite_lookup="1/min")

    first = api.get("/api/v1/invitations/lookup/?token=nope")
    assert first.status_code == 404

    second = api.get("/api/v1/invitations/lookup/?token=nope2")
    assert_error(second, 429, "throttled")
