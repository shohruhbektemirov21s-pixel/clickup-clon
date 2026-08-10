import re
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest
from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle

from apps.comments.models import Comment
from apps.core.access import bump_permissions_version
from apps.core.enums import SpaceAccess
from apps.core.permissions import ALL_CODES
from apps.tasks.models import Task
from apps.workspaces import services as workspace_services
from apps.workspaces.models import RolePermission, SpaceMember, TaskList
from apps.workspaces.services import bootstrap_workspace
from conftest import assert_error, client_for, make_user

pytestmark = pytest.mark.django_db

DOC = {"type": "doc", "content": []}


@pytest.fixture
def task(env):
    response = env.member_client.post(
        f"/api/v1/lists/{env.list.id}/tasks/", {"title": "Discussable"}, format="json"
    )
    return response.json()


def comments_url(task_id):
    return f"/api/v1/tasks/{task_id}/comments/"


def comment_url(comment_id):
    return f"/api/v1/comments/{comment_id}/"


def post_comment(client, task_id, html="<p>hello</p>", **extra):
    return client.post(
        comments_url(task_id), {"body_html": html, "body_json": DOC, **extra}, format="json"
    )


def test_create_comment_and_count(env, task):
    response = post_comment(env.guest_client, task["id"])  # guests may comment
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["body_html"] == "<p>hello</p>"
    assert body["parent_id"] is None
    assert body["author"]["id"] == str(env.guest.id)
    assert Task.objects.get(pk=task["id"]).comment_count == 1
    # commenting auto-adds the watcher
    detail = env.member_client.get(f"/api/v1/tasks/{task['id']}/").json()
    assert str(env.guest.id) in [w["id"] for w in detail["watchers"]]


def test_both_body_fields_required(env, task):
    response = env.member_client.post(
        comments_url(task["id"]), {"body_html": "<p>x</p>"}, format="json"
    )
    assert_error(response, 400, "validation_error")

    empty = post_comment(env.member_client, task["id"], html="<script>x</script>")
    assert_error(empty, 400, "validation_error")  # empty after sanitisation


def test_replies_are_depth_one(env, task):
    parent = post_comment(env.member_client, task["id"]).json()
    reply = post_comment(env.member_client, task["id"], parent_id=parent["id"])
    assert reply.status_code == 201
    assert reply.json()["parent_id"] == parent["id"]
    assert Comment.objects.get(pk=parent["id"]).reply_count == 1

    nested = post_comment(env.member_client, task["id"], parent_id=reply.json()["id"])
    assert_error(nested, 400, "validation_error")

    other_task = env.member_client.post(
        f"/api/v1/lists/{env.list.id}/tasks/", {"title": "Other"}, format="json"
    ).json()
    cross = post_comment(env.member_client, other_task["id"], parent_id=parent["id"])
    assert_error(cross, 400, "validation_error")


def test_edit_is_author_only(env, task):
    comment = post_comment(env.member_client, task["id"]).json()
    denied = env.admin_client.patch(
        comment_url(comment["id"]),
        {"body_html": "<p>hijack</p>", "body_json": DOC},
        format="json",
    )
    assert_error(denied, 403, "permission_denied")  # admins may NOT edit others'

    edited = env.member_client.patch(
        comment_url(comment["id"]),
        {"body_html": "<p>edited</p>", "body_json": DOC},
        format="json",
    )
    assert edited.status_code == 200
    assert edited.json()["is_edited"] is True
    assert edited.json()["edited_at"] is not None


def test_delete_author_or_admin(env, task):
    comment = post_comment(env.guest_client, task["id"]).json()

    denied = env.member_client.delete(comment_url(comment["id"]))
    assert_error(denied, 403, "permission_denied")

    ok = env.admin_client.delete(comment_url(comment["id"]))  # admin+ may delete anyone's
    assert ok.status_code == 204
    assert Task.objects.get(pk=task["id"]).comment_count == 0

    listing = env.member_client.get(comments_url(task["id"])).json()
    assert listing["count"] == 0  # soft-deleted comments excluded


