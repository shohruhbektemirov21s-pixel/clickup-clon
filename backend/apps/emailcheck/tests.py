"""`apps.emailcheck` testlari.

Hech bir test TARMOQQA CHIQMAYDI: DNS va SMTP qatlamlari qo'lda yozilgan
soxta obyektlar bilan almashtiriladi. Sabab ikkita — CI'da tarmoq bo'lmasligi
mumkin, va haqiqiy MX serverga test paytida so'rov yuborish o'sha serverning
resursini bekorga sarflaydi.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from apps.emailcheck import io as check_io
from apps.emailcheck.resolver import MxLookup
from apps.emailcheck.runner import verify_all, verify_stream
from apps.emailcheck.throttle import DomainThrottle
from apps.emailcheck.verifiers import build_verifier
from apps.emailcheck.verifiers.base import (
    EmailStatus,
    VerificationResult,
    Verifier,
    check_syntax,
    domain_of,
    normalise,
)
from apps.emailcheck.verifiers.external import _abstract_parse, _hunter_parse, _zerobounce_parse
from apps.emailcheck.verifiers.smtp import SmtpVerifier

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ------------------------------------------------------------------ sintaksis


@pytest.mark.parametrize(
    "email",
    [
        "a@b.uz",
        "ism.familiya@example.com",
        "user+tag@sub.domain.co.uk",
        "u_s-e'r@example.museum".replace("'", ""),
        "x" * 64 + "@example.com",
    ],
)
def test_valid_syntax_is_accepted(email):
    assert check_syntax(email) is None, email


@pytest.mark.parametrize(
    ("email", "fragment"),
    [
        ("", "bo'sh"),
        ("yoq-at-belgisi", "@ belgisi"),
        ("ikki@@example.com", "@ belgisi"),
        ("a@b", "RFC 5322"),
        ("a..b@example.com", "ikkita nuqta"),
        ("@example.com", "RFC 5322"),
        ("a@.com", "RFC 5322"),
        ("a@example.", "RFC 5322"),
        ("x" * 65 + "@example.com", "juda uzun"),
        ("a" * 250 + "@example.com", "juda uzun"),
    ],
)
def test_invalid_syntax_is_rejected(email, fragment):
    reason = check_syntax(email)
    assert reason is not None, email
    assert fragment in reason


def test_normalise_lowercases_only_the_domain():
    # Local qism RFC bo'yicha registrga sezgir — uni o'zgartirish kirishdagi
    # ma'lumotni jimgina buzish bo'lardi.
    assert normalise("  <Ali.Valiev@EXAMPLE.COM>  ") == "Ali.Valiev@example.com"


def test_normalise_leaves_broken_input_alone():
    assert normalise("  buzuq  ") == "buzuq"


def test_domain_of_takes_the_last_at():
    assert domain_of("a@b@example.com") == "example.com"


# -------------------------------------------------------------------- kirish


def test_csv_email_column_is_found_by_name(tmp_path):
    path = tmp_path / "r.csv"
    path.write_text("ism,email,izoh\nAli,a@example.com,x\nVali,b@example.com,y\n", encoding="utf-8")
    assert list(check_io.read_emails(path)) == ["a@example.com", "b@example.com"]


def test_csv_uzbek_header_is_found(tmp_path):
    path = tmp_path / "r.csv"
    path.write_text("ism;pochta\nAli;a@example.com\n", encoding="utf-8")
    assert list(check_io.read_emails(path)) == ["a@example.com"]


def test_csv_without_header_uses_the_first_column(tmp_path):
    path = tmp_path / "r.csv"
    path.write_text("a@example.com\nb@example.com\n", encoding="utf-8")
    assert list(check_io.read_emails(path)) == ["a@example.com", "b@example.com"]


def test_txt_one_per_line_skips_comments_and_blanks(tmp_path):
    path = tmp_path / "r.txt"
    path.write_text("# izoh\na@example.com\n\n  b@example.com  \n", encoding="utf-8")
    assert list(check_io.read_emails(path)) == ["a@example.com", "b@example.com"]


def test_duplicates_are_collapsed_case_insensitively_on_the_domain(tmp_path):
    path = tmp_path / "r.txt"
    path.write_text("a@Example.com\na@example.com\nb@example.com\n", encoding="utf-8")
    assert list(check_io.read_emails(path)) == ["a@example.com", "b@example.com"]


def test_dedupe_can_be_switched_off(tmp_path):
    path = tmp_path / "r.txt"
    path.write_text("a@example.com\na@example.com\n", encoding="utf-8")
    assert list(check_io.read_emails(path, dedupe=False)) == ["a@example.com"] * 2


def test_bom_prefixed_csv_is_read(tmp_path):
    # Excel'dan eksport qilingan fayl deyarli har doim BOM bilan keladi.
    path = tmp_path / "r.csv"
    path.write_bytes("﻿email\na@example.com\n".encode("utf-8"))
    assert list(check_io.read_emails(path)) == ["a@example.com"]


# -------------------------------------------------------------------- chiqish


def test_writer_emits_header_and_rows(tmp_path):
    path = tmp_path / "out.csv"
    with check_io.ResultWriter(path) as writer:
        writer.write(
            VerificationResult(
                email="a@example.com",
                status=EmailStatus.VALID,
                reason="server qabul qildi (250)",
                smtp_code=250,
                provider="smtp",
            )
        )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "email,status,sabab,tekshirilgan_vaqt,mx,smtp_kod,manba"
    assert lines[1].startswith("a@example.com,valid,server qabul qildi (250),")
    assert lines[1].endswith(",250,smtp")


def test_writer_flushes_each_row(tmp_path):
    """Yurish o'rtasida uzilsa ham yozilganlari faylda qolishi kerak."""
    path = tmp_path / "out.csv"
    writer = check_io.ResultWriter(path)
    writer.write(VerificationResult(email="a@example.com", status=EmailStatus.VALID, reason="ok"))
    # `close()` chaqirilmasdan o'qiymiz — flush ishlagan bo'lsa qator ko'rinadi.
    assert "a@example.com" in path.read_text(encoding="utf-8")
    writer.close()


