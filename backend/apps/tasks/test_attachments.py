"""Vazifa biriktirmalari — docs/API_CONTRACT.md §10.7.

Asosiy mahsulot talabi shu faylda qulflangan: **bajarilgan (yopilgan)
vazifaga ham fayl biriktirib bo'ladi**
(`test_upload_to_completed_task_is_allowed`).
"""

import io
import os
import pathlib
import shutil
import tempfile
import time
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings

from apps.core.enums import ActivityVerb, StatusType
from apps.tasks.attachments import (
    content_disposition,
    sanitize_original_name,
    validate_file_signature,
)
from apps.tasks.models import Task, TaskActivity, TaskAttachment
from apps.workspaces.models import Space, TaskList
from apps.workspaces.services import bootstrap_workspace
from conftest import assert_error, client_for, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(settings):
    """Har bir test o'z MEDIA_ROOT'ida ishlaydi — repo media/ iflos bo'lmaydi."""
    path = tempfile.mkdtemp(prefix="clickup-attach-")
    settings.MEDIA_ROOT = path
    yield path
    shutil.rmtree(path, ignore_errors=True)


def attachments_url(task_id):
    return f"/api/v1/tasks/{task_id}/attachments/"


def attachment_url(attachment_id, suffix=""):
    return f"/api/v1/attachments/{attachment_id}/{suffix}"


