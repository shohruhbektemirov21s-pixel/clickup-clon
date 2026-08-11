# 6 — Migratsiya siyosati

Holat: Qabul qilindi | Sana: 2026-08-11

## Kontekst

Django migratsiyalari kodni model bilan sinxronlashtiradi; ular kod bilan
birga versiyalanmasa (masalan, kimdir model o'zgartirib migratsiya
yaratishni unutsa) prod deploy vaqtida `migrate` xato beradi yoki — battari —
jimgina eskirgan sxema bilan qoladi. Bir nechta agent/dasturchi parallel
ishlaganda migratsiya to'qnashuvi (ikki PR bir xil raqamli migratsiya yaratishi)
alohida xavf.

## Qaror

CI'da majburiy darvoza: `.github/workflows/ci.yml:116-118` — "Migratsiya
drift gate" qadami `python manage.py makemigrations --check --dry-run`ni
ishga tushiradi. Agar modelda migratsiyasiz o'zgarish bo'lsa, job qizil
bo'ladi. Bundan tashqari **"bitta PR — bitta migratsiya"** qoidasi amal
qiladi: har bir PR o'z model o'zgarishlari uchun eng ko'pi bilan bitta yangi
migratsiya fayli qo'shadi (kerak bo'lsa `--merge` bilan oldindan
to'qnashuvlarni hal qilib).

## Sabab

`makemigrations --check --dry-run` — bepul va aniq darvoza: model va
migratsiya faylining haqiqiy fayl tizimidagi holati orasidagi har qanday
farqni ushlaydi, taxminga tayanmaydi. `backend-sqlite` legi
(`ci.yml:227-269`, Windows/SQLite) esa alohida `migrate --noinput` qadamini
ham ishga tushiradi — ya'ni migratsiyalar ikkala backend'da (Postgres va
SQLite) ham qo'llanilishi tekshiriladi, chunki `position` ustunining
collation semantikasi ikkalasida farq qiladi (`ci.yml:6-10` izohi).

"Bitta PR — bitta migratsiya" qoidasi kod ko'rib chiqishni osonlashtiradi
(bitta migratsiya fayli = bitta model o'zgarishi to'plami, kodni o'qish
osonroq) va parallel PR'lar orasidagi migratsiya raqami to'qnashuvi
ehtimolini kamaytiradi — chunki har bir PR kichik va tez birlashtiriladi.

## Oqibatlar

**Ijobiy:** modelni o'zgartirib migratsiyani unutish endi CI'da mumkin emas;
Postgres va SQLite orasidagi farqlar erta topiladi.

**Salbiy:** darvoza faqat "migratsiya YETISHMAYAPTIMI" ni tekshiradi — u
migratsiyaning **to'g'riligini** (masalan, katta jadvalda bloklovchi
`ALTER TABLE`) tekshirmaydi. "Bitta PR — bitta migratsiya" qoidasi tashkiliy
(CI tomonidan majburlanmaydi) — kod ko'rib chiqishda amalga oshiriladi, ya'ni
inson e'tiboriga bog'liq. Ikki parallel PR bir xil model ustida ishlasa,
birinchisi birlashtirilgach ikkinchisi baribir rebase + `makemigrations`ni
qayta ishga tushirishga muhtoj bo'ladi.

## Rejadan chetlashish

Yo'q.
