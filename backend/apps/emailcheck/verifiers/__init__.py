"""Verifier amalga oshiruvlari va ularni nomdan yasovchi fabrika."""

from apps.emailcheck.verifiers.base import (
    CSV_COLUMNS,
    STATUS_LABEL,
    EmailStatus,
    VerificationResult,
    Verifier,
    check_syntax,
    domain_of,
    normalise,
)
from apps.emailcheck.verifiers.external import PROVIDERS, ExternalApiVerifier
from apps.emailcheck.verifiers.smtp import SmtpVerifier

__all__ = [
    "CSV_COLUMNS",
    "PROVIDERS",
    "STATUS_LABEL",
    "EmailStatus",
    "ExternalApiVerifier",
    "SmtpVerifier",
    "VerificationResult",
    "Verifier",
    "build_verifier",
    "check_syntax",
    "domain_of",
    "normalise",
]


def build_verifier(kind: str, **options) -> Verifier:
    """`kind` nomidan verifier yasaydi.

    `kind` — `smtp` yoki `PROVIDERS` dagi kalit (`zerobounce`, `abstractapi`,
    `hunter`). CLI ham, API ham SHU funksiyadan foydalanadi, shuning uchun
    yangi provayder ikkala joyda birdaniga paydo bo'ladi.
    """
    kind = kind.lower()
    if kind == "smtp":
        return SmtpVerifier(**options)
    if kind in PROVIDERS:
        return ExternalApiVerifier(provider=kind, **options)
    known = ", ".join(["smtp", *sorted(PROVIDERS)])
    raise ValueError(f"noma'lum verifier {kind!r}; mavjudlari: {known}")
