# 2 — Timezone

Holat: Qabul qilindi | Sana: 2026-08-11

## Kontekst

Loyiha faqat O'zbekiston foydalanuvchilari uchun mo'ljallangan, lekin Django
loyihasi standart `TIME_ZONE = "UTC"` bilan boshlangan edi
(`backend/config/settings.py:498`). `USE_TZ = True` (`settings.py:500`) —
ma'lumotlar bazasida barcha vaqt qiymatlari har doim UTC-aware saqlanadi;
`TIME_ZONE` faqat naive vaqtlarni talqin qilish va standart ko'rsatish uchun
ishlatiladi (masalan, admin panel, `auto_now_add`/`auto_now` maydonlarining
lokal ko'rinishi).

**Diqqat:** bu ADR yozilayotgan payida backend agenti xuddi shu sozlamani
`Asia/Tashkent`ga o'zgartirish ustida ishlamoqda (`fix/list-view-readonly-affordances`
branch'idagi ochiq ish). Ushbu ADR shu maqsadli holatni qayd etadi — commit
qilingan `settings.py:498` hali `"UTC"` bo'lishi mumkin, lekin qaror allaqachon
qabul qilingan.

## Qaror

`TIME_ZONE = "Asia/Tashkent"`, `USE_TZ = True` saqlanadi. Ma'lumotlar bazasi
UTC-aware qiymatlarni saqlashda davom etadi (`USE_TZ`ni o'chirish yo'q) —
o'zgaradigan narsa faqat Django'ning standart lokal-vaqt talqini
(masalan, `timezone.localtime()`, admin ko'rinishi).

## Sabab

Mahsulot bitta mintaqa (O'zbekiston, UTC+5, DST yo'q) uchun. Backend/frontend
o'rtasidagi barcha vaqt maydonlari API orqali ISO-8601 UTC formatda uzatiladi
(`API_CONTRACT.md`), shuning uchun `TIME_ZONE`ning API javoblariga bevosita
ta'siri yo'q — bu faqat server-tarafidagi ko'rsatish (log yozuvlari, admin,
kelajakdagi email/eslatma shablonlari) uchun muhim. `Asia/Tashkent`ga o'tish
shu server-tarafidagi ko'rinishlarni to'g'ridan-to'g'ri mahalliy vaqtda
ko'rsatadi, qo'shimcha konvertatsiya kodisiz.

## Oqibatlar

**Ijobiy:** admin panel va server loglari mahalliy vaqtda o'qiladi; kelajakda
email/eslatma funksiyalari qo'shilganda ular avtomatik to'g'ri vaqt zonasida
bo'ladi.

**Salbiy:** `USE_TZ = True` saqlangani uchun bu amaliy tavakkalchilikni
oshirmaydi — lekin agar kimdir keyinchalik `USE_TZ = False`ga o'tishga
urinsa (masalan, "soddalashtirish" niyatida), bu barcha saqlangan vaqtlarni
noto'g'ri talqin qilishga olib keladi. Bu birlashtirilmasligi kerak bo'lgan
ikkita alohida qaror: **saqlash zonasi** (har doim UTC, `USE_TZ=True`) va
**ko'rsatish zonasi** (`TIME_ZONE`).

## Rejadan chetlashish

Yo'q.