def test_deleted_parent_keeps_replies(env, task):
    parent = post_comment(env.member_client, task["id"]).json()
    reply = post_comment(env.guest_client, task["id"], parent_id=parent["id"]).json()
    env.member_client.delete(comment_url(parent["id"]))

    listing = env.member_client.get(comments_url(task["id"])).json()
    ids = [c["id"] for c in listing["results"]]
    assert reply["id"] in ids
    assert parent["id"] not in ids


def test_comment_pagination_is_chronological(env, task):
    for i in range(3):
        post_comment(env.member_client, task["id"], html=f"<p>c{i}</p>")
    listing = env.member_client.get(comments_url(task["id"])).json()
    assert [c["body_html"] for c in listing["results"]] == ["<p>c0</p>", "<p>c1</p>", "<p>c2</p>"]
    assert set(listing.keys()) == {"count", "next", "previous", "results"}


# ===========================================================================
# Kirish nazorati — anonim
# ===========================================================================


def test_every_comment_endpoint_requires_authentication(api, env, task):
    """Autentifikatsiyasiz hech bir izoh yo'li ochilmaydi."""
    comment = post_comment(env.member_client, task["id"]).json()

    calls = [
        ("get", comments_url(task["id"]), None),
        ("post", comments_url(task["id"]), {"body_html": "<p>x</p>", "body_json": DOC}),
        ("patch", comment_url(comment["id"]), {"body_html": "<p>x</p>", "body_json": DOC}),
        ("delete", comment_url(comment["id"]), None),
    ]
    for method, url, body in calls:
        response = (
            getattr(api, method)(url)
            if body is None
            else getattr(api, method)(url, body, format="json")
        )
        assert_error(response, 401, "authentication_failed")


# ===========================================================================
# Ijara chegarasi (cross-tenant) — begona ish maydoni HECH QACHON oshkor bo'lmaydi
# ===========================================================================
#
# Kontrakt §1.7: ish maydonidan tashqaridagi resurs uchun javob **404**, 403
# emas. 403 "bu yerda shunday obyekt bor, lekin sizga ruxsat yo'q" degani —
# ya'ni mavjudlikni tasdiqlab, ID'larni sanab chiqishga yo'l ochadi.
# `_get_comment()` buni `require_membership()` orqali qiladi va shu paytgacha
# bu yo'l umuman testlanmagan edi.


@pytest.fixture
def rival(db):
    """Butunlay boshqa ish maydoni: o'z egasi, vazifasi va izohi bilan."""
    owner = make_user("rival@other.dev", "Rival Owner")
    workspace = bootstrap_workspace(owner, name="Rival Inc.")
    task_list = workspace.spaces.get(name="Jamoa bo'limi").lists.get(name="Boshlash")
    client = client_for(owner)

    task = client.post(
        f"/api/v1/lists/{task_list.id}/tasks/", {"title": "Maxfiy ish"}, format="json"
    ).json()
    comment = post_comment(client, task["id"], html="<p>maxfiy izoh</p>").json()

    return SimpleNamespace(
        owner=owner, workspace=workspace, client=client, task=task, comment=comment
    )


def test_outsider_cannot_list_comments_on_a_foreign_task(env, rival):
    assert_error(env.owner_client.get(comments_url(rival.task["id"])), 404, "not_found")


def test_outsider_cannot_comment_on_a_foreign_task(env, rival):
    response = post_comment(env.owner_client, rival.task["id"], html="<p>salom</p>")
    assert_error(response, 404, "not_found")
    assert Comment.objects.filter(task_id=rival.task["id"]).count() == 1


def test_outsider_cannot_edit_a_foreign_comment(env, rival):
    """`_get_comment` → `require_membership` → 404 (403 EMAS)."""
    response = env.owner_client.patch(
        comment_url(rival.comment["id"]),
        {"body_html": "<p>o'zgartirdim</p>", "body_json": DOC},
        format="json",
    )
    assert_error(response, 404, "not_found")
    assert Comment.objects.get(pk=rival.comment["id"]).body_html == "<p>maxfiy izoh</p>"