def test_summary_counts_every_status():
    text = check_io.render_summary(
        {"valid": 3, "invalid": 1, "risky": 0, "unknown": 2}, total=6, elapsed=1.0
    )
    assert "Jami tekshirildi: 6 ta" in text
    for status in ("valid", "invalid", "risky", "unknown"):
        assert status in text


# ------------------------------------------------------------------ throttle


async def test_domain_throttle_spaces_out_the_same_domain():
    throttle = DomainThrottle(interval=0.15, concurrency=1)
    started = time.monotonic()

    async def hit():
        async with throttle.acquire("example.com"):
            pass

    await asyncio.gather(*(hit() for _ in range(3)))
    # Uchta so'rov: 0.0, 0.15, 0.30 → kamida 0.30 s.
    assert time.monotonic() - started >= 0.29


async def test_domain_throttle_does_not_block_other_domains():
    throttle = DomainThrottle(interval=0.4, concurrency=1)
    started = time.monotonic()

    async def hit(domain):
        async with throttle.acquire(domain):
            pass

    await asyncio.gather(hit("a.uz"), hit("b.uz"), hit("c.uz"))
    # Har xil domen — birinchi navbat hech kimni kutmaydi.
    assert time.monotonic() - started < 0.3


async def test_domain_throttle_limits_concurrency_per_domain():
    throttle = DomainThrottle(interval=0.0, concurrency=2)
    live = 0
    peak = 0

    async def hit():
        nonlocal live, peak
        async with throttle.acquire("example.com"):
            live += 1
            peak = max(peak, live)
            await asyncio.sleep(0.05)
            live -= 1

    await asyncio.gather(*(hit() for _ in range(6)))
    assert peak == 2


