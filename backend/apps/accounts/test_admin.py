"""AppSec B.2 — `/admin/` qattiqlashtirilganini isbotlovchi testlar.

Bu yerdagi har bir test bitta aniq regressiyani ushlaydi:

* admin butunlay yopiq (staff bo'lmaganlar uchun) va sozlanadigan yo'lda turadi;
* `delete_selected` hech bir muhim modelda yo'q (soft-delete'ni chetlab
  o'tuvchi ommaviy o'chirish);
* `LogEntry` audit jurnali ko'rinadi, lekin uni tahrirlash/o'chirish mumkin emas;
* `delete_*` ruxsati berilgan oddiy staff ham `User` o'chira olmaydi;
* muvaffaqiyatsiz kirish urinishi jurnalga tushadi.
"""

import logging

import pytest
from django.conf import settings
from django.contrib import admin as django_admin
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import authenticate
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, RequestFactory
from django.urls import reverse

from apps.accounts.models import User
from apps.comments.models import Comment
from apps.tasks.models import Task, TaskActivity
from apps.workspaces.models import RolePermission, Workspace, WorkspaceMember
from conftest import PASSWORD, make_user

pytestmark = pytest.mark.django_db

#: 1-band: bulk o'chirish shu modellarning hech birida bo'lmasligi kerak.
HARDENED_MODELS = [User, Workspace, WorkspaceMember, Task, Comment]


# --------------------------------------------------------------------- utils


def staff_user(**flags):
    user = make_user("staff@test.dev", "Staff Member")
    user.is_staff = True
    for name, value in flags.items():
        setattr(user, name, value)
    user.save()
    return user


def superuser():
    user = make_user("root@test.dev", "Root User")
    user.is_staff = True
    user.is_superuser = True
    user.save()
    return user


def grant(user, model, *codenames):
    ct = ContentType.objects.get_for_model(model)
    user.user_permissions.add(
        *Permission.objects.filter(content_type=ct, codename__in=codenames)
    )
    # `ModelBackend` ruxsatlarni instansiyada keshlaydi.
    return User.objects.get(pk=user.pk)


def logged_in(user):
    client = Client()
    assert client.login(email=user.email, password=PASSWORD)
    return client


def admin_for(model):
    return django_admin.site._registry[model]


def request_from(user):
    request = RequestFactory().get("/")
    request.user = user
    return request


@pytest.fixture
def auth_log(caplog):
    """`apps` logger'i `propagate=False` — caplog handler'ini qo'lda ulaymiz."""
    logger = logging.getLogger("apps.accounts.auth")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="apps.accounts.auth")
    yield caplog
    logger.removeHandler(caplog.handler)


# ------------------------------------------------------- admin kirish nazorati


def test_admin_is_mounted_on_configured_path():
    """`ADMIN_URL` env orqali ko'chiriladi — test yo'lni qattiq yozmaydi."""
    assert reverse("admin:index") == f"/{settings.ADMIN_URL}"


def test_anonymous_is_redirected_to_admin_login(client):
    response = client.get(reverse("admin:index"))
    assert response.status_code == 302
    assert "/login/" in response["Location"]


def test_non_staff_user_cannot_enter_admin():
    user = make_user("plain@test.dev", "Plain User")
    response = logged_in(user).get(reverse("admin:index"))
    assert response.status_code == 302
    assert "/login/" in response["Location"]
    # ...va login sahifasi ham uni ichkariga qo'ymaydi.
    login_page = logged_in(user).get(response["Location"])
    assert login_page.status_code == 200


# ------------------------------------------------- 1-band: bulk delete yo'qligi


@pytest.mark.parametrize("model", HARDENED_MODELS, ids=lambda m: m.__name__)
def test_delete_selected_action_is_removed(model):
    """Superuser uchun ham `delete_selected` ro'yxatda bo'lmasligi kerak."""
    request = request_from(superuser())
    assert "delete_selected" not in admin_for(model).get_actions(request)


@pytest.mark.parametrize("model", HARDENED_MODELS, ids=lambda m: m.__name__)
def test_only_superuser_may_delete(model):
    model_admin = admin_for(model)
    assert model_admin.has_delete_permission(request_from(staff_user())) is False
    assert model_admin.has_delete_permission(request_from(superuser())) is True