def test_outsider_cannot_delete_a_foreign_comment(env, rival):
    response = env.owner_client.delete(comment_url(rival.comment["id"]))
    assert_error(response, 404, "not_found")
    assert Comment.objects.filter(pk=rival.comment["id"]).exists()


def test_a_foreign_comment_id_is_indistinguishable_from_a_missing_one(env, rival):
    """Mavjud begona izoh va umuman yo'q izoh bir xil javob berishi shart."""
    ghost = uuid.uuid4()
    real = env.owner_client.delete(comment_url(rival.comment["id"]))
    absent = env.owner_client.delete(comment_url(ghost))

    assert real.status_code == absent.status_code == 404
    assert real.json() == absent.json()


def test_reply_cannot_be_parented_to_a_comment_in_another_workspace(env, task, rival):
    """`parent_id` orqali ijara chegarasidan o'tib bo'lmaydi."""
    response = post_comment(env.member_client, task["id"], parent_id=rival.comment["id"])
    assert_error(response, 400, "validation_error")


# ===========================================================================
# Yopiq bo'lim — ko'rinuvchanlik va `comment.create`
# ===========================================================================


@pytest.fixture
def private_task(env):
    """Yopiq bo'limdagi vazifa (admin yaratadi va shu bo'lim menejeri bo'ladi)."""
    space = workspace_services.create_space(
        env.workspace, env.admin, name="Yopiq loyiha", is_private=True
    )
    task_list = TaskList.objects.create(
        space=space, name="Yopiq ro'yxat", position="n", created_by=env.admin
    )
    response = env.admin_client.post(
        f"/api/v1/lists/{task_list.id}/tasks/", {"title": "Yopiq ish"}, format="json"
    )
    assert response.status_code == 201, response.content
    return SimpleNamespace(space=space, list=task_list, task=response.json())


def test_guest_cannot_see_or_comment_inside_a_private_space(env, private_task):
    """`check_space_visible` → 404: mehmon uchun bo'lim umuman mavjud emas."""
    assert_error(env.guest_client.get(comments_url(private_task.task["id"])), 404, "not_found")
    assert_error(
        post_comment(env.guest_client, private_task.task["id"]), 404, "not_found"
    )


def test_guest_added_to_the_private_space_may_comment(env, private_task):
    """`SpaceMember` qatori ko'rinuvchanlikni ochadi (legacy qoida, R20)."""
    SpaceMember.objects.create(
        space=private_task.space, user=env.guest, access=SpaceAccess.CONTRIBUTOR
    )
    response = post_comment(env.guest_client, private_task.task["id"])
    assert response.status_code == 201, response.content


def test_space_viewer_may_read_but_not_comment(env, private_task):
    """"Eng past huquq g'olib" (B.5): `comment.create` `SPACE_VIEWER_GRANTS` da yo'q.

    Bu `require_space_perm(membership, space, "comment.create")` ning yagona
    haqiqiy sinovi: `viewer` bo'lim ichida rolidan qat'i nazar yoza olmaydi.
    """
    SpaceMember.objects.create(
        space=private_task.space, user=env.member, access=SpaceAccess.VIEWER
    )
    assert env.member_client.get(comments_url(private_task.task["id"])).status_code == 200
    assert_error(
        post_comment(env.member_client, private_task.task["id"]), 403, "permission_denied"
    )


def test_space_viewer_cannot_edit_a_comment_they_already_wrote(env, private_task):
    """`comment.update_own` ham `SPACE_VIEWER_GRANTS` da yo'q."""
    SpaceMember.objects.create(
        space=private_task.space, user=env.member, access=SpaceAccess.CONTRIBUTOR
    )
    comment = post_comment(env.member_client, private_task.task["id"]).json()

    SpaceMember.objects.filter(space=private_task.space, user=env.member).update(
        access=SpaceAccess.VIEWER
    )
    response = env.member_client.patch(
        comment_url(comment["id"]),
        {"body_html": "<p>yangi</p>", "body_json": DOC},
        format="json",
    )
    assert_error(response, 403, "permission_denied")


