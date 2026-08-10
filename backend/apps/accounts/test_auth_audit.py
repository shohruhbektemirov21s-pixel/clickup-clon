"""Autentifikatsiya auditi — `apps/accounts/signals.py` (AppSec B.2.4).

Ikki 2026-08 topilmasi shu yerda qulflanadi.

**1. API kirish yo'li auditdan tashqarida edi.** `LoginSerializer` foydalanuvchini
qo'lda topib `check_password()` chaqirardi, ya'ni `authenticate()` ham,
`login()` ham ishlamasdi va `user_login_failed` / `user_logged_in` signallari
HECH QACHON chiqmasdi. Jurnalda faqat `/admin/` formasi ko'rinardi — modul
yozilishining sababi bo'lgan per-IP brute-force alerti esa ilovaning asosiy
kirish nuqtasini umuman ko'rmasdi. Yon ta'sir: mavjud bo'lmagan email uchun
parol hash'i hisoblanmasdi, ya'ni javob vaqti "bu email bor/yo'q" degan
o'lchanadigan oracle berardi.

**2. Audit jurnalidagi IP buzg'unchi tanlagan qiymat edi.** `_client_ip`
`X-Forwarded-For` ning ENG CHAPDAGI elementini olardi. Zanjirni mijoz
boshlaydi, proxy esa o'zi ko'rgan manzilni OXIRIGA qo'shadi — demak chapdagi
element to'liq soxtalashtiriladi. Endi indeksatsiya DRF throttling'i bilan
bir xil: o'ngdan `NUM_PROXIES`-chi.
"""

import logging
from unittest import mock

import pytest
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.test import RequestFactory, override_settings
from rest_framework.throttling import BaseThrottle

from apps.accounts.models import User
from apps.accounts.signals import _client_ip
from conftest import PASSWORD, assert_error, make_user

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login/"
LOGOUT = "/api/v1/auth/logout/"
DEMO = "/api/v1/auth/demo/"
DEMO_EMAIL = "mehmon@clickish.dev"


@pytest.fixture
def auth_log(caplog):
    """`apps` logger'i `propagate=False` — caplog handler'ini qo'lda ulaymiz."""
    logger = logging.getLogger("apps.accounts.auth")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="apps.accounts.auth")
    yield caplog
    logger.removeHandler(caplog.handler)


def events(auth_log, name):
    return [r for r in auth_log.records if getattr(r, "event", "") == name]


# --------------------------------------------------- 1. API kirish yo'li auditda


def test_api_login_success_is_audited(api, auth_log):
    make_user("audit@test.dev")

    response = api.post(
        LOGIN,
        {"email": "audit@test.dev", "password": PASSWORD},
        format="json",
        HTTP_USER_AGENT="Mozilla/5.0 (audit)",
        REMOTE_ADDR="198.51.100.7",
    )
    assert response.status_code == 200, response.content

    records = events(auth_log, "auth.login_succeeded")
    assert records, "`POST auth/login/` auditga tushmadi"
    record = records[-1]
    assert record.email == "audit@test.dev"
    assert record.levelno == logging.INFO
    assert record.ip == "198.51.100.7"
    assert record.user_agent == "Mozilla/5.0 (audit)"


def test_api_login_failure_is_audited_as_a_warning(api, auth_log):
    make_user("audit@test.dev")

    bad = api.post(
        LOGIN, {"email": "audit@test.dev", "password": "not-the-password"}, format="json"
    )
    assert_error(bad, 401, "authentication_failed")

    records = events(auth_log, "auth.login_failed")
    assert records, "muvaffaqiyatsiz API kirishi auditga tushmadi"
    record = records[-1]
    assert record.levelno == logging.WARNING  # alert shu daraja bo'yicha qo'yiladi
    assert record.email == "audit@test.dev"
    # Parol jurnalda hech qachon ko'rinmaydi (`_clean_credentials` maskalaydi).
    assert "not-the-password" not in record.getMessage()


def test_unknown_email_is_audited_too(api, auth_log):
    """Mavjud bo'lmagan email — credential stuffing signalining o'zi."""
    response = api.post(
        LOGIN, {"email": "ghost@test.dev", "password": PASSWORD}, format="json"
    )
    assert_error(response, 401, "authentication_failed")

    records = events(auth_log, "auth.login_failed")
    assert records
    assert records[-1].email == "ghost@test.dev"


def test_inactive_account_login_is_audited_as_a_failure(api, auth_log):
    user = make_user("frozen@test.dev")
    user.is_active = False
    user.save(update_fields=["is_active"])

    assert_error(
        api.post(LOGIN, {"email": "frozen@test.dev", "password": PASSWORD}, format="json"),
        401,
        "authentication_failed",
    )
    assert events(auth_log, "auth.login_failed")
    assert not events(auth_log, "auth.login_succeeded")