def upload(name="hisobot.pdf", content=b"%PDF-1.7 salom", content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


@pytest.fixture
def task(env):
    response = env.member_client.post(
        f"/api/v1/lists/{env.list.id}/tasks/", {"title": "Fayl kerak"}, format="json"
    )
    assert response.status_code == 201, response.content
    return Task.objects.get(pk=response.json()["id"])


@pytest.fixture
def closed_task(env):
    """Yopiq (`closed`) statusdagi vazifa — `completed_at` to'ldirilgan."""
    closed = next(s for s in env.statuses if s.type == StatusType.CLOSED)
    response = env.member_client.post(
        f"/api/v1/lists/{env.list.id}/tasks/",
        {"title": "Bajarilgan vazifa", "status_id": str(closed.id)},
        format="json",
    )
    assert response.status_code == 201, response.content
    task = Task.objects.get(pk=response.json()["id"])
    assert task.completed_at is not None
    assert task.status.type == StatusType.CLOSED
    return task


# ------------------------------------------------------------------ happy path


def test_member_uploads_attachment(env, task):
    response = env.member_client.post(
        attachments_url(task.id), {"file": upload()}, format="multipart"
    )
    assert response.status_code == 201, response.content
    body = response.json()

    assert body["original_name"] == "hisobot.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(b"%PDF-1.7 salom")
    assert body["uploaded_by"]["email"] == env.member.email
    assert body["download_url"].endswith(f"/api/v1/attachments/{body['id']}/download/")
    # `file` (xom yo'l) hech qachon serializatsiya qilinmaydi.
    assert "file" not in body

    attachment = TaskAttachment.objects.get(pk=body["id"])
    # Diskdagi nom serverda generatsiya qilingan — mijoz nomi emas.
    assert "hisobot" not in attachment.file.name
    assert attachment.file.name.startswith("attachments/")
    assert attachment.file.name.endswith(".pdf")

    task.refresh_from_db()
    assert task.attachment_count == 1


def test_attachment_count_appears_on_the_task(env, task):
    assert env.member_client.get(f"/api/v1/tasks/{task.id}/").json()["attachment_count"] == 0
    env.member_client.post(attachments_url(task.id), {"file": upload()}, format="multipart")
    assert env.member_client.get(f"/api/v1/tasks/{task.id}/").json()["attachment_count"] == 1


def test_list_attachments_is_paginated_newest_first(env, task):
    # Mazmun kengaytmaga MOS bo'lishi shart (imzo tekshiruvi) — shuning uchun
    # `.pdf` ga PDF, `.png` ga haqiqiy PNG beriladi.
    for name, payload, mime in (
        ("bir.pdf", b"%PDF-1.7 salom", "application/pdf"),
        ("ikki.png", REAL_PNG, "image/png"),
    ):
        created = env.member_client.post(
            attachments_url(task.id),
            {"file": upload(name, payload, mime)},
            format="multipart",
        )
        assert created.status_code == 201, created.content

    response = env.guest_client.get(attachments_url(task.id))  # guest o'qiy oladi
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 2
    assert [r["original_name"] for r in body["results"]] == ["ikki.png", "bir.pdf"]


# ---------------------------------------------------- ASOSIY TALAB: yopiq vazifa


def test_upload_to_completed_task_is_allowed(env, closed_task):
    """Bajarilgan vazifaga biriktirish — mahsulot talabi, `201` bo'lishi SHART."""
    response = env.member_client.post(
        attachments_url(closed_task.id),
        {"file": upload("yakuniy-hisobot.pdf")},
        format="multipart",
    )
    assert response.status_code == 201, response.content
    assert response.json()["original_name"] == "yakuniy-hisobot.pdf"

    closed_task.refresh_from_db()
    assert closed_task.completed_at is not None  # holat o'zgarmaydi
    assert closed_task.attachment_count == 1


def test_delete_and_download_work_on_a_completed_task(env, closed_task):
    created = env.member_client.post(
        attachments_url(closed_task.id), {"file": upload()}, format="multipart"
    )
    attachment_id = created.json()["id"]

    download = env.member_client.get(attachment_url(attachment_id, "download/"))
    assert download.status_code == 200

    removed = env.member_client.delete(attachment_url(attachment_id))
    assert removed.status_code == 204


# -------------------------------------------------------------------- ruxsatlar


def test_guest_cannot_upload(env, task):
    response = env.guest_client.post(
        attachments_url(task.id), {"file": upload()}, format="multipart"
    )
    assert_error(response, 403, "permission_denied")
    assert TaskAttachment.objects.count() == 0


def test_owner_can_delete_own_attachment(env, task):
    created = env.member_client.post(
        attachments_url(task.id), {"file": upload()}, format="multipart"
    )
    attachment_id = created.json()["id"]

    response = env.member_client.delete(attachment_url(attachment_id))
    assert response.status_code == 204
    assert not TaskAttachment.objects.filter(pk=attachment_id).exists()
    task.refresh_from_db()
    assert task.attachment_count == 0


def test_member_cannot_delete_someone_elses_attachment(env, task):
    other = make_user("member2@test.dev", "Member Five")
    from apps.core.enums import WorkspaceRole
    from apps.workspaces.models import WorkspaceMember

    WorkspaceMember.objects.create(
        workspace=env.workspace, user=other, role=WorkspaceRole.MEMBER
    )
    created = client_for(other).post(
        attachments_url(task.id), {"file": upload()}, format="multipart"
    )
    attachment_id = created.json()["id"]

    assert_error(
        env.member_client.delete(attachment_url(attachment_id)), 403, "permission_denied"
    )
    assert TaskAttachment.objects.filter(pk=attachment_id).exists()


def test_admin_can_delete_someone_elses_attachment(env, task):
    created = env.member_client.post(
        attachments_url(task.id), {"file": upload()}, format="multipart"
    )
    attachment_id = created.json()["id"]

    response = env.admin_client.delete(attachment_url(attachment_id))
    assert response.status_code == 204


def test_guest_cannot_delete(env, task):
    created = env.member_client.post(
        attachments_url(task.id), {"file": upload()}, format="multipart"
    )
    assert_error(
        env.guest_client.delete(attachment_url(created.json()["id"])),
        403,
        "permission_denied",
    )


# ------------------------------------------------------------------- validatsiya


@override_settings(MAX_ATTACHMENT_BYTES=1024, MAX_ATTACHMENT_MB=1)
def test_file_over_the_size_limit_is_rejected(env, task):
    big = SimpleUploadedFile("katta.pdf", b"x" * 2048, content_type="application/pdf")
    response = env.member_client.post(
        attachments_url(task.id), {"file": big}, format="multipart"
    )
    error = assert_error(response, 400, "validation_error")
    assert "MB" in error["details"]["file"][0]
    assert TaskAttachment.objects.count() == 0


def test_ten_megabyte_limit_is_the_default(env, task, settings):
    assert settings.MAX_ATTACHMENT_BYTES == 10 * 1024 * 1024
    too_big = SimpleUploadedFile(
        "katta.pdf", b"x" * (10 * 1024 * 1024 + 1), content_type="application/pdf"
    )
    response = env.member_client.post(
        attachments_url(task.id), {"file": too_big}, format="multipart"
    )
    assert_error(response, 400, "validation_error")


@pytest.mark.parametrize(
    "name,content_type",
    [
        ("xss.svg", "image/svg+xml"),
        ("virus.exe", "application/x-msdownload"),
        ("sahifa.html", "text/html"),
        ("skript.js", "text/javascript"),
        ("run.sh", "application/x-sh"),
        ("run.bat", "application/x-bat"),
    ],
)
def test_dangerous_extensions_are_rejected(env, task, name, content_type):
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile(name, b"<svg onload=alert(1)>", content_type)},
        format="multipart",
    )
    assert_error(response, 400, "validation_error")
    assert TaskAttachment.objects.count() == 0