def test_a_comment_in_a_private_space_is_404_for_a_guest(env, private_task):
    """`_get_comment` → `check_space_visible` → izoh ID'si ham oshkor bo'lmaydi."""
    comment = post_comment(env.admin_client, private_task.task["id"]).json()

    assert_error(env.guest_client.delete(comment_url(comment["id"])), 404, "not_found")
    assert_error(
        env.guest_client.patch(
            comment_url(comment["id"]),
            {"body_html": "<p>x</p>", "body_json": DOC},
            format="json",
        ),
        404,
        "not_found",
    )


# ===========================================================================
# Ruxsat matritsasi izohlar ustida haqiqatan ishlaydi
# ===========================================================================


def revoke(workspace, role, code):
    RolePermission.objects.update_or_create(
        workspace=workspace, role=role, permission=code, defaults={"allowed": False}
    )
    bump_permissions_version(workspace)


def grant(workspace, role, code):
    RolePermission.objects.update_or_create(
        workspace=workspace, role=role, permission=code, defaults={"allowed": True}
    )
    bump_permissions_version(workspace)


def test_revoking_comment_create_closes_the_endpoint(env, task):
    assert post_comment(env.member_client, task["id"]).status_code == 201

    revoke(env.workspace, "member", "comment.create")

    assert_error(post_comment(env.member_client, task["id"]), 403, "permission_denied")


def test_revoking_comment_update_own_blocks_the_author(env, task):
    comment = post_comment(env.member_client, task["id"]).json()
    revoke(env.workspace, "member", "comment.update_own")

    response = env.member_client.patch(
        comment_url(comment["id"]),
        {"body_html": "<p>yangi</p>", "body_json": DOC},
        format="json",
    )
    assert_error(response, 403, "permission_denied")


def test_revoking_comment_delete_any_leaves_delete_own_working(env, task):
    """`views.py` kodni muallifga qarab tanlaydi — ikkalasi mustaqil."""
    foreign = post_comment(env.guest_client, task["id"], html="<p>mehmon</p>").json()
    own = post_comment(env.admin_client, task["id"], html="<p>admin</p>").json()

    revoke(env.workspace, "admin", "comment.delete_any")

    assert_error(env.admin_client.delete(comment_url(foreign["id"])), 403, "permission_denied")
    assert env.admin_client.delete(comment_url(own["id"])).status_code == 204


def test_revoking_comment_delete_own_leaves_delete_any_working(env, task):
    own = post_comment(env.admin_client, task["id"], html="<p>admin</p>").json()
    foreign = post_comment(env.guest_client, task["id"], html="<p>mehmon</p>").json()

    revoke(env.workspace, "admin", "comment.delete_own")

    assert_error(env.admin_client.delete(comment_url(own["id"])), 403, "permission_denied")
    assert env.admin_client.delete(comment_url(foreign["id"])).status_code == 204


# ===========================================================================
# "Boshqaning izohini hech kim tahrirlay olmaydi" — ruxsatdan USTUN invariant
# ===========================================================================
#
# `views.py` dagi izoh: "`comment.update_any` kodi ataylab mavjud emas".
# Ilgari buni faqat oddiy admin uchun test qilingandi, ya'ni "admin'da bu kod
# yo'q ekan" degan xulosa bilan chalkashib ketardi. Quyidagi uchta test
# invariant RUXSATDAN QAT'I NAZAR amal qilishini isbotlaydi.


def test_owner_holding_every_code_still_cannot_edit_a_foreign_comment(env, task):
    """Owner `ALL_CODES` ga ega (AD-3 short-circuit) — baribir 403."""
    comment = post_comment(env.member_client, task["id"]).json()

    response = env.owner_client.patch(
        comment_url(comment["id"]),
        {"body_html": "<p>egasi tahrirladi</p>", "body_json": DOC},
        format="json",
    )
    assert_error(response, 403, "permission_denied")
    assert Comment.objects.get(pk=comment["id"]).body_html == "<p>hello</p>"