def test_api_logout_is_audited(api, auth_log):
    make_user("bye@test.dev")
    tokens = api.post(
        LOGIN, {"email": "bye@test.dev", "password": PASSWORD}, format="json"
    ).json()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    assert api.post(LOGOUT, {"refresh": tokens["refresh"]}, format="json").status_code == 204

    records = events(auth_log, "auth.logout")
    assert records
    assert records[-1].email == "bye@test.dev"


@override_settings(DEMO_MODE=True, DEMO_USER_EMAIL=DEMO_EMAIL)
def test_demo_login_is_audited(api, auth_log):
    """Parolsiz kirish yo'li ham auditda — aks holda u ko'rinmas eshik bo'lardi."""
    user = make_user(DEMO_EMAIL)
    user.is_readonly = True
    user.save(update_fields=["is_readonly"])

    assert api.post(DEMO, {}, format="json").status_code == 200

    records = events(auth_log, "auth.login_succeeded")
    assert records
    assert records[-1].email == DEMO_EMAIL


def test_login_goes_through_the_django_auth_backend(api):
    """`authenticate()` chaqirilishi — audit qamrovining YAGONA kafolati.

    Signal receiver'lari o'chirilib qo'yilsa ham bu test kirish yo'li Django
    auth qatlamidan o'tishini isbotlaydi; kelajakdagi SSO backend'i ham shu
    tufayli avtomatik ishlaydi.
    """
    make_user("backend@test.dev")

    with mock.patch("apps.accounts.serializers.authenticate") as authenticate:
        authenticate.return_value = None
        response = api.post(
            LOGIN, {"email": "backend@test.dev", "password": PASSWORD}, format="json"
        )

    assert_error(response, 401, "authentication_failed")
    assert authenticate.call_count == 1
    assert authenticate.call_args.kwargs["email"] == "backend@test.dev"
    assert authenticate.call_args.kwargs["password"] == PASSWORD
    assert authenticate.call_args.kwargs["request"] is not None


def test_signals_carry_the_real_request(api, auth_log):
    """Signal `request=None` bilan yuborilsa IP/User-Agent jurnalda `-` bo'lardi."""
    make_user("req@test.dev")
    seen = {}

    def capture(sender, request=None, **kwargs):
        seen["request"] = request

    user_logged_in.connect(capture, dispatch_uid="test.capture.login")
    try:
        api.post(
            LOGIN,
            {"email": "req@test.dev", "password": PASSWORD},
            format="json",
            REMOTE_ADDR="203.0.113.55",
        )
    finally:
        user_logged_in.disconnect(dispatch_uid="test.capture.login")

    assert seen["request"] is not None
    assert seen["request"].META["REMOTE_ADDR"] == "203.0.113.55"


def test_failed_login_signal_never_carries_the_password(api):
    captured = {}

    def capture(sender, credentials=None, **kwargs):
        captured["credentials"] = credentials or {}

    user_login_failed.connect(capture, dispatch_uid="test.capture.failed")
    try:
        api.post(LOGIN, {"email": "x@test.dev", "password": "hunter2"}, format="json")
    finally:
        user_login_failed.disconnect(dispatch_uid="test.capture.failed")

    assert captured["credentials"].get("email") == "x@test.dev"
    assert "hunter2" not in str(captured["credentials"])


def test_user_agent_is_truncated_in_the_log(api, auth_log):
    """User-Agent mijoz boshqaradi — cheklanmasa log qatorini shishirish mumkin."""
    make_user("ua@test.dev")
    api.post(
        LOGIN,
        {"email": "ua@test.dev", "password": "wrong"},
        format="json",
        HTTP_USER_AGENT="A" * 5000,
    )

    record = events(auth_log, "auth.login_failed")[-1]
    assert len(record.user_agent) == 200


# ------------------------------------------- 1b. foydalanuvchi mavjudligi oracle


def test_unknown_email_still_runs_the_password_hasher(api, db):
    """Timing oracle: noma'lum email uchun ham hash hisoblanishi SHART.

    Vaqtni o'lchash test muhitida beqaror bo'lardi, shuning uchun sababni
    to'g'ridan-to'g'ri tekshiramiz: `ModelBackend` mavjud bo'lmagan
    foydalanuvchi uchun `UserModel().set_password(password)` chaqiradi
    (Django #20760). Bu chaqiruv yo'qolsa — noma'lum email javobi
    o'lchanadigan darajada tez qaytadi va ro'yxatni sanab chiqish mumkin
    bo'ladi.
    """
    before = User.objects.count()

    with mock.patch.object(User, "set_password", autospec=True) as hasher:
        response = api.post(
            LOGIN, {"email": "nobody@test.dev", "password": PASSWORD}, format="json"
        )

    assert_error(response, 401, "authentication_failed")
    assert hasher.call_count == 1, "noma'lum email uchun soxta hash hisoblanmadi"
    # Soxta hash yon ta'sir qoldirmaydi.
    assert User.objects.count() == before


