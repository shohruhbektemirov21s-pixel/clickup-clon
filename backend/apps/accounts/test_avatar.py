"""`POST /api/v1/me/avatar/` — ishonchsiz baytlar Pillow'ga boradigan yagona yo'l.

Nega alohida fayl: bu endpoint repo'dagi IKKINCHI fayl yuklash nuqtasi
(birinchisi — vazifa biriktirmalari, ularda 49 ta test bor), lekin bu yerda
yuklangan bayt shunchaki diskka yozilmaydi — u **dekodlanadi va qayta
o'lchamlanadi**. Ya'ni tasvir kutubxonasi hujum yuzasi bo'lib qoladi:
buzilgan fayl, "decompression bomb" (kichik fayl → gigabaytlab piksel) va
kutilmagan rang rejimi shu yerda ushlanishi kerak.

Har bir test view'dagi bitta aniq shoxni qulflaydi:

* `avatar` maydoni yo'q                     → 400
* 2 MB dan katta                            → 400 (dekodlashdan OLDIN)
* Pillow tushunadigan, lekin ruxsat etilmagan format (GIF) → 400
* Pillow umuman dekodlay olmaydigan baytlar → 400 (`except Exception`)
* decompression bomb                        → 400 (o'sha `except`)
* palitrali PNG                             → RGBA
* kulrang JPEG                              → RGB
* har qanday o'lcham                        → 256×256
* `avatar` throttle scope                   → 429
* anonim / faqat o'qish hisobi              → 401 / 403
"""

import io
import shutil
import tempfile
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.views import AVATAR_FORMATS, MAX_AVATAR_BYTES
from conftest import assert_error

pytestmark = pytest.mark.django_db

AVATAR_URL = "/api/v1/me/avatar/"


@pytest.fixture(autouse=True)
def media_root(settings):
    """Har bir test o'z MEDIA_ROOT'ida — repo `media/` iflos bo'lmaydi."""
    path = tempfile.mkdtemp(prefix="clickup-avatar-")
    settings.MEDIA_ROOT = path
    yield path
    shutil.rmtree(path, ignore_errors=True)


def image_bytes(fmt="PNG", size=(512, 512), mode="RGB", color=(200, 40, 90)):
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, format=fmt)
    return buffer.getvalue()


def upload(client, content, name="avatar.png", content_type="image/png"):
    return client.post(
        AVATAR_URL,
        {"avatar": SimpleUploadedFile(name, content, content_type=content_type)},
        format="multipart",
    )


def stored_image(user):
    """Diskka YOZILGAN faylni ochadi — javobga emas, natijaga qaraymiz."""
    user.refresh_from_db()
    with user.avatar.open("rb") as handle:
        image = Image.open(io.BytesIO(handle.read()))
        image.load()
    return image


# ------------------------------------------------------------------ rad etish


def test_avatar_field_is_required(env):
    response = env.member_client.post(AVATAR_URL, {}, format="multipart")
    error = assert_error(response, 400, "validation_error")
    assert "avatar" in error["details"]


def test_avatar_over_the_size_cap_is_rejected_before_decoding(env):
    """2 MB tekshiruvi Pillow'dan OLDIN — bomba dekodlanmaydi ham."""
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_AVATAR_BYTES

    response = upload(env.member_client, oversized)
    error = assert_error(response, 400, "validation_error")
    # Aynan HAJM shoxi ishlaganini qulflaymiz: format shoxi boshqa xabar
    # beradi, ya'ni hajm tekshiruvi olib tashlansa bu test yiqiladi.
    assert error["details"]["avatar"] == ["Avatar must be at most 2 MB."]
    env.member.refresh_from_db()
    assert not env.member.avatar


def test_a_file_exactly_at_the_cap_is_not_rejected_by_size(env):
    """Chegara `>` — roppa-rosa 2 MB o'tadi (format shoxida yiqiladi)."""
    at_cap = b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_AVATAR_BYTES - 8)
    assert len(at_cap) == MAX_AVATAR_BYTES

    error = assert_error(upload(env.member_client, at_cap), 400, "validation_error")
    assert error["details"]["avatar"] == ["Avatar must be a jpeg, png or webp image."]


@pytest.mark.parametrize(
    "fmt,name,content_type",
    [
        ("GIF", "avatar.gif", "image/gif"),
        ("BMP", "avatar.bmp", "image/bmp"),
        ("TIFF", "avatar.tiff", "image/tiff"),
    ],
)
def test_formats_outside_the_allow_list_are_rejected(env, fmt, name, content_type):
    """`AVATAR_FORMATS` — allow-list, ya'ni Pillow qo'llaydigan ~50 format emas.

    GIF/BMP/TIFF ni Pillow bemalol ochadi; ular rad etilishi kerakligi
    kontent-turdan emas, aynan shu ro'yxatdan kelib chiqadi.
    """
    assert fmt not in AVATAR_FORMATS
    error = assert_error(
        upload(env.member_client, image_bytes(fmt=fmt), name, content_type),
        400,
        "validation_error",
    )
    assert error["details"]["avatar"] == ["Avatar must be a jpeg, png or webp image."]