def test_granting_the_whole_catalog_does_not_unlock_foreign_edits(env, task):
    """Mehmonga katalogdagi HAR BIR kod berilsa ham begona izoh tegilmaydi."""
    comment = post_comment(env.member_client, task["id"]).json()
    for code in sorted(ALL_CODES):
        RolePermission.objects.update_or_create(
            workspace=env.workspace, role="guest", permission=code,
            defaults={"allowed": True},
        )
    bump_permissions_version(env.workspace)

    response = env.guest_client.patch(
        comment_url(comment["id"]),
        {"body_html": "<p>mehmon tahrirladi</p>", "body_json": DOC},
        format="json",
    )
    assert_error(response, 403, "permission_denied")


def test_comment_update_any_is_not_a_grantable_code(env):
    """Kod katalogda YO'Q, ya'ni uni matritsa orqali ixtiro qilib bo'lmaydi."""
    assert "comment.update_any" not in ALL_CODES

    response = env.owner_client.put(
        f"/api/v1/workspaces/{env.workspace.id}/role-permissions/",
        {
            "expected_version": env.workspace.permissions_version,
            "roles": {"admin": {"comment.update_any": True}},
        },
        format="json",
    )
    assert_error(response, 400, "validation_error")


# ===========================================================================
# XSS — ilovadagi eng yuqori ta'sirli yuza
# ===========================================================================
#
# Izoh matni har bir hamkasbning brauzerida `dangerouslySetInnerHTML` bilan
# chiziladi. Ya'ni bitta o'tib ketgan payload = butun jamoada saqlanadigan
# (stored) XSS: sessiya o'g'irlash, ruxsatlarni o'zgartirish, hamma narsa.
# Ilgari bu yerda faqat yalang'och `<script>` teg testlangan edi — u eng
# oddiy va eng kam uchraydigan holat.
#
# Har bir payload oldiga zararsiz matn qo'shiladi: aks holda tozalashdan
# keyin tana bo'sh qolib 400 bo'lardi va biz "nima saqlandi" ni ko'ra
# olmasdik.

XSS_PAYLOADS = {
    "img_onerror": '<img src=x onerror="alert(1)">',
    "svg_onload": "<svg onload=alert(1)></svg>",
    "body_onload": '<body onload="alert(1)">',
    "javascript_href": '<a href="javascript:alert(1)">bos</a>',
    "javascript_href_mixed_case": '<a href="JaVaScRiPt:alert(1)">bos</a>',
    "javascript_href_padded": '<a href="  javascript:alert(1)">bos</a>',
    "javascript_href_entity": '<a href="java&#115;cript:alert(1)">bos</a>',
    "data_uri_href": '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">yuk</a>',
    "iframe": '<iframe src="https://evil.example/steal"></iframe>',
    "iframe_srcdoc": '<iframe srcdoc="&lt;script&gt;alert(1)&lt;/script&gt;"></iframe>',
    "object": '<object data="javascript:alert(1)"></object>',
    "embed": '<embed src="https://evil.example/x.swf">',
    "external_script": '<script src="https://evil.example/x.js"></script>',
    "style_expression": "<style>body{background:url('javascript:alert(1)')}</style>",
    "inline_style_attr": '<p style="background:url(javascript:alert(1))">matn</p>',
    "onmouseover_on_allowed_tag": '<p onmouseover="alert(1)">hover</p>',
    "onclick_on_allowed_tag": '<a href="https://ok.example" onclick="alert(1)">bos</a>',
    "nested_script_tags": "<scr<script>ipt>alert(1)</scr</script>ipt>",
    "double_encoded": "&lt;img src=x onerror=alert(1)&gt;",
    "form_action": '<form action="https://evil.example"><input name="p"></form>',
    "meta_refresh": '<meta http-equiv="refresh" content="0;url=https://evil.example">',
    "base_tag": '<base href="https://evil.example/">',
    "mxss_mglyph": "<math><mtext><table><mglyph><style><!--</style>"
    '<img src=x onerror="alert(1)">',
    "noscript_breakout": "<noscript><p title=\"</noscript><img src=x onerror=alert(1)>\">",
    "svg_foreignobject": "<svg><foreignObject><script>alert(1)</script></foreignObject></svg>",
}