def test_domain_throttle_rejects_bad_arguments():
    with pytest.raises(ValueError):
        DomainThrottle(interval=-1)
    with pytest.raises(ValueError):
        DomainThrottle(concurrency=0)


# -------------------------------------------------------------------- runner


class FakeVerifier(Verifier):
    """Oldindan belgilangan javob beradigan verifier."""

    name = "fake"

    def __init__(self, mapping=None, *, delay: float = 0.0):
        self.mapping = mapping or {}
        self.delay = delay
        self.seen: list[str] = []

    async def verify(self, email):
        if self.delay:
            await asyncio.sleep(self.delay)
        self.seen.append(email)
        status = self.mapping.get(email, EmailStatus.VALID)
        return self._result(email, status, "test")


async def test_runner_returns_one_result_per_email():
    verifier = FakeVerifier()
    emails = [f"u{i}@example.com" for i in range(25)]
    got = [r.email async for r in verify_stream(emails, verifier, concurrency=5)]
    assert sorted(got) == sorted(emails)


async def test_runner_counts_by_status():
    verifier = FakeVerifier(
        {
            "a@example.com": EmailStatus.VALID,
            "b@example.com": EmailStatus.INVALID,
            "c@example.com": EmailStatus.RISKY,
            "d@example.com": EmailStatus.UNKNOWN,
        }
    )
    stats = await verify_all(list(verifier.mapping), verifier, concurrency=2)
    assert stats.total == 4
    assert stats.as_dict() == {"valid": 1, "invalid": 1, "risky": 1, "unknown": 1}


async def test_runner_reports_progress_monotonically():
    seen: list[int] = []
    verifier = FakeVerifier()
    await verify_all(
        [f"u{i}@example.com" for i in range(10)],
        verifier,
        concurrency=3,
        on_progress=lambda done, total: seen.append(done),
    )
    assert seen == list(range(1, 11))


async def test_runner_streams_into_a_sink_without_collecting():
    written: list[str] = []
    verifier = FakeVerifier()
    await verify_all(
        [f"u{i}@example.com" for i in range(8)],
        verifier,
        concurrency=4,
        sink=lambda r: written.append(r.email),
    )
    assert len(written) == 8


async def test_runner_survives_a_verifier_that_raises():
    class Broken(Verifier):
        name = "broken"

        async def verify(self, email):
            raise RuntimeError("bo'ldi")

    stats = await verify_all(["a@example.com", "b@example.com"], Broken(), concurrency=2)
    assert stats.as_dict()["unknown"] == 2


async def test_runner_respects_concurrency_limit():
    live = 0
    peak = 0

    class Counting(Verifier):
        name = "counting"

        async def verify(self, email):
            nonlocal live, peak
            live += 1
            peak = max(peak, live)
            await asyncio.sleep(0.02)
            live -= 1
            return self._result(email, EmailStatus.VALID, "ok")

    await verify_all([f"u{i}@example.com" for i in range(20)], Counting(), concurrency=4)
    assert peak <= 4


def test_runner_rejects_zero_concurrency():
    async def run():
        async for _ in verify_stream(["a@example.com"], FakeVerifier(), concurrency=0):
            pass

    with pytest.raises(ValueError):
        asyncio.run(run())


# ---------------------------------------------------------------------- SMTP


class StubResolver:
    def __init__(self, lookup: MxLookup):
        self.lookup = lookup

    async def resolve(self, domain):
        return self.lookup


def smtp_verifier(monkeypatch, *, code, message="", lookup=None, catch_all_code=None):
    """`_probe_once` ni almashtirgan `SmtpVerifier` yasaydi."""
    verifier = SmtpVerifier(
        helo_hostname="test.local",
        mail_from="probe@test.local",
        resolver=StubResolver(lookup or MxLookup(hosts=("mx.example.com",))),
        throttle=DomainThrottle(interval=0.0),
        retries=0,
        detect_catch_all=catch_all_code is not None,
    )

    async def fake_probe(host, email, *, use_tls=True):
        # Catch-all probe tasodifiy local qism bilan keladi.
        if catch_all_code is not None and not email.startswith("user@"):
            return SmtpVerifier._Probe(catch_all_code, "catch-all probe")
        return SmtpVerifier._Probe(code, message)

    monkeypatch.setattr(verifier, "_probe_once", fake_probe)
    return verifier