def test_content_type_alone_does_not_get_a_file_through(env):
    """`image/png` deb e'lon qilingan matn fayli — baribir 400.

    Mijoz beradigan `Content-Type` va kengaytma hech narsani isbotlamaydi;
    yagona haqiqat — Pillow dekodlagan `image.format`.
    """
    error = assert_error(
        upload(env.member_client, b"<?php echo 1; ?>" * 8),
        400,
        "validation_error",
    )
    assert error["details"]["avatar"] == ["Avatar must be a jpeg, png or webp image."]


def test_truncated_image_hits_the_decode_guard(env):
    """Yarim yo'lda uzilgan PNG — `except Exception` shoxi."""
    whole = image_bytes()
    truncated = whole[: len(whole) // 2]

    error = assert_error(upload(env.member_client, truncated), 400, "validation_error")
    assert error["details"]["avatar"] == ["Avatar must be a jpeg, png or webp image."]


def test_decompression_bomb_is_refused(env):
    """Kichik fayl → gigabaytlab piksel. Pillow buni `Image.open()` da otadi.

    `MAX_IMAGE_PIXELS` ni pasaytirib haqiqiy `DecompressionBombError` ni
    chaqiramiz: view'dagi keng `except Exception` aynan shuni ushlashi kerak,
    aks holda bu 500 bo'lib chiqardi.
    """
    content = image_bytes(size=(512, 512))
    with mock.patch.object(Image, "MAX_IMAGE_PIXELS", 100):
        response = upload(env.member_client, content)

    error = assert_error(response, 400, "validation_error")
    assert error["details"]["avatar"] == ["Avatar must be a jpeg, png or webp image."]


# --------------------------------------------------------------- normalizatsiya


def test_avatar_is_resized_to_a_256_square(env):
    """Har qanday o'lcham 256×256 ga keltiriladi (nisbat saqlanmaydi — shu holat)."""
    response = upload(env.member_client, image_bytes(size=(800, 200)))
    assert response.status_code == 200, response.content
    assert response.json()["avatar"]

    assert stored_image(env.member).size == (256, 256)


def test_palette_png_is_converted_to_rgba(env):
    """`P` rejimi RGB/RGBA emas → PNG uchun RGBA ga o'tkaziladi."""
    source = Image.new("P", (300, 300))
    buffer = io.BytesIO()
    source.save(buffer, format="PNG")

    response = upload(env.member_client, buffer.getvalue())
    assert response.status_code == 200, response.content

    saved = stored_image(env.member)
    assert saved.mode == "RGBA"
    assert saved.format == "PNG"


def test_grayscale_jpeg_is_converted_to_rgb(env):
    """`L` rejimi → JPEG uchun RGB.

    Bu shox shunchaki chiroyli emas, MAJBURIY: JPEG alfa kanalini saqlay
    olmaydi, ya'ni RGBA bilan `image.save(..., "JPEG")` istisno otardi.
    """
    buffer = io.BytesIO()
    Image.new("L", (300, 300), 128).save(buffer, format="JPEG")

    response = upload(env.member_client, buffer.getvalue(), "avatar.jpg", "image/jpeg")
    assert response.status_code == 200, response.content

    saved = stored_image(env.member)
    assert saved.mode == "RGB"
    assert saved.format == "JPEG"
    env.member.refresh_from_db()
    assert env.member.avatar.name.endswith(".jpg")


def test_rgba_png_keeps_its_alpha_channel(env):
    """RGB/RGBA allaqachon to'g'ri — konvertatsiya qilinmaydi."""
    response = upload(env.member_client, image_bytes(mode="RGBA", color=(1, 2, 3, 4)))
    assert response.status_code == 200, response.content
    assert stored_image(env.member).mode == "RGBA"


def test_webp_is_accepted_and_named_by_format(env):
    response = upload(env.member_client, image_bytes(fmt="WEBP"), "a.webp", "image/webp")
    assert response.status_code == 200, response.content
    env.member.refresh_from_db()
    assert env.member.avatar.name.endswith(".webp")


# ------------------------------------------------------------ kirish nazorati


def test_avatar_upload_requires_authentication(api):
    error = assert_error(
        api.post(
            AVATAR_URL,
            {"avatar": SimpleUploadedFile("a.png", image_bytes(), "image/png")},
            format="multipart",
        ),
        401,
        "authentication_failed",
    )
    assert error


def test_readonly_account_cannot_replace_its_avatar(env):
    """Demo hisob — profiliga ham yozmaydi (`BlockReadonlyAccountWrites`)."""
    env.member.is_readonly = True
    env.member.save(update_fields=["is_readonly"])

    error = assert_error(
        upload(env.member_client, image_bytes()), 403, "permission_denied"
    )
    assert "Demo hisob" in error["message"]


def test_avatar_upload_is_throttled(env):
    """`avatar` scope — dekodlash + qayta o'lchamlash eng qimmat amal.

    Autentifikatsiyalangan foydalanuvchi uni cheklovsiz chaqira olsa, bu
    bitta hisob bilan CPU'ni band qilish yo'li bo'lardi.
    """
    with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"avatar": "1/hour"}):
        first = upload(env.member_client, image_bytes())
        assert first.status_code == 200, first.content

        second = upload(env.member_client, image_bytes())
        assert_error(second, 429, "throttled")