#: Chiqishda BO'LMASLIGI shart bo'lgan konstruksiyalar.
DANGEROUS_TAG_RE = re.compile(
    r"<\s*/?\s*(script|iframe|svg|object|embed|style|math|form|meta|base|link|"
    r"noscript|body|img|input|foreignobject|mglyph|mtext|table)\b",
    re.IGNORECASE,
)
EVENT_HANDLER_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
JS_URL_RE = re.compile(r"javascript\s*:", re.IGNORECASE)
DATA_URL_RE = re.compile(r"data\s*:", re.IGNORECASE)


#: Haqiqiy markup — ya'ni brauzer teg sifatida o'qiydigan qism. `nh3` xavfli
#: kirishni ko'pincha o'chirmaydi, balki **ekranlaydi**: `&lt;img onerror=…&gt;`
#: chiqishda qoladi, lekin u endi matn, teg emas. Hodisa atributi / `javascript:`
#: / `data:` faqat tegning ICHIDA bo'lsa xavfli, shuning uchun ularni butun
#: satrda emas, aynan shu qismda qidiramiz — aks holda test xavfsiz ekranlangan
#: matnni ham nuqson deb hisoblab, yolg'on signal beradi.
MARKUP_RE = re.compile(r"<[^>]*>")


def assert_sanitised(html):
    assert not DANGEROUS_TAG_RE.search(html), f"xavfli teg qoldi: {html!r}"
    markup = " ".join(MARKUP_RE.findall(html))
    assert not EVENT_HANDLER_RE.search(markup), f"hodisa atributi qoldi: {html!r}"
    assert not JS_URL_RE.search(markup), f"javascript: URL qoldi: {html!r}"
    assert not DATA_URL_RE.search(markup), f"data: URL qoldi: {html!r}"
    assert "style=" not in markup.lower(), f"inline style qoldi: {html!r}"


@pytest.mark.parametrize("name", sorted(XSS_PAYLOADS), ids=sorted(XSS_PAYLOADS))
def test_xss_payloads_are_stripped_on_create(env, task, name):
    payload = XSS_PAYLOADS[name]
    response = post_comment(env.member_client, task["id"], html=f"<p>Salom</p>{payload}")
    assert response.status_code == 201, response.content

    body = response.json()["body_html"]
    assert_sanitised(body)
    # Zararsiz qism saqlanadi — ya'ni sanitizer hamma narsani o'chirib
    # yubormayapti (aks holda bu testlar bo'sh natijada ham yashil bo'lardi).
    assert "Salom" in body
    # Bazadagi qiymat ham tozalangan: `body_html` javob paytida emas,
    # YOZISHDAN OLDIN tozalanadi.
    assert Comment.objects.get(pk=response.json()["id"]).body_html == body


