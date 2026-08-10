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
* **Magic bytes**: kengaytma yolg'on bo'lishi mumkin — yuklashda faylning
  birinchi baytlari o'qilib, e'lon qilingan turga mos kelishi tekshiriladi
  (`validate_file_signature`). Zip oilasi uchun qo'shimcha: zip-slip
  yozuvlari va decompression bomb rad etiladi.
* Har bir biriktirish/o'chirish `TaskActivity` ga yozib qo'yiladi (§10.6
  `attachment_added` / `attachment_removed`).
"""

from __future__ import annotations

import codecs
import re
import unicodedata
import zipfile
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
from apps.core.enums import ActivityVerb
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


# ---------------------------------------------------------------------------
# Fayl imzosi (magic bytes) — kengaytmaga ISHONMAYMIZ
# ---------------------------------------------------------------------------
#
# Kengaytma — bu mijoz aytgan gap, dalil emas. `.png` deb nomlangan fayl
# ichida PDF, HTML yoki bajariladigan yuk bo'lishi mumkin. Shuning uchun
# yuklashda faylning birinchi baytlari o'qilib, e'lon qilingan kengaytmaga
# mos kelishi tekshiriladi; mos kelmasa `400`.
#
# Bu tekshiruv `Content-Disposition: attachment` + `nosniff` ni ALMASHTIRMAYDI,
# ular ustiga qo'shiladi (defense in depth).

#: Imzo uchun yetarli sarlavha (eng uzuni RIFF/WEBP — 12 bayt).
SIGNATURE_READ_BYTES = 32

#: Matnli turlar uchun tekshiriladigan bo'lak — dastlabki 8 KB.
TEXT_PROBE_BYTES = 8192

#: Kengaytma → qabul qilinadigan imzo PREFIKSLARI. Kamida bittasiga mos
#: kelishi shart. Maxsus tekshiruv talab qiladigan turlar (webp, matn)
#: bu yerda emas — pastdagi to'plamlarda.
SIGNATURES: dict[str, tuple[bytes, ...]] = {
    # --- rasmlar (qat'iy) ---
    ".png": (b"\x89PNG\r\n\x1a\n",),  # PNG 8 baytlik imzo (RFC 2083 §3.1)
    ".jpg": (b"\xff\xd8\xff",),  # JPEG: SOI (FFD8) + marker boshlanishi
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),  # GIF ning ikkala versiyasi
    # --- hujjatlar ---
    ".pdf": (b"%PDF-",),  # spec talabi: `%PDF-` bilan boshlanishi SHART
    # OLE2 / Compound File Binary — eski Office (.doc/.xls/.ppt). RTF ham
    # `.doc` nomi bilan keladi (Word uni ochadi), shuning uchun ikkinchi imzo.
    ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", b"{\\rtf"),
    ".xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    ".ppt": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    # --- ZIP oilasi: OOXML hujjatlari ham oddiy zip arxivi ---
    ".zip": (b"PK\x03\x04",),
    ".docx": (b"PK\x03\x04",),
    ".xlsx": (b"PK\x03\x04",),
    ".pptx": (b"PK\x03\x04",),
}

#: RIFF konteyneri: `RIFF` + 4 bayt hajm + `WEBP`. O'rtadagi hajm o'zgaruvchi
#: bo'lgani uchun oddiy prefiks yetmaydi — alohida tekshiriladi.
WEBP_EXTENSIONS = frozenset({".webp"})

#: Imzosi yo'q turlar: UTF-8 dekodlanishi va null bayt bo'yicha tekshiriladi.
TEXT_EXTENSIONS = frozenset({".txt", ".md", ".csv"})

#: Ichini ochib ko'radigan turlar (zip-slip + decompression bomb).
ZIP_EXTENSIONS = frozenset({".zip", ".docx", ".xlsx", ".pptx"})

#: Ochilgan hajm / siqilgan hajm nisbati. Bundan yuqorisi — zip bomba.
#: Oddiy hujjat/rasm arxivida bu nisbat 1..20 atrofida bo'ladi.
ZIP_MAX_COMPRESSION_RATIO = 100

#: Arxiv ochilgandagi umumiy hajm chegarasi (nisbat past bo'lsa ham diskni
#: to'ldirib yuboradigan "sekin bomba" bo'lmasin).
ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES = 256 * 1024 * 1024

#: Arxivdagi yozuvlar soni — "million bo'sh fayl" varianti.
ZIP_MAX_ENTRIES = 5000

#: Windows disk harfi bilan boshlanadigan mutlaq yo'l: `C:\...`.
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


def _read_head(upload, size: int) -> bytes:
    """Yuklanayotgan fayldan `size` bayt o'qiydi va kursorni 0 ga qaytaradi.

    Kursorni qaytarish MAJBURIY: shundan keyin `services.create_attachment`
    faylni to'liq saqlaydi. Qaytarilmasa — fayl boshsiz saqlanadi.
    """
    try:
        upload.seek(0)
        return upload.read(size) or b""
    finally:
        upload.seek(0)


def _validate_text(head: bytes) -> None:
    """`.txt/.md/.csv` — imzosiz turlar uchun yengil sanity tekshiruv."""
    if b"\x00" in head:
        raise _invalid(
            "Matnli fayl ichida null bayt topildi — bu matn emas, binar fayl."
        )
    # Bo'lak ko'p baytli belgining o'rtasida uzilishi mumkin, shuning uchun
    # `final=False` bilan inkremental dekoder ishlatiladi.
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        decoder.decode(head, False)
    except UnicodeDecodeError:
        raise _invalid("Matnli fayl UTF-8 da emas.")


def _validate_zip(upload) -> None:
    """Zip (va OOXML) ichini ochmasdan METAMA'LUMOTI bo'yicha tekshiradi.

    * **zip-slip** — `..` segmenti yoki mutlaq yo'l bo'lgan yozuv arxivni
      butunlay rad ettiradi. Biz arxivni ochmasak ham, uni keyinchalik
      ochadigan mijoz/CI qurboni bo'lmasin.
    * **decompression bomb** — ochilgan/siqilgan nisbati
      `ZIP_MAX_COMPRESSION_RATIO` dan oshsa rad etiladi. Hech qanday bayt
      ochilmaydi: hisob markaziy katalogdagi `file_size`/`compress_size`
      maydonlaridan olinadi.
    """
    stream = getattr(upload, "file", upload)
    try:
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError, EOFError):
        raise _invalid("Arxivni o'qib bo'lmadi — fayl buzilgan yoki zip emas.")
    finally:
        try:
            stream.seek(0)
        except (OSError, ValueError):  # pragma: no cover - juda kam holat
            pass

    if len(entries) > ZIP_MAX_ENTRIES:
        raise _invalid(f"Arxivda juda ko'p yozuv bor (chegara — {ZIP_MAX_ENTRIES} ta).")

    total_raw = 0
    total_packed = 0
    for entry in entries:
        name = entry.filename.replace("\\", "/")
        if (
            name.startswith("/")
            or _DRIVE_PREFIX.match(name)
            or any(part == ".." for part in name.split("/"))
        ):
            raise _invalid(
                "Arxiv ichida xavfli yo'l topildi "
                f"({entry.filename}) — u papkadan tashqariga chiqadi."
            )
        total_raw += entry.file_size
        total_packed += entry.compress_size

    if total_raw > ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES:
        raise _invalid("Arxiv ochilganda hajmi juda katta bo'lib ketadi.")
    if total_raw and total_raw / max(total_packed, 1) > ZIP_MAX_COMPRESSION_RATIO:
        raise _invalid(
            "Arxivning siqilish nisbati shubhali darajada yuqori "
            "(«zip bomba» ehtimoli) — fayl qabul qilinmadi."
        )


def _signature_error(extension: str) -> str:
    return (
        f"Fayl mazmuni «{extension.lstrip('.')}» turiga mos kelmadi: "
        "ichki imzosi boshqa. Faylni to'g'ri kengaytma bilan yuklang."
    )


def validate_file_signature(upload, extension: str) -> None:
    """Fayl mazmuni e'lon qilingan kengaytmaga mos kelishini tekshiradi."""
    head = _read_head(upload, max(SIGNATURE_READ_BYTES, TEXT_PROBE_BYTES))

    if extension in TEXT_EXTENSIONS:
        _validate_text(head[:TEXT_PROBE_BYTES])
        return

    if extension in WEBP_EXTENSIONS:
        if not (head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
            raise _invalid(_signature_error(extension))
        return

    expected = SIGNATURES.get(extension)
    if expected and not any(head.startswith(prefix) for prefix in expected):
        raise _invalid(_signature_error(extension))

    if extension in ZIP_EXTENSIONS:
        _validate_zip(upload)


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

    # Nom ham, e'lon qilingan MIME ham mijozdan keladi — oxirgi so'z faylning
    # o'zida: birinchi baytlar kengaytmaga mos kelmasa, `400`.
    validate_file_signature(upload, extension)

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


def log_attachment_activity(task, actor, verb, attachment) -> None:
    """Vazifa tarixiga bitta qator yozadi — §10.6 lug'atining yangi ikki verbi.

    ATAYLAB shu modulda: `apps/tasks/services.py` ga tegilmaydi, lekin qator
    o'sha yerdagi `activity()`/`log_activities()` orqali quriladi — format
    boshqa verblar bilan bir xil bo'lib qoladi.

    `ATTACHMENT_ADDED` → `to_value` = fayl nomi;
    `ATTACHMENT_REMOVED` → `from_value` = fayl nomi (boshqa verblarda ham
    "yo'qolgan qiymat" `from_value` da turadi).
    """
    name = attachment.original_name
    added = verb == ActivityVerb.ATTACHMENT_ADDED
    services.log_activities(
        [
            services.activity(
                task,
                actor,
                verb,
                to_value=name if added else None,
                from_value=None if added else name,
                attachment_id=str(attachment.id),
                content_type=attachment.content_type,
                size_bytes=attachment.size_bytes,
            )
        ]
    )


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
        log_attachment_activity(
            task, request.user, ActivityVerb.ATTACHMENT_ADDED, attachment
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
        # Yozuvni o'chirishdan OLDIN olamiz: `delete()` dan keyin pk yo'qoladi.
        removed = TaskAttachment(
            id=attachment.id,
            task=task,
            original_name=attachment.original_name,
            content_type=attachment.content_type,
            size_bytes=attachment.size_bytes,
        )
        services.delete_attachment(
            attachment, request.user, client_id=client_id_of(request)
        )
        log_attachment_activity(
            task, request.user, ActivityVerb.ATTACHMENT_REMOVED, removed
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