def test_known_email_with_a_wrong_password_checks_the_hash(api, db):
    """Mavjud hisob yo'lida ham aynan bitta hash — ikkala yo'l simmetrik."""
    make_user("known@test.dev")

    with mock.patch.object(User, "check_password", autospec=True) as check:
        check.return_value = False
        response = api.post(
            LOGIN, {"email": "known@test.dev", "password": "guess"}, format="json"
        )

    assert_error(response, 401, "authentication_failed")
    assert check.call_count == 1


def test_login_is_case_insensitive_for_stored_mixed_case_emails(api, db):
    """`/admin/` formasi orqali yaratilgan hisob katta harfli emailga ega bo'lishi mumkin.

    `ModelBackend` ANIQ moslikni qidiradi, shuning uchun serializer saqlangan
    yozilishni oldindan topadi. Bu test o'sha ko'prikni qulflaydi.
    """
    user = make_user("mixed@test.dev")
    User.objects.filter(pk=user.pk).update(email="Mixed@Test.dev")

    for attempt in ("Mixed@Test.dev", "mixed@test.dev", "MIXED@TEST.DEV"):
        response = api.post(LOGIN, {"email": attempt, "password": PASSWORD}, format="json")
        assert response.status_code == 200, f"{attempt}: {response.content}"


# ------------------------------------- 2. audit IP'si — o'ngdan NUM_PROXIES-chi


def request_with(**meta):
    return RequestFactory().post("/api/v1/auth/login/", **meta)


@pytest.fixture
def num_proxies(settings):
    """DRF `api_settings` `setting_changed` signalida qayta yuklanadi."""

    def apply(value):
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": value}

    return apply


def test_forwarded_header_is_ignored_when_no_proxy_is_trusted(num_proxies):
    num_proxies(0)
    request = request_with(REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="8.8.8.8")
    assert _client_ip(request) == "10.0.0.9"


def test_the_spoofable_leftmost_hop_is_never_used(num_proxies):
    """Buzg'unchi zanjirni boshlaydi — chapdagi element to'liq uning nazoratida."""
    num_proxies(1)
    request = request_with(
        REMOTE_ADDR="10.0.0.9",
        HTTP_X_FORWARDED_FOR="8.8.8.8, 1.1.1.1, 203.0.113.9",
    )
    assert _client_ip(request) == "203.0.113.9"


def test_two_trusted_proxies_step_two_hops_from_the_right(num_proxies):
    num_proxies(2)
    request = request_with(
        REMOTE_ADDR="10.0.0.9",
        HTTP_X_FORWARDED_FOR="8.8.8.8, 1.1.1.1, 203.0.113.9",
    )
    assert _client_ip(request) == "1.1.1.1"


def test_a_short_chain_cannot_be_indexed_past_its_start(num_proxies):
    """Zanjir kutilganidan qisqa bo'lsa, eng chapdagi olinadi (DRF bilan bir xil)."""
    num_proxies(5)
    request = request_with(REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="1.1.1.1, 2.2.2.2")
    assert _client_ip(request) == "1.1.1.1"


def test_missing_forwarded_header_falls_back_to_remote_addr(num_proxies):
    num_proxies(3)
    assert _client_ip(request_with(REMOTE_ADDR="10.0.0.9")) == "10.0.0.9"


def test_unset_num_proxies_is_treated_as_zero(num_proxies):
    """DRF sukut qiymati `None` = "butun zanjirga ishon" — fail-closed qilamiz."""
    num_proxies(None)
    request = request_with(REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="8.8.8.8")
    assert _client_ip(request) == "10.0.0.9"


@pytest.mark.parametrize(
    "proxies,forwarded",
    [
        (0, None),
        (0, "8.8.8.8"),
        (1, "8.8.8.8"),
        (1, "8.8.8.8, 203.0.113.9"),
        (2, "8.8.8.8, 1.1.1.1, 203.0.113.9"),
        (4, "1.1.1.1, 2.2.2.2"),
    ],
)
def test_audit_ip_agrees_with_the_throttle_ident(num_proxies, proxies, forwarded):
    """Jurnal va rate-limit "mijoz kim" savoliga BIR XIL javob berishi shart.

    Ular ajralib qolsa, alert bir manzilni ko'rsatadi, blok esa boshqasiga
    tushadi — ya'ni per-IP javob chorasi ishlamaydi.
    """
    num_proxies(proxies)
    meta = {"REMOTE_ADDR": "10.0.0.9"}
    if forwarded is not None:
        meta["HTTP_X_FORWARDED_FOR"] = forwarded

    request = request_with(**meta)
    assert _client_ip(request) == BaseThrottle().get_ident(request)


def test_client_ip_bounds_the_value_it_logs(num_proxies):
    """Log injection/DoS: sarlavha uzunligi cheklanmasa qator shishib ketardi."""
    num_proxies(1)
    request = request_with(REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="9" * 500)
    assert len(_client_ip(request)) == 64


def test_client_ip_handles_a_missing_request():
    assert _client_ip(None) is None