def test_unknown_extension_is_rejected(env, task):
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile("data.bin", b"\x00\x01", "application/octet-stream")},
        format="multipart",
    )
    assert_error(response, 400, "validation_error")


def test_mismatched_declared_mime_is_rejected(env, task):
    """`.png` deb nomlangan, lekin `image/svg+xml` deb e'lon qilingan fayl."""
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile("evil.png", b"<svg/onload=alert(1)>", "image/svg+xml")},
        format="multipart",
    )
    assert_error(response, 400, "validation_error")


def test_empty_file_is_rejected(env, task):
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile("bosh.pdf", b"", "application/pdf")},
        format="multipart",
    )
    assert_error(response, 400, "validation_error")


def test_missing_file_field_is_rejected(env, task):
    response = env.member_client.post(attachments_url(task.id), {}, format="multipart")
    assert_error(response, 400, "validation_error")


def test_path_traversal_name_never_reaches_storage(env, task):
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": upload("../../../../etc/passwd.txt", b"root:x:0:0", "text/plain")},
        format="multipart",
    )
    assert response.status_code == 201, response.content
    attachment = TaskAttachment.objects.get(pk=response.json()["id"])
    assert attachment.original_name == "passwd.txt"
    assert ".." not in attachment.file.name
    assert attachment.file.name.startswith("attachments/")


def test_sanitize_original_name_unit():
    assert sanitize_original_name("../../etc/passwd") == "passwd"
    assert sanitize_original_name("C:\\Users\\a\\hisobot.pdf") == "hisobot.pdf"
    assert sanitize_original_name('bad"name.txt') == "bad_name.txt"
    assert sanitize_original_name("") == "fayl"
    assert len(sanitize_original_name("a" * 400 + ".pdf")) <= 255


# ---------------------------------------------------------------- tenant chegarasi


def test_attachment_on_a_foreign_workspace_task_is_404(env):
    outsider_workspace = bootstrap_workspace(env.outsider, name="Boshqa MChJ")
    space = Space.objects.filter(workspace=outsider_workspace).first()
    foreign_list = TaskList.objects.filter(space=space).first()
    created = env.outsider_client.post(
        f"/api/v1/lists/{foreign_list.id}/tasks/", {"title": "Begona"}, format="json"
    )
    foreign_task_id = created.json()["id"]

    # Yuklash → 404 (403 EMAS: mavjudligi oshkor qilinmaydi).
    response = env.member_client.post(
        attachments_url(foreign_task_id), {"file": upload()}, format="multipart"
    )
    assert_error(response, 404, "not_found")

    # Ro'yxat ham 404.
    assert_error(env.member_client.get(attachments_url(foreign_task_id)), 404, "not_found")

    # Begona faylni o'qish/o'chirish ham 404.
    uploaded = env.outsider_client.post(
        attachments_url(foreign_task_id), {"file": upload()}, format="multipart"
    )
    assert uploaded.status_code == 201, uploaded.content
    foreign_attachment_id = uploaded.json()["id"]
    assert_error(
        env.member_client.get(attachment_url(foreign_attachment_id, "download/")),
        404,
        "not_found",
    )
    assert_error(
        env.member_client.delete(attachment_url(foreign_attachment_id)), 404, "not_found"
    )


def test_unknown_attachment_is_404(env):
    import uuid

    assert_error(env.member_client.delete(attachment_url(uuid.uuid4())), 404, "not_found")


# ------------------------------------------------------------------- yuklab olish


def test_download_returns_attachment_disposition(env, task):
    created = env.member_client.post(
        attachments_url(task.id),
        {"file": upload("hisobot.pdf", b"%PDF-1.7 salom")},
        format="multipart",
    )
    response = env.member_client.get(attachment_url(created.json()["id"], "download/"))

    assert response.status_code == 200
    disposition = response["Content-Disposition"]
    assert disposition.startswith("attachment;")
    assert 'filename="hisobot.pdf"' in disposition
    assert "filename*=UTF-8''hisobot.pdf" in disposition
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Type"] == "application/pdf"
    assert b"".join(response.streaming_content) == b"%PDF-1.7 salom"