@pytest.mark.parametrize("name", sorted(XSS_PAYLOADS), ids=sorted(XSS_PAYLOADS))
def test_xss_payloads_are_stripped_on_edit(env, task, name):
    """Tahrirlash yo'li ham o'sha validatordan o'tishi shart."""
    comment = post_comment(env.member_client, task["id"]).json()
    response = env.member_client.patch(
        comment_url(comment["id"]),
        {"body_html": f"<p>Salom</p>{XSS_PAYLOADS[name]}", "body_json": DOC},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert_sanitised(response.json()["body_html"])
    assert Comment.objects.get(pk=comment["id"]).body_html == response.json()["body_html"]


def test_body_json_is_stored_verbatim_and_is_not_rendered_html(env, task):
    """`body_json` — ProseMirror hujjati; u HTML sifatida chizilmaydi.

    Shuning uchun u tozalanmaydi, lekin buni ATAYLAB qulflaymiz: kimdir uni
    kelajakda `innerHTML` ga bersa, bu test o'sha qarorni ko'rsatib turadi.
    """
    doc = {"type": "doc", "content": [{"type": "text", "text": "<script>alert(1)</script>"}]}
    response = env.member_client.post(
        comments_url(task["id"]), {"body_html": "<p>ok</p>", "body_json": doc}, format="json"
    )
    assert response.status_code == 201, response.content
    assert response.json()["body_json"] == doc


def test_safe_rich_text_survives_sanitisation(env, task):
    """Sanitizer ruxsat etilgan formatlashni buzmaydi."""
    rich = (
        "<p><strong>qalin</strong> <em>qiya</em> <code>kod</code></p>"
        "<ul><li>bir</li><li>ikki</li></ul>"
        "<blockquote>iqtibos</blockquote>"
    )
    body = post_comment(env.member_client, task["id"], html=rich).json()["body_html"]
    for fragment in ("<strong>qalin</strong>", "<em>qiya</em>", "<li>bir</li>", "<blockquote>"):
        assert fragment in body


def test_external_links_get_noopener_noreferrer(env, task):
    """`target=_blank` bilan ochilgan havola `window.opener` ni bermasin."""
    html = '<p><a href="https://example.com" target="_blank">havola</a></p>'
    body = post_comment(env.member_client, task["id"], html=html).json()["body_html"]

    assert 'href="https://example.com"' in body
    assert "noopener" in body and "noreferrer" in body


def test_body_longer_than_the_cap_is_rejected(env, task):
    """20 000 belgi — tozalangan matn bo'yicha o'lchanadi."""
    long_html = "<p>" + ("a" * 20_001) + "</p>"
    assert_error(post_comment(env.member_client, task["id"], html=long_html), 400,
                 "validation_error")


def test_whitespace_only_after_sanitisation_is_rejected(env, task):
    """Faqat xavfli teglardan iborat tana — bo'sh izoh yaratmaydi."""
    for payload in ("<script>alert(1)</script>", "<iframe></iframe>", "   ", "<svg/onload=x>"):
        assert_error(
            post_comment(env.member_client, task["id"], html=payload), 400, "validation_error"
        )
    assert Comment.objects.filter(task_id=task["id"]).count() == 0


# ===========================================================================
# `comments` throttle scope — faqat POST
# ===========================================================================


def test_comment_creation_is_throttled(env, task):
    with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"comments": "1/min"}):
        first = post_comment(env.member_client, task["id"], html="<p>bir</p>")
        assert first.status_code == 201, first.content

        second = post_comment(env.member_client, task["id"], html="<p>ikki</p>")
        assert_error(second, 429, "throttled")


def test_reading_comments_is_not_throttled(env, task):
    """`get_throttles()` metodga qarab qaror qiladi — o'qish chelakni yemaydi."""
    post_comment(env.member_client, task["id"])
    # Sozlash POST'i chelakka yozildi. Stavka pastda 1/min ga tushirilgani uchun
    # o'sha bitta yozuv byudjetni to'ldirib qo'yardi va oxirgi POST o'qishlar
    # aybi bilan emas, sozlash aybi bilan 429 olardi.
    cache.clear()

    with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"comments": "1/min"}):
        for _ in range(5):
            assert env.member_client.get(comments_url(task["id"])).status_code == 200

        # ...va o'qishlar POST chelagini bo'shatmagan/to'ldirmagan.
        assert post_comment(env.member_client, task["id"], html="<p>hali ham</p>").status_code == 201


def test_editing_and_deleting_are_not_under_the_comments_scope(env, task):
    """`CommentDetailView` throttle'siz — bu ataylab, POST'dan farqli."""
    comment = post_comment(env.member_client, task["id"]).json()

    with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"comments": "1/min"}):
        for index in range(4):
            response = env.member_client.patch(
                comment_url(comment["id"]),
                {"body_html": f"<p>{index}</p>", "body_json": DOC},
                format="json",
            )
            assert response.status_code == 200, response.content
        assert env.member_client.delete(comment_url(comment["id"])).status_code == 204