async def test_smtp_250_is_valid(monkeypatch):
    verifier = smtp_verifier(monkeypatch, code=250, message="OK")
    result = await verifier.verify("user@example.com")
    assert result.status is EmailStatus.VALID
    assert result.smtp_code == 250
    assert result.mx_host == "mx.example.com"


async def test_smtp_550_is_invalid(monkeypatch):
    verifier = smtp_verifier(monkeypatch, code=550, message="No such user")
    result = await verifier.verify("user@example.com")
    assert result.status is EmailStatus.INVALID
    assert "550" in result.reason


async def test_smtp_4xx_is_unknown(monkeypatch):
    verifier = smtp_verifier(monkeypatch, code=451, message="Try later")
    result = await verifier.verify("user@example.com")
    assert result.status is EmailStatus.UNKNOWN


async def test_smtp_timeout_is_unknown(monkeypatch):
    verifier = smtp_verifier(monkeypatch, code=None, message="vaqt tugadi")
    result = await verifier.verify("user@example.com")
    assert result.status is EmailStatus.UNKNOWN
    assert result.smtp_code is None


async def test_catch_all_domain_downgrades_250_to_risky(monkeypatch):
    verifier = smtp_verifier(monkeypatch, code=250, catch_all_code=250)
    result = await verifier.verify("user@example.com")
    assert result.status is EmailStatus.RISKY
    assert "catch-all" in result.reason


async def test_non_catch_all_domain_keeps_250_valid(monkeypatch):
    verifier = smtp_verifier(monkeypatch, code=250, catch_all_code=550)
    result = await verifier.verify("user@example.com")
    assert result.status is EmailStatus.VALID


async def test_catch_all_timeout_does_not_mark_the_domain_risky(monkeypatch):
    """Tarmoq uzilishi butun domenni `risky` qilib qo'ymasligi kerak."""
    verifier = smtp_verifier(monkeypatch, code=250, catch_all_code=None)
    verifier.detect_catch_all = True

    async def fake_probe(host, email, *, use_tls=True):
        if not email.startswith("user@"):
            return SmtpVerifier._Probe(None, "vaqt tugadi")
        return SmtpVerifier._Probe(250, "OK")

    monkeypatch.setattr(verifier, "_probe_once", fake_probe)
    result = await verifier.verify("user@example.com")
    assert result.status is EmailStatus.VALID


async def test_missing_mx_is_invalid_without_touching_smtp(monkeypatch):
    verifier = smtp_verifier(
        monkeypatch, code=250, lookup=MxLookup(hosts=(), error="MX yozuvi yo'q")
    )
    result = await verifier.verify("user@example.com")
    assert result.status is EmailStatus.INVALID
    assert "MX" in result.reason


async def test_bad_syntax_never_reaches_dns(monkeypatch):
    class Exploding:
        async def resolve(self, domain):
            raise AssertionError("DNS chaqirilmasligi kerak edi")

    verifier = SmtpVerifier(
        helo_hostname="t", mail_from="p@t", resolver=Exploding(), retries=0
    )
    result = await verifier.verify("buzuq")
    assert result.status is EmailStatus.INVALID
    assert "sintaksis" in result.reason


