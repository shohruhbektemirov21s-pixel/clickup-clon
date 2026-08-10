"""Vazifa biriktirmalari — docs/API_CONTRACT.md §10.7.

Asosiy mahsulot talabi shu faylda qulflangan: **bajarilgan (yopilgan)
vazifaga ham fayl biriktirib bo'ladi**
(`test_upload_to_completed_task_is_allowed`).
"""

import shutil
import tempfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.core.enums import StatusType
from apps.tasks.attachments import content_disposition, sanitize_original_name
from apps.tasks.models import Task, TaskAttachment
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
    for name in ("bir.pdf", "ikki.png"):
        created = env.member_client.post(
            attachments_url(task.id),
            {"file": upload(name, b"\x89PNG\r\n\x1a\n data", "image/png")},
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