def test_download_encodes_non_ascii_names_rfc5987(env, task):
    created = env.member_client.post(
        attachments_url(task.id),
        {"file": upload("hisobot — o'zbekcha.pdf", b"%PDF-1.7")},
        format="multipart",
    )
    response = env.member_client.get(attachment_url(created.json()["id"], "download/"))
    disposition = response["Content-Disposition"]
    assert disposition.startswith("attachment;")
    assert "filename*=UTF-8''" in disposition
    # ASCII zaxira nomi ham bo'lishi shart (eski mijozlar uchun).
    assert 'filename="' in disposition


def test_content_disposition_unit():
    value = content_disposition("hisobot.pdf")
    assert value == "attachment; filename=\"hisobot.pdf\"; filename*=UTF-8''hisobot.pdf"
    assert "\r" not in content_disposition("a\r\nb.pdf")


def test_guest_can_download(env, task):
    created = env.member_client.post(
        attachments_url(task.id), {"file": upload()}, format="multipart"
    )
    response = env.guest_client.get(attachment_url(created.json()["id"], "download/"))
    assert response.status_code == 200


def test_anonymous_cannot_read_attachments(api, env, task):
    created = env.member_client.post(
        attachments_url(task.id), {"file": upload()}, format="multipart"
    )
    response = api.get(attachment_url(created.json()["id"], "download/"))
    assert response.status_code == 401


# --------------------------------------------------------------------- throttle


def test_upload_is_throttled(env, task, monkeypatch):
    from rest_framework.throttling import SimpleRateThrottle

    monkeypatch.setattr(
        SimpleRateThrottle,
        "THROTTLE_RATES",
        {**SimpleRateThrottle.THROTTLE_RATES, "attachment": "1/hour"},
    )
    first = env.member_client.post(
        attachments_url(task.id), {"file": upload()}, format="multipart"
    )
    assert first.status_code == 201, first.content

    second = env.member_client.post(
        attachments_url(task.id), {"file": upload("ikkinchi.pdf")}, format="multipart"
    )
    assert_error(second, 429, "throttled")

    # GET throttle ostida emas.
    assert env.member_client.get(attachments_url(task.id)).status_code == 200


# ============================================================ fayl imzosi (magic bytes)
#
# Kengaytma — mijoz aytgan gap. Bu blok faylning ICHI e'lon qilingan turga
# mos kelishini tekshiradi (`attachments.validate_file_signature`).

#: Eng kichik haqiqiy PNG (1x1, shaffof) — imzo + IHDR + IDAT + IEND.
REAL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IENDsalom"
)


def zip_bytes(entries, compression=zipfile.ZIP_STORED):
    """`{nom: mazmun}` dan xotirada zip arxivi yasaydi."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def test_png_named_file_with_pdf_content_is_rejected(env, task):
    """`.png` deb nomlangan, lekin ichi PDF bo'lgan fayl — 400."""
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile("rasm.png", b"%PDF-1.7 aslida hujjat", "image/png")},
        format="multipart",
    )
    error = assert_error(response, 400, "validation_error")
    assert "mos kelmadi" in error["details"]["file"][0]
    assert TaskAttachment.objects.count() == 0


def test_real_png_is_accepted(env, task):
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile("rasm.png", REAL_PNG, "image/png")},
        format="multipart",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == len(REAL_PNG)
    # Imzo tekshiruvi kursorni qaytargan bo'lishi SHART — fayl to'liq saqlanadi.
    download = env.member_client.get(attachment_url(body["id"], "download/"))
    assert b"".join(download.streaming_content) == REAL_PNG


@pytest.mark.parametrize(
    "name,content_type,payload",
    [
        ("rasm.jpg", "image/jpeg", b"\x89PNG\r\n\x1a\n emas jpeg"),
        ("rasm.gif", "image/gif", b"not a gif at all"),
        ("rasm.webp", "image/webp", b"RIFF\x00\x00\x00\x00NOPExxxx"),
        ("hujjat.pdf", "application/pdf", b"MZ\x90\x00 bajariladigan fayl"),
        ("arxiv.zip", "application/zip", b"not a zip"),
    ],
)
def test_content_that_contradicts_the_extension_is_rejected(
    env, task, name, content_type, payload
):
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile(name, payload, content_type)},
        format="multipart",
    )
    assert_error(response, 400, "validation_error")
    assert TaskAttachment.objects.count() == 0