async def test_transient_response_is_retried(monkeypatch):
    verifier = SmtpVerifier(
        helo_hostname="t",
        mail_from="p@t",
        resolver=StubResolver(MxLookup(hosts=("mx.example.com",))),
        throttle=DomainThrottle(interval=0.0),
        retries=2,
        detect_catch_all=False,
    )
    calls = {"n": 0}

    async def fake_probe(host, email, *, use_tls=True):
        calls["n"] += 1
        # Ikki marta 4xx, uchinchisida 250.
        if calls["n"] < 3:
            return SmtpVerifier._Probe(451, "band")
        return SmtpVerifier._Probe(250, "OK")

    monkeypatch.setattr(verifier, "_probe_once", fake_probe)
    # Backoff kutishini nolga tushiramiz. Asl `sleep` OLDIN olinadi, aks holda
    # almashtirilgan funksiya o'zini chaqirib rekursiyaga tushadi.
    real_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda *_args, **_kw: real_sleep(0))
    result = await verifier.verify("user@example.com")
    assert calls["n"] == 3
    assert result.status is EmailStatus.VALID


async def test_permanent_response_is_not_retried(monkeypatch):
    verifier = SmtpVerifier(
        helo_hostname="t",
        mail_from="p@t",
        resolver=StubResolver(MxLookup(hosts=("mx.example.com",))),
        throttle=DomainThrottle(interval=0.0),
        retries=2,
        detect_catch_all=False,
    )
    calls = {"n": 0}

    async def fake_probe(host, email, *, use_tls=True):
        calls["n"] += 1
        return SmtpVerifier._Probe(550, "yo'q")

    monkeypatch.setattr(verifier, "_probe_once", fake_probe)
    result = await verifier.verify("user@example.com")
    assert calls["n"] == 1, "550 yakuniy javob — takrorlanmasligi kerak"
    assert result.status is EmailStatus.INVALID


# ------------------------------------------------------------- tashqi API


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"status": "valid"}, EmailStatus.VALID),
        ({"status": "invalid", "sub_status": "mailbox_not_found"}, EmailStatus.INVALID),
        ({"status": "catch-all"}, EmailStatus.RISKY),
        ({"status": "spamtrap"}, EmailStatus.RISKY),
        ({"status": "unknown"}, EmailStatus.UNKNOWN),
        ({}, EmailStatus.UNKNOWN),
    ],
)
def test_zerobounce_status_mapping(payload, expected):
    assert _zerobounce_parse(payload)[0] is expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"deliverability": "DELIVERABLE"}, EmailStatus.VALID),
        ({"deliverability": "UNDELIVERABLE"}, EmailStatus.INVALID),
        ({"deliverability": "DELIVERABLE", "is_catchall_email": {"value": True}}, EmailStatus.RISKY),
        ({"deliverability": "DELIVERABLE", "is_disposable_email": True}, EmailStatus.RISKY),
        ({}, EmailStatus.UNKNOWN),
    ],
)
def test_abstractapi_status_mapping(payload, expected):
    assert _abstract_parse(payload)[0] is expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"data": {"result": "deliverable"}}, EmailStatus.VALID),
        ({"data": {"result": "undeliverable"}}, EmailStatus.INVALID),
        ({"data": {"result": "deliverable", "accept_all": True}}, EmailStatus.RISKY),
        ({"data": {"result": "unknown"}}, EmailStatus.UNKNOWN),
        ({}, EmailStatus.UNKNOWN),
    ],
)
def test_hunter_status_mapping(payload, expected):
    assert _hunter_parse(payload)[0] is expected


# ------------------------------------------------------------------ fabrika


def test_build_verifier_makes_smtp():
    verifier = build_verifier("smtp", helo_hostname="t", mail_from="p@t")
    assert isinstance(verifier, SmtpVerifier)
    assert verifier.name == "smtp"


def test_build_verifier_makes_every_external_provider():
    for provider in ("zerobounce", "abstractapi", "hunter"):
        verifier = build_verifier(provider, api_key="k")
        assert verifier.name == provider


def test_build_verifier_rejects_unknown_kind():
    with pytest.raises(ValueError, match="noma'lum verifier"):
        build_verifier("yoq", api_key="k")


def test_external_verifier_requires_a_key():
    with pytest.raises(ValueError, match="API kalit"):
        build_verifier("hunter", api_key="")
