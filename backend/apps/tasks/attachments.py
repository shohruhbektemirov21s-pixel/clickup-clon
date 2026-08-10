"""Vazifa biriktirmalari — docs/API_CONTRACT.md §10.7.

Bu modul `apps/tasks/views.py` dan ATAYLAB ajratilgan: u yerdagi kirish
nazorati helper'lari (`get_task`) faqat **import** qilinadi, nusxalanmaydi —
shunda 404-vs-403 tartibi (§C.4) va yopiq bo'lim ko'rinishi bir joyda qoladi.

XAVFSIZLIK QOIDALARI (binding):

* Maksimal hajm — `settings.MAX_ATTACHMENT_BYTES` (`MAX_ATTACHMENT_MB`, 10 MB).
* Kengaytma allow-list; `.svg`, `.html`, `.js`, `.exe`, `.bat`, `.sh` va
  boshqa bajariladigan/faol turlar QAT'IYAN taqiqlangan. SVG — saqlanadigan
  XSS vektori, shuning uchun ro'yxatda yo'q.
* Diskdagi fayl nomi SERVERDA generatsiya qilinadi (`<uuid4>.<ext>`), mijoz
  nomi faqat `original_name` da ko'rsatish uchun saqlanadi → path traversal
  ("../../etc/passwd") va ikki karra kengaytma ("a.php.png") ta'sirsiz.
* Yuklab olish faqat shu endpoint orqali: `Content-Disposition: attachment`
  (RFC 5987) + `X-Content-Type-Options: nosniff`. `MEDIA_URL` ostidagi
  to'g'ridan-to'g'ri havola serializatsiya qilinmaydi.
* `Content-Type` mijozdan olinmaydi — kengaytmadan kanonik qiymat qo'yiladi.
* `attachment` throttle scope (30/hour).
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse
from rest_framework import status as http
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.access import require_space_perm
from apps.core.api import client_id_of, paginate
from apps.core.exceptions import ApiError
from apps.tasks import services
from apps.tasks.models import TaskAttachment
from apps.tasks.serializers import TaskAttachmentSerializer
from apps.tasks.views import get_task

#: Kengaytma → kanonik MIME turi. Bu ro'yxatdan tashqari hamma narsa `400`.
#: Yangi tur qo'shishdan oldin o'zingizga savol bering: brauzer uni bir xil
#: origin ichida BAJARA oladimi? Ha bo'lsa — qo'shmang.
ALLOWED_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".zip": "application/zip",
}

#: Ruxsat etilgan MIME qiymatlari (mijoz e'lon qilgan turni tekshirish uchun).
ALLOWED_MIME_TYPES = frozenset(ALLOWED_TYPES.values())

#: Mijoz "men bilmayman" deganda yuboradigan turlar — kengaytma hal qiladi.
NEUTRAL_MIME_TYPES = frozenset({"", "application/octet-stream", "binary/octet-stream"})

#: Aniq nom bilan rad etiladigan kengaytmalar — foydalanuvchiga tushunarli
#: xabar berish uchun (umumiy "ro'yxatda yo'q" o'rniga).
DENIED_EXTENSIONS = frozenset(
    {
        ".svg", ".svgz", ".html", ".htm", ".xhtml", ".xml", ".xsl",
        ".js", ".mjs", ".cjs", ".jsx", ".ts", ".vbs", ".wsf",
        ".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".dll", ".sys",
        ".sh", ".bash", ".zsh", ".ps1", ".psm1", ".jar", ".apk", ".app",
        ".php", ".phtml", ".py", ".rb", ".pl", ".cgi", ".asp", ".aspx",
        ".jsp", ".lnk", ".reg", ".hta", ".swf",
    }
)

#: `original_name` uchun xavfli belgilar (boshqaruv belgilari, yo'l
#: ajratgichlari, sarlavhani buzadigan qo'shtirnoq).
_UNSAFE_NAME_CHARS = re.compile(r'[\x00-\x1f\x7f"\\/:*?<>|]')

MAX_ORIGINAL_NAME_LENGTH = 255


def _invalid(message: str, field: str = "file"):
    return ApiError(
        "Request payload is invalid.",
        details={field: [message]},
        code="validation_error",
    )


def sanitize_original_name(raw: str) -> str:
    """Mijoz nomini KO'RSATISH uchun tozalaydi (saqlash nomi emas)."""
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = unicodedata.normalize("NFC", name)
    name = _UNSAFE_NAME_CHARS.sub("_", name).strip().lstrip(".")
    if len(name) > MAX_ORIGINAL_NAME_LENGTH:
        stem, _, ext = name.rpartition(".")
        keep = MAX_ORIGINAL_NAME_LENGTH - len(ext) - 1
        name = f"{stem[:keep]}.{ext}" if ext and keep > 0 else name[:MAX_ORIGINAL_NAME_LENGTH]
    return name or "fayl"


def _extension_of(name: str) -> str:
    _, dot, ext = name.rpartition(".")
    return f".{ext.lower()}" if dot else ""