def test_valid_zip_is_accepted(env, task):
    payload = zip_bytes({"hisobot.txt": b"salom dunyo"})
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile("arxiv.zip", payload, "application/zip")},
        format="multipart",
    )
    assert response.status_code == 201, response.content


@pytest.mark.parametrize(
    "entry_name",
    ["../../etc/passwd", "papka/../../chiqdi.txt", "/etc/shadow", "C:/Windows/evil.txt"],
)
def test_zip_slip_entries_are_rejected(env, task, entry_name):
    """Arxiv ichidagi `..` yoki mutlaq yo'l — butun arxiv rad etiladi."""
    payload = zip_bytes({entry_name: b"root:x:0:0"})
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile("arxiv.zip", payload, "application/zip")},
        format="multipart",
    )
    error = assert_error(response, 400, "validation_error")
    assert "xavfli yo'l" in error["details"]["file"][0]
    assert TaskAttachment.objects.count() == 0


def test_decompression_bomb_is_rejected(env, task):
    """5 MB nol bayt bir necha KB ga siqiladi — nisbat 100 dan yuqori."""
    payload = zip_bytes({"bomba.bin": b"\x00" * (5 * 1024 * 1024)}, zipfile.ZIP_DEFLATED)
    assert len(payload) < 100 * 1024  # arxivning o'zi kichkina
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile("arxiv.zip", payload, "application/zip")},
        format="multipart",
    )
    error = assert_error(response, 400, "validation_error")
    assert "zip bomba" in error["details"]["file"][0]
    assert TaskAttachment.objects.count() == 0


def test_docx_is_checked_as_a_zip_too(env, task):
    """OOXML hujjatlari ham zip — ular ham zip-slip tekshiruvidan o'tadi."""
    payload = zip_bytes({"../qochdi.xml": b"<w:document/>"})
    response = env.member_client.post(
        attachments_url(task.id),
        {
            "file": SimpleUploadedFile(
                "hujjat.docx",
                payload,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        format="multipart",
    )
    assert_error(response, 400, "validation_error")


def test_text_file_with_a_null_byte_is_rejected(env, task):
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile("izoh.txt", b"salom\x00dunyo", "text/plain")},
        format="multipart",
    )
    error = assert_error(response, 400, "validation_error")
    assert "null bayt" in error["details"]["file"][0]


def test_text_file_that_is_not_utf8_is_rejected(env, task):
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile("izoh.csv", b"\xff\xfe\xfa nomalum kodlash", "text/csv")},
        format="multipart",
    )
    assert_error(response, 400, "validation_error")


def test_utf8_text_with_uzbek_letters_is_accepted(env, task):
    body = "o'zbekcha matn — ҳарфлар ҳам".encode("utf-8")
    response = env.member_client.post(
        attachments_url(task.id),
        {"file": SimpleUploadedFile("izoh.txt", body, "text/plain")},
        format="multipart",
    )
    assert response.status_code == 201, response.content


def test_validate_file_signature_unit():
    from django.core.files.uploadedfile import SimpleUploadedFile as F

    validate_file_signature(F("a.png", REAL_PNG), ".png")  # xato bermaydi
    with pytest.raises(Exception):
        validate_file_signature(F("a.png", b"%PDF-1.7"), ".png")


# ================================================================ TaskActivity izi


def test_upload_writes_a_task_activity_row(env, task):
    created = env.member_client.post(
        attachments_url(task.id), {"file": upload("shartnoma.pdf")}, format="multipart"
    )
    assert created.status_code == 201, created.content

    row = TaskActivity.objects.get(task=task, verb=ActivityVerb.ATTACHMENT_ADDED)
    assert row.actor_id == env.member.id
    assert row.to_value == "shartnoma.pdf"
    assert row.from_value is None
    assert row.metadata["attachment_id"] == created.json()["id"]
    assert row.metadata["content_type"] == "application/pdf"

    # §10.6 endpoint yangi verbni ham qaytara olishi kerak.
    feed = env.member_client.get(f"/api/v1/tasks/{task.id}/activity/")
    assert feed.status_code == 200, feed.content
    assert "attachment_added" in [r["verb"] for r in feed.json()["results"]]


