# 5 — Email backend

Holat: Qabul qilindi | Sana: 2026-08-11

## Kontekst

Taklif (invitation) oqimi va kelajakdagi bildirishnomalar odatda email orqali
yuboriladi. `backend/config/settings.py` faylida `EMAIL_BACKEND` sozlamasi
umuman yo'q — qidiruv (`grep EMAIL_BACKEND backend/`) hech narsa topmaydi.

## Qaror

**Hozircha email umuman yuborilmaydi.** `Invitation` modeli
(`backend/apps/workspaces/models.py:145-151`) o'zining `token`ini
(`CharField(max_length=64, unique=True)`) generatsiya qiladi; taklif oqimi bu
token bilan yasalgan havola orqali ishlaydi — havolani foydalanuvchiga
yetkazish (nusxalab yuborish, boshqa kanal orqali ulashish) mahsulot
oqimidan tashqarida, qo'lda bajariladi. Backend hech qanday SMTP/email
xizmatiga ulanmaydi, `django.core.mail` chaqirilmaydi.

## Sabab

Bu **haqiqiy holat**, ideal emas — talab shuni "halol yozib qo'yish"dan
iborat. MVP bosqichida email infratuzilmasi (SMTP kredensiallari, jo'natuvchi
domenning SPF/DKIM sozlamasi, yetkazish monitoringi) hali qurilmagan, shu
sababli `EMAIL_BACKEND` konfiguratsiya qilinmagan. Token-asosidagi havola
email talab qilmasdan ham to'liq ishlaydi (front-end taklif havolasini
ko'rsatadi/nusxalaydi), shuning uchun bu funksional bloklovchi emas — lekin
foydalanuvchi tajribasi cheklangan: taklif qiluvchi havolani qo'lda
yuborishi kerak.

## Oqibatlar

**Ijobiy:** qo'shimcha tashqi bog'liqlik yo'q (SMTP provayder, kredensial
boshqaruvi, yetkazilish monitoringi), demo/dev muhitida email domenini
sozlashning hojati yo'q.

**Salbiy:** taklif qiluvchi havolani email orqali avtomatik olmaydi — buni
qo'lda ulashish kerak. Parolni tiklash, bildirishnoma email'lari kabi
kelajakdagi funksiyalar ham hozircha imkonsiz (`apps.notifications`
ilovasi mavjud, lekin u WebSocket/in-app bildirishnomalar uchun — email
kanali emas). `EMAILCHECK_*` sozlamalari (`settings.py:544-555`) faqat
email SINTAKSISI/MX/SMTP-mavjudligini TEKSHIRISH uchun — email YUBORISH
bilan aloqasi yo'q, ikkalasini aralashtirib yubormaslik kerak.

## Rejadan chetlashish

Reja email orqali taklif yuborishni nazarda tutgan bo'lishi mumkin; hozirgi
amalga oshirish token/havola-asosidagi oqim bilan cheklangan. Haqiqiy SMTP
backend (`django.core.mail.backends.smtp.EmailBackend` yoki uchinchi tomon
provayder) qo'shilishi alohida keyingi ish — bu ADR shunchaki hozirgi
bo'shliqni qayd etadi.