def test_staff_does_not_see_delete_selected_on_user_changelist():
    user = grant(staff_user(), User, "view_user", "change_user", "delete_user")
    response = logged_in(user).get(reverse("admin:accounts_user_changelist"))
    assert response.status_code == 200
    assert b'value="delete_selected"' not in response.content


def test_non_superuser_staff_cannot_delete_user():
    """`delete_user` ruxsati berilgan bo'lsa ham o'chirish sahifasi yopiq."""
    victim = make_user("victim@test.dev", "Victim")
    user = grant(staff_user(), User, "view_user", "change_user", "delete_user")
    client = logged_in(user)

    url = reverse("admin:accounts_user_delete", args=[victim.pk])
    assert client.get(url).status_code == 403
    assert client.post(url, {"post": "yes"}).status_code == 403
    assert User.objects.filter(pk=victim.pk).exists()


# ------------------------------------------------- 2-band: LogEntry o'zgarmas


def make_log_entry(user):
    return LogEntry.objects.log_actions(
        user_id=user.pk,
        queryset=[user],
        action_flag=ADDITION,
        change_message="test yozuvi",
        single_object=True,
    )


def test_logentry_admin_is_registered_and_fully_readonly():
    model_admin = admin_for(LogEntry)
    request = request_from(superuser())
    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False
    assert set(model_admin.get_readonly_fields(request)) == {
        "action_time",
        "user",
        "content_type",
        "object_id",
        "object_repr",
        "action_flag",
        "change_message",
    }


def test_logentry_pages_expose_no_write_form():
    root = superuser()
    entry = make_log_entry(root)
    client = logged_in(root)

    changelist = client.get(reverse("admin:admin_logentry_changelist"))
    assert changelist.status_code == 200
    assert b"test yozuvi" in changelist.content
    assert b'value="delete_selected"' not in changelist.content

    # Add va delete umuman marshrutlanmaydi/ruxsat etilmaydi.
    assert client.get(reverse("admin:admin_logentry_add")).status_code == 403
    assert (
        client.get(reverse("admin:admin_logentry_delete", args=[entry.pk])).status_code
        == 403
    )

    # Detal sahifasi ochiladi, lekin saqlash tugmasi yo'q.
    detail = client.get(reverse("admin:admin_logentry_change", args=[entry.pk]))
    assert detail.status_code == 200
    assert b'name="_save"' not in detail.content


# ------------------------------- 3-band: audit modellari readonly / superuser


def test_task_activity_admin_is_readonly():
    model_admin = admin_for(TaskActivity)
    request = request_from(superuser())
    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False


def test_role_permission_admin_is_superuser_only():
    """docs/DESIGN_PERMISSIONS.md F-7 — matritsa admin orqali chetlab o'tilmaydi."""
    model_admin = admin_for(RolePermission)
    staff = request_from(staff_user())
    root = request_from(superuser())

    assert model_admin.has_add_permission(staff) is False
    assert model_admin.has_change_permission(staff) is False
    assert model_admin.has_delete_permission(staff) is False
    assert model_admin.has_add_permission(root) is True
    assert model_admin.has_change_permission(root) is True
    assert model_admin.has_delete_permission(root) is True


# ------------------------------------------------- 5-band: o'zbekcha brending


def test_admin_site_is_branded_in_uzbek():
    assert django_admin.site.site_header == "Clickish boshqaruvi"
    assert django_admin.site.site_title
    assert django_admin.site.index_title


# ---------------------------------------------- 4-band: auth hodisalari jurnali


def test_failed_login_is_logged(auth_log):
    make_user("target@test.dev", "Target")
    assert authenticate(email="target@test.dev", password="not-the-password") is None

    records = [r for r in auth_log.records if r.name == "apps.accounts.auth"]
    assert records, "muvaffaqiyatsiz kirish jurnalga yozilmadi"
    record = records[-1]
    assert record.levelno == logging.WARNING
    assert record.event == "auth.login_failed"
    assert record.email == "target@test.dev"
    assert "auth.login_failed" in record.getMessage()
    assert "not-the-password" not in record.getMessage()


