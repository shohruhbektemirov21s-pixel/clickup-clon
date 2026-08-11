# 1 — Fayl saqlash (attachments)

Holat: Qabul qilindi | Sana: 2026-08-11

## Kontekst

Vazifa biriktirmalari (`TaskAttachment`, `backend/apps/tasks/models.py:229`) va
foydalanuvchi avatarlari yuklanadigan fayllardir. Ularni qayerda va qanday saqlash —
mahalliy diskmi, bulut obyekt-do'konimi — ko'p instansli joylashtirishga,
zaxira nusxalashga va konteyner qayta ishga tushishiga bevosita ta'sir qiladi.

## Qaror

`backend/config/settings.py:507-510` dagi `STORAGES["default"]` —
`django.core.files.storage.FileSystemStorage`. Fayllar `MEDIA_ROOT`
(`backend/media/`, `settings.py:513`) ostida mahalliy diskka yoziladi va
`MEDIA_URL = "media/"` orqali beriladi. Bulut obyekt-do'koni (S3, GCS va h.k.)
uchun `STORAGES` backend'i yo'q.

## Sabab

MVP bosqichida bitta backend instansi (yoki Docker Compose'dagi bitta konteyner +
bog'langan volume) ishlatiladi — `docker-compose.yml` da `backend` xizmati uchun
alohida obyekt-do'kon konteyneri yo'q. Mahalliy disk eng oddiy yo'l: qo'shimcha
kredensial, qo'shimcha xizmat yoki tarmoq bog'liqligi talab qilmaydi.
`MAX_ATTACHMENT_MB = 10` (`settings.py:521`, `env`dan) hajmni ataylab past tutadi,
bu diskning tez to'lishi xavfini ham kamaytiradi.

## Oqibatlar

**Ijobiy:** nol qo'shimcha infratuzilma, dev/CI/Docker'da bir xil ishlaydi,
sozlash yo'q.

**Salbiy:** backend bir nechta instansda (masalan, gorizontal masshtablashda)
ishga tushirilsa, har bir instans o'z diskini ko'radi — umumiy `NFS`/bulut
volume bo'lmasa fayllar instansga bog'lanib qoladi. Konteyner o'chirilsa
(`docker compose down -v`) yuklangan fayllar ham yo'qoladi — `docs/DOCKER.md`
buni zaxira bo'limida qayd etadi. CDN yo'q, ya'ni fayl yuklab olish to'g'ridan-to'g'ri
Django/WhiteNoise orqali o'tadi.

## Rejadan chetlashish

Yo'q — Master Plan bu qarorni oldindan belgilamagan; bu MVP uchun amaliy tanlov.
Prodakshnga o'tishda `STORAGES["default"]`ni S3-moslashuvchan backend'ga
(`django-storages`) almashtirish kerak bo'ladi — bu alohida ADR bilan qayd etilishi
kerak, chunki media URL shakli va CORS siyosati o'zgaradi.
