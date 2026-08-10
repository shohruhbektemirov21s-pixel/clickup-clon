# Nima o'zgardi?

<!-- 2-4 gapda tushuntiring: muammo nima edi va bu PR uni qanday hal qiladi. -->

## Turi

- [ ] Yangi funksiya (feat)
- [ ] Xatolik tuzatish (fix)
- [ ] Refactor / texnik qarz
- [ ] Hujjat (docs)
- [ ] CI / infratuzilma
- [ ] Breaking change (API_CONTRACT o'zgardi)

## Bog'liq issue / vazifa

<!-- Masalan: Closes #12 -->

## Qanday tekshirildi?

<!-- Qaysi testlar yozildi/ishga tushirildi, qo'lda qanday tekshirdingiz. -->

- [ ] `../.venv/Scripts/python.exe -m pytest` (backend) o'tdi
- [ ] `npm run lint` va `npm run build` (frontend) o'tdi
- [ ] Qo'lda brauzerda tekshirildi

## Skrinshot / GIF (UI o'zgarishi bo'lsa)

<!-- Oldin / keyin -->

---

## Xavfsizlik tekshiruv ro'yxati

Har bir band uchun: belgilang yoki nega tegishli emasligini yozing (`N/A — sabab`).

- [ ] **Workspace scope** — barcha query'lar joriy foydalanuvchining workspace/member a'zoligiga filtrlangan; boshqa workspace ma'lumotiga sizib chiqish yo'q.
- [ ] **404-vs-403 qoidasi** — foydalanuvchi ko'rmasligi kerak bo'lgan resurs uchun `404` qaytadi (mavjudligini oshkor qilmaydi); ko'rish huquqi bor, lekin amal bajarish huquqi yo'q bo'lsa `403`.
- [ ] **Mass assignment yo'q** — serializer'da `fields` aniq sanab o'tilgan (`__all__` emas); `owner`, `workspace`, `created_by`, `role`, `is_staff` kabi maydonlar `read_only`.
- [ ] **Throttle** — yangi auth / og'ir / yozuv endpoint'lariga scoped throttle qo'yilgan (`AUTH_THROTTLE_RATE`, `COMMENT_THROTTLE_RATE` yoki yangi rate settings'da).
- [ ] **Migratsiya reverse qilinadi** — `migrate <app> <oldingi>` bilan orqaga qaytadi; `RunPython` uchun `reverse_code` berilgan; ma'lumot yo'qotuvchi qadam alohida ta'kidlangan.
- [ ] **`docs/API_CONTRACT.md` yangilangan** — API o'zgargan bo'lsa, shartnoma shu commit'da yangilandi va `frontend/src/types/api.ts` maydonma-maydon mos.
- [ ] **O'zbekcha UI matni** — barcha yangi ko'rinadigan matn (tugma, xato, toast, placeholder) o'zbek tilida.
- [ ] **Testlar qo'shildi** — yangi xatti-harakat uchun test bor; ruxsat/permission uchun ijobiy va salbiy (begona foydalanuvchi) holat ham qoplangan.
- [ ] **Sir yo'q** — kod, log yoki test fixture'da haqiqiy token/parol/kalit yo'q; yangi env o'zgaruvchi `backend/.env.example` yoki `frontend/.env.example` ga qo'shilgan.
- [ ] **Realtime izchilligi** — event'lar service/serializer qatlamidan chiqariladi (view'dan emas), REST va WebSocket bir xil holatni beradi.
