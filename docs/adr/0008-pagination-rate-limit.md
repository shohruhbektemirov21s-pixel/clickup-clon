# 8 — Pagination va rate limiting

Holat: Qabul qilindi | Sana: 2026-08-11

## Kontekst

Ro'yxat endpointlari cheklanmagan natija qaytarsa, katta ish maydonlarida
(ko'plab vazifa/a'zo) javob hajmi va DB yuki nazoratsiz o'sadi. Xuddi shunday,
auth/register/invite kabi endpointlar cheklanmasa brute-force va spam xavfi
tug'iladi.

**Diqqat:** bu ADR yozilayotgan payida backend agenti sahifalash
standartlarini (`page_size`/`max_page_size`) `50/200`dan `25/100`ga
o'zgartirish ustida ishlamoqda. Ushbu ADR shu maqsadli holatni qayd etadi.

## Qaror

Sahifalash: `config.pagination.StandardPagination`
(`backend/config/pagination.py`) — standart sahifa hajmi **25**, maksimal
**100** (`page_size` so'rov parametri orqali oshirilishi mumkin, 100dan
oshsa `400 validation_error`). Bu `REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"]`
sifatida global qo'llanadi (`settings.py:248-249`).

Rate limiting: DRF throttle sinflari, har biri o'z `env`-sozlanadigan
stavkasiga ega (`settings.py:263-282`) — masalan `auth` (10/min), `register`
(5/hour), `invite` (20/hour), `attachment` (30/hour), `comments` (60/min),
`realtime_ticket` (60/min), `demo` (10/hour). Har bir sezgir endpoint-sinfi
o'zining stavkasiga ega — bitta global stavka emas.

## Sabab

Kichikroq standart sahifa hajmi (25) tarmoq orqali uzatiladigan javob
hajmini va frontend rendering yukini kamaytiradi — ayniqsa mobil/sekin
ulanishlarda. Maksimal 100 esa "bitta so'rovda hammasini ol" turdagi
suiiste'molni cheklaydi (masalan, ish maydonining barcha vazifalarini bitta
so'rovda tortib olish orqali DB yukini oshirish).

Har bir throttle sinfi alohida stavkaga ega, chunki xavf profili endpoint
bo'yicha farq qiladi: `auth` kredensial to'plash (credential stuffing)ga
qarshi tor bo'lishi kerak, `refresh` esa har sahifa yuklanishida chaqiriladi
va NAT ortidagi butun ofis bitta IP'ni ulashishi mumkin — shuning uchun
ataylab keng (`settings.py:33-36` izohi). Bitta umumiy stavka ikkalasini
ham noto'g'ri xizmat qilardi.

## Oqibatlar

**Ijobiy:** javob hajmi va DB yuki nazorat ostida; har bir endpoint o'z
xavf profiliga mos tor/keng stavkaga ega.

**Salbiy:** standart sahifa hajmining kamayishi (50→25) mavjud frontend
so'rovlar sonini ko'paytiradi (ko'proq sahifa = ko'proq so'rov) katta
ro'yxatlarda — frontend cheksiz skroll/sahifalash UI'si shunga moslashishi
kerak. Throttle stavkalarining ko'pligi sozlash sirtini kengaytiradi
(`.env.example`da har biri alohida qator) — yangi endpoint qo'shilganda
tegishli throttle sinfi va stavkasini unutish oson.

## Rejadan chetlashish

Yo'q — reja aniq sonlarni belgilamagan, bu amaliy tanlov.
