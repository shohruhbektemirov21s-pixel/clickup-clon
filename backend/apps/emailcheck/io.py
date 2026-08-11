"""Kirish faylini o'qish va natijani oqim bilan yozish.

Ikkalasi ham **oqimli**: kirish generator bilan qatorma-qator o'qiladi,
chiqish esa natija kelishi bilan darhol yoziladi va flush qilinadi. Shuning
uchun 500 000 qatorli ro'yxat ham xotirani to'ldirmaydi, va yurish o'rtasida
uzilib qolsa fayl allaqachon tekshirilganlarni saqlab qoladi.

`pandas` ataylab ISHLATILMAYDI: u butun jadvalni xotiraga yuklaydi, bu esa
shu moduldagi asosiy talabga to'g'ridan-to'g'ri zid.
"""

from __future__ import annotations

import csv
import io as _io
import sys
from pathlib import Path
from typing import IO, Iterable, Iterator

from apps.emailcheck.verifiers.base import CSV_COLUMNS, VerificationResult, normalise

#: "email" ustunini topish uchun nomlar — kichik harfda solishtiriladi.
EMAIL_HEADERS = (
    "email",
    "e-mail",
    "email_address",
    "emailaddress",
    "mail",
    "manzil",
    "pochta",
    "elektron_pochta",
)

#: `csv.Sniffer` ga beriladigan namuna hajmi.
_SNIFF_BYTES = 8192


def read_emails(path: str | Path, *, dedupe: bool = True) -> Iterator[str]:
    """Fayldan manzillarni birma-bir qaytaradi.

    `.csv` — sarlavha bo'lsa "email" ustuni avtomatik topiladi; topilmasa
    birinchi ustun olinadi. Boshqa kengaytma (`.txt` va h.k.) — har qator
    bitta manzil.

    `dedupe` — takrorlangan manzil bir marta tekshiriladi. Ko'rilganlar
    to'plami xotirada qoladi (1 mln manzil ≈ 100 MB); juda katta ro'yxatda
    `dedupe=False` qo'ying va oldindan `sort -u` qiling.
    """
    path = Path(path)
    seen: set[str] | None = set() if dedupe else None

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = _csv_rows(handle) if path.suffix.lower() == ".csv" else _plain_rows(handle)
        for raw in rows:
            email = normalise(raw)
            if not email:
                continue
            if seen is not None:
                if email in seen:
                    continue
                seen.add(email)
            yield email


def _plain_rows(handle: IO[str]) -> Iterator[str]:
    for line in handle:
        stripped = line.strip()
        # Izoh qatorlari qo'lda tuzilgan ro'yxatlarda uchraydi.
        if stripped and not stripped.startswith("#"):
            yield stripped


def _csv_rows(handle: IO[str]) -> Iterator[str]:
    sample = handle.read(_SNIFF_BYTES)
    handle.seek(0)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        # Bitta ustunli fayl — Sniffer ajratuvchini topa olmaydi.
        dialect = csv.excel

    reader = csv.reader(handle, dialect)
    try:
        header = next(reader)
    except StopIteration:
        return

    index = _email_column(header)
    if index is None:
        # Sarlavha yo'q ekan — birinchi qator ham ma'lumot.
        index = 0
        if header and header[0].strip():
            yield header[0]

    for row in reader:
        if len(row) > index:
            value = row[index].strip()
            if value:
                yield value


def _email_column(header: list[str]) -> int | None:
    """Sarlavhadan email ustunini topadi; sarlavha bo'lmasa `None`."""
    normalised = [cell.strip().lower().replace(" ", "_") for cell in header]
    for candidate in EMAIL_HEADERS:
        if candidate in normalised:
            return normalised.index(candidate)
    # Nomi mos kelmasa ham, `@` bo'lgan ustunni sarlavha deb hisoblamaymiz.
    for index, cell in enumerate(normalised):
        if "email" in cell or "mail" in cell:
            return index
    return None


class ResultWriter:
    """Natijalarni CSV'ga oqim bilan yozadi.

    Har qatordan keyin `flush()` — jarayon to'xtab qolsa ham fayl to'liq
    qoladi. Bu tezlikka arzimas ta'sir qiladi (OS buferi baribir ishlaydi),
    lekin uzoq yurishda ma'lumot yo'qotmaslikni kafolatlaydi.
    """

    def __init__(self, target: str | Path | IO[str]) -> None:
        self._own_handle = not hasattr(target, "write")
        if self._own_handle:
            self._handle: IO[str] = Path(target).open("w", encoding="utf-8", newline="")
        else:
            self._handle = target  # type: ignore[assignment]
        self._writer = csv.DictWriter(self._handle, fieldnames=list(CSV_COLUMNS))
        self._writer.writeheader()
        self._handle.flush()

    def write(self, result: VerificationResult) -> None:
        self._writer.writerow(result.as_row())
        self._handle.flush()

    def close(self) -> None:
        if self._own_handle:
            self._handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


def render_summary(counts: dict[str, int], *, total: int, elapsed: float) -> str:
    """Qisqa hisobot matni — CLI oxirida va API javobida ishlatiladi."""
    from apps.emailcheck.verifiers.base import STATUS_LABEL, EmailStatus

    lines = [f"Jami tekshirildi: {total} ta ({elapsed:.1f} s)"]
    for status in EmailStatus:
        count = counts.get(status.value, 0)
        share = (count / total * 100) if total else 0.0
        lines.append(
            f"  {status.value:<8} {STATUS_LABEL[status]:<12} {count:>7}  ({share:5.1f}%)"
        )
    return "\n".join(lines)


def write_summary(counts: dict[str, int], *, total: int, elapsed: float, stream=None) -> None:
    print(render_summary(counts, total=total, elapsed=elapsed), file=stream or sys.stderr)


def csv_string(results: Iterable[VerificationResult]) -> str:
    """Kichik ro'yxatni satrga yozadi — API javobi uchun."""
    buffer = _io.StringIO()
    with ResultWriter(buffer) as writer:
        for result in results:
            writer.write(result)
    return buffer.getvalue()