def test_delete_writes_a_task_activity_row(env, task):
    created = env.member_client.post(
        attachments_url(task.id), {"file": upload("shartnoma.pdf")}, format="multipart"
    )
    attachment_id = created.json()["id"]
    assert env.member_client.delete(attachment_url(attachment_id)).status_code == 204

    row = TaskActivity.objects.get(task=task, verb=ActivityVerb.ATTACHMENT_REMOVED)
    assert row.from_value == "shartnoma.pdf"
    assert row.to_value is None
    assert row.metadata["attachment_id"] == attachment_id
    # Qator vazifa o'chirilmaguncha qoladi — fayl ketsa ham iz qoladi.
    assert not TaskAttachment.objects.filter(pk=attachment_id).exists()


def test_activity_verbs_fit_the_column():
    """`attachment_removed` 18 belgi — `verb` maydoni undan qisqa bo'lmasin."""
    limit = TaskActivity._meta.get_field("verb").max_length
    assert max(len(value) for value in ActivityVerb.values) <= limit


# ======================================================== prune_attachments buyrug'i


def orphan_file(env, task, *, age_days=30):
    """Yuklab, DB qatorini queryset orqali o'chiradi (cascade taqlidi).

    `TaskAttachment.objects.delete()` — bu aynan cascade yo'li: qator ketadi,
    diskdagi fayl qoladi. Fayl vaqti orqaga suriladi, chunki buyruq yangi
    fayllarga ataylab tegmaydi.
    """
    created = env.member_client.post(
        attachments_url(task.id), {"file": upload()}, format="multipart"
    )
    assert created.status_code == 201, created.content
    attachment = TaskAttachment.objects.get(pk=created.json()["id"])
    path = pathlib.Path(attachment.file.path)
    TaskAttachment.objects.filter(pk=attachment.pk).delete()
    old = time.time() - age_days * 86400
    os.utime(path, (old, old))
    assert path.exists()
    return path


def run_prune(*args):
    out = io.StringIO()
    call_command("prune_attachments", *args, stdout=out, stderr=out)
    return out.getvalue()


def test_prune_dry_run_reports_but_keeps_the_orphan(env, task):
    path = orphan_file(env, task)
    output = run_prune()
    assert "DRY-RUN" in output
    assert path.name in output
    assert path.exists(), "dry-run hech narsani o'chirmasligi kerak"


def test_prune_delete_removes_the_orphan(env, task):
    path = orphan_file(env, task)
    output = run_prune("--delete")
    assert "O'chirildi: 1" in output
    assert not path.exists()


def test_prune_never_touches_a_file_that_still_has_a_row(env, task):
    created = env.member_client.post(
        attachments_url(task.id), {"file": upload()}, format="multipart"
    )
    attachment = TaskAttachment.objects.get(pk=created.json()["id"])
    path = pathlib.Path(attachment.file.path)
    old = time.time() - 30 * 86400
    os.utime(path, (old, old))

    run_prune("--delete")
    assert path.exists()
    assert TaskAttachment.objects.filter(pk=attachment.pk).exists()


def test_prune_skips_recent_orphans(env, task):
    """Hozirgina yuklangan orfan fayl 7 kunlik oynada himoyalangan."""
    path = orphan_file(env, task, age_days=0)
    output = run_prune("--delete")
    assert path.exists()
    assert "yangi" in output


def test_prune_older_than_days_window_can_be_widened(env, task):
    path = orphan_file(env, task, age_days=10)
    assert path.exists()
    run_prune("--delete", "--older-than-days", "30")
    assert path.exists(), "10 kunlik fayl 30 kunlik oynaga tushmaydi"
    run_prune("--delete", "--older-than-days", "5")
    assert not path.exists()


def test_prune_dry_run_flag_beats_delete(env, task):
    path = orphan_file(env, task)
    run_prune("--delete", "--dry-run")
    assert path.exists()


def test_prune_reports_nothing_when_the_folder_is_clean(media_root):
    os.makedirs(os.path.join(media_root, "attachments"), exist_ok=True)
    assert "Orfan fayl topilmadi" in run_prune()


def test_prune_handles_a_missing_folder(media_root):
    assert "Papka topilmadi" in run_prune()
