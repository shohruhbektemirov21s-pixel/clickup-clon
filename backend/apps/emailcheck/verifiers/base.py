"""Tekshiruv natijasining shakli va `Verifier` interfeysi.

Butun modul shu ikki narsaga tayanadi: `VerificationResult` — chiqish
formati, `Verifier` — uni ishlab chiqaradigan almashtiriladigan komponent.
SMTP amalga oshiruvi ham, tashqi API ham SHU interfeysni bajaradi, shuning
uchun runner, CSV yozuvchi va CLI ularning qaysi biri ishlayotganini
bilmaydi.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class EmailStatus(str, Enum):
    """Chiqishdagi yakuniy status.

    `str` dan meros olingan: CSV yozuvchi va JSON serializer qiymatni
    qo'shimcha konversiyasiz yoza oladi.
    """

    VALID = "valid"
    INVALID = "invalid"
    RISKY = "risky"
    UNKNOWN = "unknown"


#: Har bir status uchun o'zbekcha izoh — hisobot sarlavhalarida ishlatiladi.
STATUS_LABEL = {
    EmailStatus.VALID: "mavjud",
    EmailStatus.INVALID: "mavjud emas",
    EmailStatus.RISKY: "shubhali",
    EmailStatus.UNKNOWN: "noaniq",
}


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Bitta manzilning yakuniy natijasi.

    `frozen` — natija bir marta yoziladi va o'zgarmaydi; runner uni oqimga
    uzatadi, hech kim yo'lda tahrirlamaydi.
    """

    email: str
    status: EmailStatus
    #: Nega shu status berilgani — o'zbekcha, bitta qator.
    reason: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    #: Qaysi MX serverdan so'ralgani (SMTP yo'lida).
    mx_host: str | None = None
    #: SMTP javob kodi (250 / 550 / 4xx). API yo'lida `None`.
    smtp_code: int | None = None
    #: Qaysi verifier chiqargani — `smtp`, `zerobounce`, `hunter`…
    provider: str = ""

    def as_row(self) -> dict[str, str]:
        """CSV qatoriga aylantiradi. Ustun nomlari o'zbekcha — chiqish odam
        o'qishi uchun."""
        return {
            "email": self.email,
            "status": self.status.value,
            "sabab": self.reason,
            "tekshirilgan_vaqt": self.checked_at.isoformat().replace("+00:00", "Z"),
            "mx": self.mx_host or "",
            "smtp_kod": "" if self.smtp_code is None else str(self.smtp_code),
            "manba": self.provider,
        }


#: CSV ustunlari — `as_row()` kalitlari bilan bir xil tartibda.
CSV_COLUMNS = ("email", "status", "sabab", "tekshirilgan_vaqt", "mx", "smtp_kod", "manba")


# ---------------------------------------------------------------- sintaksis

#: RFC 5322 ning soddalashtirilgan shakli.
#:
#: To'liq grammatikani regex bilan yozish mumkin, lekin natija o'qib
#: bo'lmaydigan va amalda foyda bermaydigan bo'lardi: izohlar `(...)`,
#: qo'shtirnoqli local qism va IP-literal domenlar real ro'yxatlarda
#: uchramaydi. Bu yerda ataylab **konservativ** qoida: haqiqiy manzilni rad
#: etmaslik muhimroq, chunki keyingi bosqichlar (MX, SMTP) baribir
#: tekshiradi.
_LOCAL = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_DOMAIN = rf"{_LABEL}(?:\.{_LABEL})+"
EMAIL_RE = re.compile(rf"^{_LOCAL}@{_DOMAIN}$", re.ASCII)

#: RFC 5321 §4.5.3.1 chegaralari.
MAX_EMAIL_LENGTH = 254
MAX_LOCAL_LENGTH = 64
MAX_DOMAIN_LENGTH = 255


def check_syntax(email: str) -> str | None:
    """Format xato bo'lsa o'zbekcha sabab, to'g'ri bo'lsa `None` qaytaradi."""
    if not email:
        return "bo'sh qator"
    if len(email) > MAX_EMAIL_LENGTH:
        return f"juda uzun ({len(email)} > {MAX_EMAIL_LENGTH} belgi)"
    if email.count("@") != 1:
        return "@ belgisi bitta bo'lishi kerak"
    local, _, domain = email.partition("@")
    if len(local) > MAX_LOCAL_LENGTH:
        return f"@ dan oldingi qism juda uzun ({len(local)} > {MAX_LOCAL_LENGTH})"
    if len(domain) > MAX_DOMAIN_LENGTH:
        return f"domen juda uzun ({len(domain)} > {MAX_DOMAIN_LENGTH})"
    if ".." in email:
        return "ketma-ket ikkita nuqta"
    if not EMAIL_RE.match(email):
        return "format RFC 5322 ga mos emas"
    return None


def normalise(raw: str) -> str:
    """Kirishdagi qatorni tozalaydi.

    Domen registrga sezgir EMAS, local qism esa RFC bo'yicha sezgir — shuning
    uchun faqat domen kichik harfga o'tkaziladi. Amalda deyarli hech bir
    server local qismni farqlamaydi, lekin kirishdagi ma'lumotni jimgina
    o'zgartirib yuborish chiqishni asl ro'yxat bilan solishtirishni buzadi.
    """
    email = raw.strip().strip("<>").strip()
    if email.count("@") == 1:
        local, _, domain = email.partition("@")
        return f"{local}@{domain.lower()}"
    return email


def domain_of(email: str) -> str:
    return email.rpartition("@")[2].lower()


# ------------------------------------------------------------------ verifier


class Verifier(ABC):
    """Bitta manzilni tekshiradigan almashtiriladigan komponent.

    Shartnoma:

    * `verify()` HECH QACHON istisno ko'tarmaydi. Har qanday kutilmagan xato
      `UNKNOWN` natijaga aylanadi — 10 000 manzillik yurish bitta tarmoq
      uzilishidan to'xtamasligi kerak.
    * `verify()` o'z ichida rate limiting QILMAYDI. Domen bo'yicha
      cheklovni `throttle.DomainThrottle` boshqaradi, chunki u butun
      yurish bo'yicha global bo'lishi kerak.
    * `aclose()` idempotent.
    """

    #: `provider` maydoniga tushadigan nom.
    name: str = "base"

    @abstractmethod
    async def verify(self, email: str) -> VerificationResult:
        raise NotImplementedError

    async def aclose(self) -> None:
        """Ochiq resurslarni yopadi. Standart holatda qiladigan ishi yo'q."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        await self.aclose()

    # Amalga oshiruvchilar uchun qulaylik.
    def _result(self, email: str, status: EmailStatus, reason: str, **extra) -> VerificationResult:
        return VerificationResult(
            email=email, status=status, reason=reason, provider=self.name, **extra
        )