def test_successful_admin_login_is_logged(auth_log):
    root = superuser()
    logged_in(root)

    records = [r for r in auth_log.records if getattr(r, "event", "") == "auth.login_succeeded"]
    assert records
    assert records[-1].email == root.email
    assert records[-1].levelno == logging.INFO


def test_logout_is_logged(auth_log):
    root = superuser()
    client = logged_in(root)
    client.post(reverse("admin:logout"))

    records = [r for r in auth_log.records if getattr(r, "event", "") == "auth.logout"]
    assert records
    assert records[-1].email == root.email


def test_forwarded_ip_is_ignored_without_a_trusted_proxy(auth_log, settings):
    """`X-Forwarded-For` soxtalashtiriladi — proxy yo'q bo'lsa unga ishonmaymiz.

    Qaror `NUM_PROXIES` ga bog'langan (ilgari `SECURE_PROXY_SSL_HEADER` ga
    edi — u TLS haqidagi sozlama va "necha hop ishonchli" degan savolga javob
    bermaydi). Indeksatsiya qoidalarining to'liq matritsasi
    `apps/accounts/test_auth_audit.py` da.
    """
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 0}
    Client().post(
        reverse("admin:login"),
        {"username": "ghost@test.dev", "password": "x"},
        HTTP_X_FORWARDED_FOR="1.2.3.4",
        REMOTE_ADDR="10.1.2.3",
    )

    records = [r for r in auth_log.records if getattr(r, "event", "") == "auth.login_failed"]
    assert records
    assert records[-1].ip == "10.1.2.3"


# ------------------------------------------- 6-band: `is_readonly` ko'rinadi


def test_is_readonly_is_visible_in_the_user_admin():
    """AppSec: ko'rinmaydigan nazorat — nazorat emas.

    `is_readonly` demo hisobning YAGONA qulfi (`has_perm` va
    `BlockReadonlyAccountWrites` shunga tayanadi), lekin u `fieldsets` da
    umuman yo'q edi: bayroqni faqat `seed_demo` yoki shell o'zgartirardi va
    admin sahifasida hech qanday izi ko'rinmasdi. Ya'ni yozish huquqi bor
    "demo" hisobni hech kim payqamasdi.
    """
    model_admin = admin_for(User)
    fields = {
        name
        for _title, options in model_admin.fieldsets
        for name in options["fields"]
    }
    assert "is_readonly" in fields
    assert "is_readonly" in model_admin.list_display
    assert "is_readonly" in model_admin.list_filter


def test_only_superuser_may_toggle_is_readonly():
    """Ko'rish hammaga, o'zgartirish faqat superuser'ga.

    `NoBulkDeleteMixin.has_delete_permission` bilan bir xil mantiq: `change_user`
    berilgan oddiy staff demo qulfini yechib, faqat o'qish uchun mo'ljallangan
    hisobni to'liq yozadigan hisobga aylantira olmasligi kerak.
    """
    model_admin = admin_for(User)
    victim = make_user("ro@test.dev", "Read Only")

    staff_readonly = model_admin.get_readonly_fields(request_from(staff_user()), victim)
    assert "is_readonly" in staff_readonly

    root_readonly = model_admin.get_readonly_fields(request_from(superuser()), victim)
    assert "is_readonly" not in root_readonly


def test_staff_cannot_clear_is_readonly_through_the_change_form():
    """Faqat atribut emas, HTTP yo'li ham yopiq bo'lsin."""
    victim = make_user("demo-lock@test.dev", "Demo Lock")
    victim.is_readonly = True
    victim.save(update_fields=["is_readonly"])

    staff = grant(staff_user(), User, "view_user", "change_user")
    client = logged_in(staff)
    url = reverse("admin:accounts_user_change", args=[victim.pk])

    page = client.get(url)
    assert page.status_code == 200
    # Readonly maydon input sifatida chizilmaydi, lekin qiymat ko'rinadi.
    assert b'name="is_readonly"' not in page.content

    client.post(
        url,
        {
            "email": victim.email,
            "full_name": victim.full_name,
            "profession": "",
            "avatar_color": victim.avatar_color,
            "timezone": victim.timezone,
            "is_active": "on",
        },
    )
    victim.refresh_from_db()
    assert victim.is_readonly is True