def validate_upload(request) -> tuple[object, str, str, str]:
    """`(upload, original_name, content_type, extension)` yoki `400`.

    Vazifa holati (`closed` / `completed_at`) BU YERDA HAM, chaqiruvchida ham
    tekshirilmaydi — bajarilgan vazifaga biriktirish ataylab ruxsat etilgan.
    """
    upload = request.FILES.get("file")
    if upload is None:
        raise _invalid("Fayl yuborilmadi.")

    if upload.size == 0:
        raise _invalid("Fayl bo'sh.")
    limit = settings.MAX_ATTACHMENT_BYTES
    if upload.size > limit:
        raise _invalid(
            f"Fayl hajmi {settings.MAX_ATTACHMENT_MB} MB dan oshmasligi kerak."
        )

    original_name = sanitize_original_name(upload.name)
    extension = _extension_of(original_name)
    if extension in DENIED_EXTENSIONS:
        raise _invalid(
            f"«{extension}» turidagi fayllar xavfsizlik sababli qabul qilinmaydi."
        )
    if extension not in ALLOWED_TYPES:
        raise _invalid(
            "Bu fayl turi qo'llab-quvvatlanmaydi. Ruxsat etilganlar: "
            + ", ".join(sorted(e.lstrip(".") for e in ALLOWED_TYPES))
            + "."
        )

    declared = (getattr(upload, "content_type", "") or "").split(";")[0].strip().lower()
    if declared not in NEUTRAL_MIME_TYPES and declared not in ALLOWED_MIME_TYPES:
        raise _invalid(f"«{declared}» MIME turi qo'llab-quvvatlanmaydi.")

    # Mijoz turiga ishonmaymiz: kanonik qiymat kengaytmadan olinadi.
    return upload, original_name, ALLOWED_TYPES[extension], extension


def content_disposition(filename: str) -> str:
    """RFC 6266 + RFC 5987: ASCII zaxira nom + `filename*` UTF-8 kodlash."""
    ascii_name = (
        unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
    )
    ascii_name = re.sub(r'[\\"\r\n]', "_", ascii_name).strip() or "file"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def get_attachment(user, attachment_id):
    """`(attachment, task, membership)` — begona workspace fayli → 404."""
    attachment = (
        TaskAttachment.objects.select_related("uploaded_by")
        .filter(pk=attachment_id)
        .first()
    )
    if attachment is None:
        raise NotFound()
    # Kirish nazorati vazifa orqali: workspace scope + yopiq bo'lim ko'rinishi.
    task, membership = get_task(user, attachment.task_id)
    return attachment, task, membership


class TaskAttachmentsView(APIView):
    """`GET|POST tasks/{task_id}/attachments/`."""

    parser_classes = [MultiPartParser, FormParser]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "attachment"
            return [ScopedRateThrottle()]
        return []

    def get(self, request, task_id):
        task, membership = get_task(request.user, task_id)
        require_space_perm(membership, task.list.space, "attachment.read")
        attachments = (
            TaskAttachment.objects.filter(task=task)
            .select_related("uploaded_by")
            .order_by("-created_at")
        )
        return paginate(request, attachments, TaskAttachmentSerializer)

    def post(self, request, task_id):
        task, membership = get_task(request.user, task_id)
        require_space_perm(membership, task.list.space, "attachment.create")
        # ATAYLAB: `task.completed_at` / `status.type == "closed"` tekshirilmaydi.
        # Bajarilgan vazifaga hujjat biriktirish mahsulot talabi (§10.7).
        upload, original_name, content_type, extension = validate_upload(request)
        attachment = services.create_attachment(
            task,
            request.user,
            upload=upload,
            original_name=original_name,
            content_type=content_type,
            extension=extension,
            client_id=client_id_of(request),
        )
        return Response(
            TaskAttachmentSerializer(attachment, context={"request": request}).data,
            status=http.HTTP_201_CREATED,
        )


class AttachmentDetailView(APIView):
    """`DELETE attachments/{id}/` — o'ziniki vs boshqaniki ikki xil kod."""

    def delete(self, request, attachment_id):
        attachment, task, membership = get_attachment(request.user, attachment_id)
        code = (
            "attachment.delete_own"
            if attachment.uploaded_by_id == request.user.id
            else "attachment.delete_any"
        )
        require_space_perm(membership, task.list.space, code)
        services.delete_attachment(
            attachment, request.user, client_id=client_id_of(request)
        )
        return Response(status=http.HTTP_204_NO_CONTENT)


class AttachmentDownloadView(APIView):
    """`GET attachments/{id}/download/` — yagona o'qish yo'li."""

    def get(self, request, attachment_id):
        attachment, task, membership = get_attachment(request.user, attachment_id)
        require_space_perm(membership, task.list.space, "attachment.read")
        try:
            handle = attachment.file.open("rb")
        except (FileNotFoundError, ValueError):
            # Fayl saqlashdan yo'qolgan — mavjudligini oshkor qilmaymiz.
            raise NotFound()
        response = FileResponse(handle, content_type=attachment.content_type)
        response["Content-Disposition"] = content_disposition(attachment.original_name)
        # Brauzer turni "taxmin qilib" HTML sifatida ochib yubormasin.
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
