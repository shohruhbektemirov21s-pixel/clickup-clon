/**
 * ============================================================================
 *  UZ — ilovaning o'zbekcha lug'ati (yagona manba)
 * ============================================================================
 *
 * NEGA BU FAYL BOR
 * ----------------
 * Ikkita sabab bor.
 *
 * 1. **Domen yorliqlari.** Status va muhimlik endi bazada NOM ham, RANG ham
 *    saqlamaydi: server faqat kod qaytaradi (`todo` / `in_progress` /
 *    `review` / `done`, `urgent` … `none`). Ya'ni yorliq va rang
 *    **klientning ishi** bo'lib qoldi, va ular bitta joyda turishi kerak —
 *    aks holda «Bajarildi» ni bir ekranda «Yakunlandi» deb yozib qo'yish hech
 *    gap emas. Kontrakt (`docs/API_CONTRACT.md` §9) buni ochiq aytadi.
 *
 * 2. **Interfeys matni.** Har bir komponent ichida yozib ketilgan o'zbekcha
 *    matn qidirib bo'lmaydigan, qayta ishlatib bo'lmaydigan va bir xilligini
 *    tekshirib bo'lmaydigan holatga olib keldi: «Bekor qilish» bir necha
 *    joyda, «Qayta urinish» olti joyda alohida yozilgan edi. Endi ular shu
 *    yerda.
 *
 * QANDAY KENGAYTIRILADI
 * ---------------------
 * 1. Yangi matnni MAVJUD bo'limlardan biriga qo'shing (bo'limlar quyida
 *    `// ---- <NOM> ----` sarlavhalari bilan ajratilgan). Mos bo'lim bo'lmasa,
 *    fayl oxiriga xuddi shu uslubda yangi bo'lim oching.
 * 2. **Avval `COMMON` ga qarang.** Takrorlanadigan matn (Bekor qilish,
 *    Saqlash, Yopish, Qayta urinish, Yuklanmoqda…) faqat `COMMON` da bo'ladi;
 *    ekranga xos bo'lgani o'z bo'limiga tushadi.
 * 3. Nomlash: domen jadvallari `SCREAMING_SNAKE_CASE` va `Record<TIP, string>`
 *    (backend enum'ga qiymat qo'shsa TypeScript darhol aytadi); ekran matni
 *    esa `SCREAMING_SNAKE_CASE` obyekt ichida `camelCase` kalit bilan —
 *    `AUTH.errEmailInvalid`. Yassi `t("a.b.c")` kalitlari ATAYLAB yo'q:
 *    obyekt tipi avtomatik to'ldirishni beradi va xato kalitni
 *    kompilyatsiyada ushlaydi.
 * 4. O'zgaruvchi qatnashsa — funksiya, masalan
 *    `unreadCount: (n: number) => ...`. JSX ichida qo'lda ulash matnni yana
 *    ikkiga bo'lib yuboradi.
 * 5. **HTML entity ISHLATILMAYDI.** Bu yerdagi qiymatlar oddiy satr, JSX matn
 *    tuguni emas — brauzer ularni entity sifatida ochmaydi va apostrofning
 *    entity shakli ekranda xom holida ko'rinib qoladi. Apostrof
 *    to'g'ridan-to'g'ri yoziladi: `bo'lim`, `yo'q`.
 * 6. Rang faqat shu yerda hex bo'lib yashaydi va `app/globals.css` dagi
 *    `@theme` tokenlariga MOS bo'lishi kerak (ikkalasi bir xil palitra).
 *    Tailwind sinfi yetarli bo'lgan joyda hex emas, sinf ishlating.
 * 7. Bu fayl butun ilovaga (shu jumladan testlarga va lug'at tekshiruviga)
 *    import qilinadi — ichida React yoki brauzer API'si BO'LMASIN.
 */

import type {
  PermissionGroupKey,
  Priority,
  Profession,
  Role,
  SpaceAccess,
  TaskStatus,
} from "@/types/api";

// ---------------------------------------------------------------------------
// APP — mahsulot brendi
// ---------------------------------------------------------------------------
//
// Nom FAQAT shu yerda yoziladi: logotip, brauzer yorlig'i va landing sarlavhasi
// hammasi shundan oziqlanadi. DIQQAT: `localStorage` kalitlari (`clickish.*`),
// demo hisob emaillari va e2e fiksturalari brend emas — ular IDENTIFIKATOR va
// bu yerga bog'lanmaydi; o'zgartirilsa mavjud sessiyalar va demo ma'lumot buziladi.

const BRAND = "UzWork";

export const APP = {
  brand: BRAND,
  /** Logotip kvadratchasidagi harf — brend nomining birinchi harfi. */
  brandInitial: "U",
  /** Brauzer yorlig'i: «Kirish — UzWork». */
  pageTitle: (screen: string) => `${screen} — ${BRAND}`,
} as const;

// ---------------------------------------------------------------------------
// COMMON — bir necha ekranda takrorlanadigan matn
// ---------------------------------------------------------------------------
//
// Bu yerga faqat MA'NOSI ekrandan mustaqil bo'lgan so'zlar tushadi. «Saqlash»
// hamma joyda saqlash; «Taklif yuborish» esa faqat taklif dialogida ma'noli —
// u o'z bo'limida qoladi.

export const COMMON = {
  cancel: "Bekor qilish",
  save: "Saqlash",
  saving: "Saqlanmoqda…",
  close: "Yopish",
  retry: "Qayta urinish",
  loading: "Yuklanmoqda…",
  searching: "Qidirilmoqda…",
  add: "Qo'shish",
  join: "Qo'shilish",
  login: "Kirish",
  register: "Ro'yxatdan o'tish",
  email: "Email",
  password: "Parol",
  /** Ixtiyoriy maydon belgisi — qavs bilan, yorliq yonida turadi. */
  optional: "(ixtiyoriy)",
  notSelected: "Tanlanmagan",
  delete: "O'chirish",
  name: "Nomi",
  /** Ko'rinish yorlig'i — ro'yxat sahifasi va landing skrinshotida bir xil. */
  list: "Ro'yxat",
  board: "Doska",
  /** Doska ustuni, ro'yxat guruhi va landing skrinshotida takrorlanadi. */
  addTask: "Vazifa qo'shish",
  tasksLoadFailed: "Vazifalarni yuklab bo'lmadi.",
  backToWorkspace: "Ish maydoniga qaytish",
  createTask: "Vazifa yaratish",
  createSpace: "Bo'lim yaratish",
  createList: "Ro'yxat yaratish",
  /** Ish maydoni nomi hali kelmaganda ko'rsatiladigan umumiy nom. */
  workspaceFallback: "Ish maydoni",
  /** Tarmoq / kutilmagan xato — auth formasi ham, mutatsiyalar ham shuni ko'rsatadi. */
  errNetwork: "Nimadir xato ketdi. Internet aloqasini tekshirib, qayta urinib ko'ring.",
  errThrottled: "Urinishlar juda ko'p. Biroz kutib, qayta urinib ko'ring.",
  /** `lib/permissions.ts` dagi tooltip ham, mutatsiya toast'i ham shu matnni beradi. */
  errPermissionDenied: "Sizda bu amal uchun ruxsat yo'q.",
  /** Bo'sh katak — `null` yoki ko'rsatilmaydigan qiymat o'rniga. */
  emptyValue: "—",
  /** Ismi ham, emaili ham yo'q foydalanuvchi. */
  someone: "Foydalanuvchi",
} as const;

// ---------------------------------------------------------------------------
// STATUS (kontrakt §9 — yopiq to'plam, o'zgarmas tartib)
// ---------------------------------------------------------------------------

/**
 * Doska ustunlari va ro'yxat guruhlarining tartibi.
 *
 * DIQQAT: bu tartib serverning `STATUS_ORDER` iga mos, lekin doska ustunlari
 * baribir **javobning o'zidan** chiziladi (grouped payload doim to'rtta
 * guruhni shu tartibda qaytaradi). Bu massiv — grouped javob yo'q joylarda
 * (masalan tanlagich ro'yxati) kerak bo'ladigan zaxira tartib.
 */
export const STATUS_ORDER: readonly TaskStatus[] = [
  "todo",
  "in_progress",
  "review",
  "done",
] as const;

export const STATUS_LABEL: Record<TaskStatus, string> = {
  todo: "Boshlanmagan",
  in_progress: "Jarayonda",
  review: "Tekshirilmoqda",
  done: "Bajarildi",
};

/**
 * `app/globals.css` dagi `--color-status-*` tokenlari bilan bir xil qiymatlar.
 * Inline `style={{ backgroundColor }}` kerak bo'lgan joylar uchun (SVG,
 * dinamik nuqta) — Tailwind sinfi yetadigan joyda `STATUS_BG_CLASS` ni oling.
 */
export const STATUS_COLOR: Record<TaskStatus, string> = {
  todo: "#87909e",
  in_progress: "#4194f6",
  review: "#7b68ee",
  done: "#6bc950",
};

/** Tailwind fon sinfi — `@theme` tokenidan hosil bo'ladi. */
export const STATUS_BG_CLASS: Record<TaskStatus, string> = {
  todo: "bg-status-todo",
  in_progress: "bg-status-in-progress",
  review: "bg-status-review",
  done: "bg-status-done",
};

/**
 * Yopiq (bajarilgan) status. Server tomonda `CLOSED_STATUSES` — hozircha
 * bitta kod, lekin tekshiruv har joyda `=== "done"` deb yozilmasin.
 */
export function isClosedStatus(status: TaskStatus): boolean {
  return status === "done";
}

// ---------------------------------------------------------------------------
// MUHIMLIK (kontrakt §10.2 — `normal` `medium` ga qayta nomlangan)
// ---------------------------------------------------------------------------

/** Tanlagichdagi tartib: eng muhimdan eng past tomon, oxirida «yo'q». */
export const PRIORITY_ORDER: readonly Priority[] = [
  "urgent",
  "high",
  "medium",
  "low",
  "none",
] as const;

export const PRIORITY_LABEL: Record<Priority, string> = {
  urgent: "Juda muhim",
  high: "Yuqori",
  medium: "O'rtacha",
  low: "Past",
  none: "Muhimlik yo'q",
};

/** Bayroqcha rangi — `--color-priority-*` tokenlari. */
export const PRIORITY_CLASS: Record<Priority, string> = {
  urgent: "text-priority-urgent",
  high: "text-priority-high",
  medium: "text-priority-medium",
  low: "text-priority-low",
  none: "text-priority-none",
};

// ---------------------------------------------------------------------------
// MUDDAT GURUHLARI (`lib/task-buckets.ts` dagi `BucketKey` uchun)
// ---------------------------------------------------------------------------
//
// Izoh: guruhlash mantiqi `lib/task-buckets.ts` da qoladi, faqat MATN shu
// yerga ko'chirilgan.

export const DUE_BUCKET_LABEL = {
  overdue: "Muddati o'tgan",
  today: "Bugun",
  week: "Shu hafta",
  later: "Keyinroq",
  none: "Muddatsiz",
} as const;

// ---------------------------------------------------------------------------
// AUTH — kirish va ro'yxatdan o'tish formalari
// ---------------------------------------------------------------------------
//
// `banner*` — serverning javob KODI bo'yicha tanlanadigan umumiy xabar;
// qolganlari maydon tekshiruvlari va yorliqlar. Server matnini ko'r-ko'rona
// ko'rsatmaymiz: `authentication_failed` inglizcha matn bilan keladi va u
// foydalanuvchi ekraniga chiqib qolardi.

export const AUTH = {
  bannerNetwork: COMMON.errNetwork,
  bannerInvalidCredentials: "Bunday email va parolga ega faol hisob topilmadi.",
  bannerThrottled: COMMON.errThrottled,
  bannerInviteExpired: "Taklif muddati tugagan yoki bekor qilingan.",
  bannerInviteUsed: "Bu taklif allaqachon ishlatilgan.",

  errFullNameTooShort: "To'liq ismni kiriting (kamida 2 ta belgi).",
  errEmailInvalid: "To'g'ri email manzilini kiriting.",
  errPasswordTooShort: "Parol kamida 8 ta belgidan iborat bo'lsin.",
  errPasswordAllDigits: "Parol faqat raqamlardan iborat bo'lmasin.",
  errPasswordConfirmRequired: "Parolni tasdiqlang.",
  errPasswordMismatch: "Parollar mos kelmadi.",
  errTermsRequired: "Davom etish uchun shartlarga rozilik bildiring.",

  emailPlaceholder: "siz@kompaniya.uz",
  signingIn: "Kirilmoqda…",
  noAccountQuestion: "Hisobingiz yo'qmi?",
  registerCta: "Ro'yxatdan o'ting",
  haveAccountQuestion: "Hisobingiz bormi?",

  fullNameLabel: "To'liq ism",
  fullNamePlaceholder: "Alisher Navoiy",
  inviteEmailLocked: "Taklif shu manzilga yuborilgan, uni o'zgartirib bo'lmaydi.",
  passwordHint: "Kamida 8 ta belgi, faqat raqamlardan iborat bo'lmasin.",
  passwordConfirmLabel: "Parolni tasdiqlash",
  passwordShow: "Parolni ko'rsatish",
  passwordHide: "Parolni yashirish",
  strengthVeryWeak: "juda zaif",
  strengthWeak: "zaif",
  strengthMedium: "o'rtacha",
  strengthStrong: "kuchli",
  professionLabel: "Kasb roli",
  professionHint:
    "Bu ish maydonidagi ruxsatlarga ta'sir qilmaydi — jamoadagi o'rningizni ko'rsatadi.",
  // `workspaceName*` ro'yxatdan o'tish formasida ham, «Birinchi ish
  // maydoningizni yarating» kartasida ham ishlatiladi — matn bitta.
  workspaceNameLabel: "Ish maydoni nomi",
  workspaceNamePlaceholder: "Acme MChJ",

  // Rozilik qatori bo'laklarga bo'lingan, chunki ikkita hujjat nomi JSX
  // ichida alohida `<span>` bilan ajratib ko'rsatiladi.
  termsOfService: "Foydalanish shartlari",
  termsAnd: " va ",
  privacyPolicy: "Maxfiylik siyosati",
  termsAgreeSuffix: "ga roziman",

  loginWelcome: "Xush kelibsiz!",
  registerTitle: "Hisob yarating",
  registerSubtitle: "Beta davrida bepul.",

  creatingAccount: "Hisob yaratilmoqda…",
  createAccount: "Hisob yaratish",
} as const;

// ---------------------------------------------------------------------------
// INVITE — ommaviy taklif sahifasi (`/invite/[token]`)
// ---------------------------------------------------------------------------
//
// XAVFSIZLIK ESLATMASI: xato holatlarida ish maydoni nomi OSHKOR QILINMAYDI,
// shuning uchun `expired*` matnlari hech qanday parametr olmaydi.

export const INVITE = {
  goToLogin: "Kirish sahifasiga o'tish",

  missingLinkTitle: "Taklif havolasi topilmadi",
  missingLinkHint:
    "Xavfsizlik uchun taklif kodi manzil qatorida saqlanmaydi. Emaildagi havolani shu brauzerda qaytadan oching.",
  expiredTitle: "Taklif muddati tugagan yoki bekor qilingan",
  expiredHint: "Havola ishlamayapti. Ish maydoni administratoridan yangi taklif so'rang.",
  acceptFailed: "Taklifni qabul qilib bo'lmadi. Havola eskirgan bo'lishi mumkin.",

  heading: (workspaceName: string) =>
    `Siz «${workspaceName}» ish maydoniga taklif qilingansiz`,

  // Email qalin `<span>` bilan ajratilgani uchun matn ikki bo'lak.
  sentToPrefix: "Taklif ",
  sentToSuffix: " manziliga yuborilgan.",
  roleGivenPrefix: "Sizga ",
  roleGivenSuffix: " roli berilgan",
  roleReadOnly: "Rolni administrator belgilaydi — uni bu yerda o'zgartirib bo'lmaydi.",

  joining: "Qo'shilmoqda…",
  joinWorkspace: "Ish maydoniga qo'shilish",

  signedInPrefix: "Siz hozir ",
  signedInSuffix: " hisobi bilan kirgansiz.",
  // Nom ATAYLAB `use` bilan boshlanmaydi: `react-hooks/rules-of-hooks` bunday
  // chaqiruvni React hook deb hisoblab, shartli render ichida xato beradi.
  invitedAccountHint: (email: string) =>
    ` Taklifni qabul qilish uchun ${email} hisobiga kiring.`,
  loginWithOtherAccount: "Boshqa hisob bilan kirish",
  loginAndJoin: "Kirish va qo'shilish",

  /** Brauzer yorlig'i uchun qisqa nom. */
  pageTitle: "Taklif",
  fallbackTitle: "Taklif havolasi to'liq emas",
  fallbackHint:
    "Xavfsizlik uchun taklif kodi manzil qatorida saqlanmaydi. Emaildagi havolani qaytadan oching yoki hisobingizga kiring.",
} as const;

// ---------------------------------------------------------------------------
// INVITE_EMAIL — tanlagich ichidagi «manzilni tekshir va taklif qil» bloki
// ---------------------------------------------------------------------------

export const INVITE_EMAIL = {
  throttled: "Juda ko'p tekshiruv. Biroz kutib, qayta urinib ko'ring.",
  forbidden: "Taklif yuborish huquqingiz yo'q.",
  checkFailed: "Manzilni tekshirib bo'lmadi.",
  notInWorkspace: "Bu manzil ish maydonida yo'q. Avval mavjudligini tekshiring.",
  checking: "Tekshirilmoqda…",
  recheck: "Qayta tekshirish",
  check: "Tekshirish",
  alreadyInvited: "Taklif yuborilgan",
  invite: "Taklif qilish",
  uncertain:
    "Aniq javob olinmadi — taklif yuborish mumkin, lekin yetib borishiga kafolat yo'q.",
} as const;

// ---------------------------------------------------------------------------
// INVITE_DIALOG — «Jamoaga qo'shish» dialogi
// ---------------------------------------------------------------------------

export const INVITE_DIALOG = {
  title: "Jamoaga qo'shish",
  description:
    "Ro'yxatdan o'tgan foydalanuvchini darhol qo'shing yoki hisobi yo'q odamga taklif yuboring.",
  roleLabel: "Rol",
  guestHint: "Mehmonlar o'qishi va komment yozishi mumkin, lekin ro'yxat yarata olmaydi.",
  tabSearch: "Foydalanuvchi qidirish",
  tabEmail: "Email orqali taklif",

  emailLabel: "Email manzili",
  emailPlaceholder: "yangi.dev@kompaniya.uz",
  emailHint: "Ularga ish maydoniga qo'shilish havolasi emailda yuboriladi.",
  sending: "Yuborilmoqda…",
  sendInvite: "Taklif yuborish",

  searchPlaceholder: "Ism yoki email bo'yicha qidiring…",
  searchAria: "Ro'yxatdan o'tgan foydalanuvchilarni qidirish",
  searchTooShort: "Qidirish uchun kamida 2 ta belgi kiriting.",
  searchFailed: "Qidiruvni bajarib bo'lmadi.",
  searchEmpty:
    "Hech kim topilmadi. Hisobi yo'q bo'lsa, «Email orqali taklif» yorlig'idan foydalaning.",
  inTeam: "Jamoada",
  invitationPending: "Taklif yuborilgan",
} as const;

// ---------------------------------------------------------------------------
// SEARCH — buyruqlar paneli (`Ctrl+K`)
// ---------------------------------------------------------------------------

export const SEARCH = {
  title: "Tezkor qidiruv",
  dialogDescription:
    "Vazifa, ro'yxat, bo'lim yoki a'zoni qidiring. Yurish uchun yuqori/quyi o'q, ochish uchun Enter, yopish uchun Esc.",
  inputPlaceholder: "Vazifa, ro'yxat, bo'lim yoki a'zoni qidiring…",

  // Minimal uzunlik `use-search.ts` dagi `MIN_QUERY_LENGTH` dan keladi —
  // matnda raqamni ikkinchi marta yozib qo'ymaslik uchun parametr.
  tooShortTitle: (min: number) => `Kamida ${min} belgi kiriting`,
  tooShortHint: (min: number) => `Qidiruv ${min} ta belgidan boshlab ishlaydi.`,
  idleTitle: "Nimani qidiramiz?",
  idleHint: "Vazifalar, ro'yxatlar, bo'limlar va a'zolar bo'yicha qidiring.",
  recentHeading: "Yaqinda ochilganlar",
  failed: "Qidiruv amalga oshmadi.",

  groupTasks: "Vazifalar",
  groupLists: "Ro'yxatlar",
  groupContainers: "Bo'limlar va jildlar",
  groupMembers: "A'zolar",
  space: "Bo'lim",
  spaceWithoutList: "Bo'lim — ro'yxat yo'q",
  folder: "Jild",

  emptyTitle: (query: string) => `«${query}» bo'yicha hech narsa topilmadi`,
  emptyHint: "Imloni tekshiring yoki qisqaroq so'z bilan urinib ko'ring.",
  seeAll: (query: string) => `«${query}» bo'yicha barcha natijalar`,

  hintSelect: "tanlash",
  hintOpen: "ochish",
  hintClose: "yopish",
  scopeWorkspace: "Ish maydoni bo'yicha",

  errorHint: "Tarmoqni tekshirib, qayta urinib ko'ring.",
  resultCount: (query: string, total: number) =>
    `«${query}» bo'yicha ${total} ta natija`,
  tipSpelling: "Imloni tekshiring.",
  tipShorter: "Qisqaroq yoki boshqa so'z bilan urinib ko'ring.",
  tipArchived: "Arxivlangan va o'chirilgan yozuvlar qidiruvga tushmaydi.",

  pageSearchAria: "Ish maydoni bo'yicha qidirish",
  groupSpaces: "Bo'limlar",
  groupFolders: "Jildlar",
  noListInside: "Ichida ro'yxat yo'q",
  idlePagePrompt: "Vazifa, ro'yxat, bo'lim yoki a'zoni qidiring",
  // Yorliq tugmalari (`Ctrl` / `K`) orasida turgani uchun gap ikki bo'lak.
  shortcutHintPrefix: "Istalgan joydan",
  shortcutHintSuffix: "bilan tezkor qidiruvni oching.",
} as const;

// ---------------------------------------------------------------------------
// SPACE_MEMBERS — bo'lim jamoasi paneli
// ---------------------------------------------------------------------------

/** Har bir daraja uchun bitta qatorlik izoh (tanlagichlar ostida chiziladi). */
export const SPACE_ACCESS_HINT: Record<SpaceAccess, string> = {
  viewer: "Faqat ko'radi — bo'lim ichida hech narsa yoza olmaydi.",
  contributor: "Ish maydonidagi roli bo'yicha ishlaydi.",
  manager: "Loyiha menejeri — shu bo'lim ichida jamoani va mazmunni boshqaradi.",
};

export const SPACE_MEMBERS = {
  notFound: "Bu bo'lim topilmadi yoki sizda unga kirish huquqi yo'q.",
  backToWorkspace: COMMON.backToWorkspace,
  workspaceCrumb: COMMON.workspaceFallback,
  spaceFallback: "Bo'lim",
  teamSuffix: "— jamoa",
  privateBadge: "Yopiq",

  manageHint: "Loyihaga mos odamlarni tanlang va ularning darajasini belgilang.",
  readOnlyHint:
    "Bu bo'limda kim ishlayapti. O'zgartirish uchun bo'lim menejeriga murojaat qiling.",
  unsavedChanges: (changed: number, removed: number) =>
    `Saqlanmagan o'zgarishlar: ${changed} ta qo'shish/o'zgartirish, ${removed} ta olib tashlash.`,

  rosterHeading: "Ish maydoni a'zolari",
  searchPlaceholder: "Ism yoki email bo'yicha qidirish",
  searchAria: "Ish maydoni a'zolarini qidirish",
  noSuchMember: "Ish maydonida bunday a'zo yo'q.",
  noMatch: "Mos a'zo topilmadi.",
  inSpace: "Bo'limda",
  addToSpaceAria: (name: string) => `${name} ni bo'limga qo'shish`,

  teamHeading: "Bo'lim jamoasi",
  teamAria: "Bo'lim jamoasi",
  teamEmpty: "Hozircha hech kim biriktirilmagan.",
  unknownUser: "Noma'lum foydalanuvchi",
  autoAssignee: "Vazifa biriktirilgani uchun avtomatik qo'shilgan",
  autoCreator: "Bo'lim yaratuvchisi",
  accessAria: (name: string) => `${name} darajasi`,
  removeAria: (name: string) => `${name} ni bo'limdan olib tashlash`,
} as const;

// ---------------------------------------------------------------------------
// NOTIFICATIONS — qo'ng'iroqcha menyusi va to'liq sahifa
// ---------------------------------------------------------------------------

export const NOTIFICATIONS = {
  title: "Bildirishnomalar",
  bellAria: "Bildirishnomalar",
  bellAriaUnread: (count: number) => `Bildirishnomalar — ${count} ta yangi`,
  markAllRead: "Hammasini o'qildi",
  loadFailed: "Bildirishnomalarni yuklab bo'lmadi.",
  empty: "Hozircha bildirishnoma yo'q.",
  seeAll: "Barcha bildirishnomalar",
  unreadDot: "O'qilmagan",

  unreadCount: (count: number) => `${count} ta o'qilmagan xabar`,
  allRead: "Barcha xabarlar o'qilgan",
  tabAll: "Hammasi",
  tabUnread: "O'qilmagan",
  emptyUnread: "O'qilmagan xabar yo'q.",
  emptyHint:
    "Jamoaga odam qo'shilganda, sizga vazifa biriktirilganda yoki rolingiz o'zgarganda xabar shu yerda paydo bo'ladi.",
} as const;

// ---------------------------------------------------------------------------
// CHAT — suhbatlar ekrani
// ---------------------------------------------------------------------------
//
// `conversationsFailed` / `messagesFailed` ATAYLAB bo'sh holatdan ajratilgan:
// tarmoq uzilganda «Hali suhbat yo'q» deb yozish foydalanuvchiga yolg'on
// ma'lumot berardi.

export const CHAT = {
  conversationsFailed: "Suhbatlarni yuklab bo'lmadi.",
  conversationsEmpty:
    "Hali suhbat yo'q. Yuqoridagi tugmalar bilan kanal oching yoki hamkasbingizga yozing.",
  messagesFailed: "Xabarlarni yuklab bo'lmadi.",

  newChannelAria: "Kanal qo'shish",
  newChannelTitle: "Yangi kanal",
  newChannelDescription: "Kanal ish maydonining barcha a'zolariga ko'rinadi.",
  newChannelPlaceholder: "masalan: umumiy",
  create: "Yaratish",

  directAria: "Yozishma boshlash",
  directTitle: "Kimga yozasiz?",
  directDescription: "Ish maydoni a'zolaridan birini tanlang.",
  directEmpty: "Ish maydonida boshqa a'zo yo'q.",

  joinPrompt: "Yozish uchun avval kanalga qo'shiling.",
  messagesEmpty: "Hali xabar yo'q — birinchi bo'lib yozing.",
  deletedAuthor: "O'chirilgan hisob",
} as const;

// ---------------------------------------------------------------------------
// WORKSPACE_SETTINGS — ish maydoni sozlamalari
// ---------------------------------------------------------------------------

export const WORKSPACE_SETTINGS = {
  loadFailed: "Ish maydoni ma'lumotini yuklab bo'lmadi.",
  notFound: "Ish maydoni topilmadi yoki sizda endi ruxsat yo'q.",

  generalHeading: "Umumiy",
  renameDenied: "Ish maydoni nomini o'zgartirish uchun ruxsatingiz yo'q.",

  // Son hali kelmaganda sarlavha faqat so'zdan iborat bo'ladi.
  membersHeading: (count: number | undefined) =>
    count === undefined ? "A'zolar" : `A'zolar (${count})`,
  membersFailed: "A'zolarni yuklab bo'lmadi.",
  colName: "Ism",
  colProfession: "Kasbi",
  colRole: "Rol",
  colJoined: "Qo'shilgan",

  invitationsHeading: (count: number) => `Kutilayotgan takliflar (${count})`,
  invite: "Taklif qilish",
  invitationsDenied: "Takliflarni ko'rish uchun ruxsatingiz yo'q.",
  invitationsEmpty: "Kutilayotgan takliflar yo'q.",
  colInvitedBy: "Taklif qilgan",
  colExpires: "Muddati",
} as const;

// ---------------------------------------------------------------------------
// LANDING — ommaviy marketing sahifasi (`/`)
// ---------------------------------------------------------------------------
//
// Bu bo'lim SERVER komponentidan o'qiladi. Ikonkalar (lucide) va vizual
// komponentlar `components/marketing/` da qoladi — bu yerda faqat MATN.
// Parametrli sarlavhalar ruxsat kodlari sonini bazadan oladi va son
// kelmaganda umumiy matnga tushadi.

export const LANDING = {
  brand: APP.brand,

  navMain: "Asosiy",
  navFeatures: "Imkoniyatlar",
  navWhy: "Nima uchun",
  navQuickStart: "Ishga tushirish",
  navDocs: "Hujjatlar",

  heroBadge: "Ochiq kod · Django + React · to'liq o'zbek tilida",
  heroTitleLead: "Jamoangizning butun ishi —",
  heroTitleAccent: "bitta real vaqtli",
  heroTitleTail: "ish maydonida.",
  heroSubtitle: (codes: number | undefined) =>
    `${APP.brand} — bo'lim, jild, ro'yxat va vazifalar iyerarxiyasi, sudrab tartiblash, ${
      codes ? `${codes} ta ruxsat kodi` : "granular ruxsat kodlari"
    } bilan granular rollar va WebSocket orqali bir zumda yangilanadigan hamkorlik.`,
  heroFootnote:
    "Ro'yxatdan o'tish bepul — birinchi ish maydoningizni bir daqiqada yaratasiz.",

  statsAria: "Raqamlarda",
  statPermissionCodes: "ruxsat kodi",
  statRoles: "rol darajasi",
  statTasks: "vazifa",
  statMembers: "foydalanuvchi",

  featuresTitle: "Ishni boshqarish uchun kerak bo'lgan hamma narsa",
  featuresSubtitle:
    "Har bir imkoniyat ilovada allaqachon ishlaydi — ro'yxat va doska ko'rinishidan tortib huquqlar matritsasigacha.",
  featureHierarchyTitle: "Ish maydonlari iyerarxiyasi",
  featureHierarchyText:
    "Bo'lim → Jild → Ro'yxat → Vazifa. Yopiq bo'limlar faqat qo'shilgan a'zolarga ko'rinadi.",
  featureOrderingTitle: "Sudrab tartiblash",
  featureOrderingText:
    "Kasr pozitsiyalar bilan — vazifani ko'chirganda butun jadval qayta raqamlanmaydi.",
  featureRealtimeTitle: "Real vaqtli hamkorlik",
  featureRealtimeText:
    "Vazifa, izoh va presence hodisalari WebSocket orqali keladi; sahifani yangilash shart emas.",
  featurePermissionsTitle: (codes: number | undefined) =>
    codes ? `${codes} ta ruxsat kodi` : "Granular ruxsat kodlari",
  featurePermissionsText:
    "Har bir ish maydonida rol × huquq matritsasi sozlanadi; tekshiruv har doim serverda.",
  featureInvitesTitle: "Takliflar bilan jamoa",
  featureInvitesText:
    "Token bilan taklif yuboring — ro'yxatdan o'tgan zahoti a'zolik avtomatik beriladi.",
  featureFilesTitle: "Fayllar va faoliyat",
  featureFilesText:
    "Vazifalarga hujjat va rasm biriktiring, a'zo profillari va faoliyat tasmasini kuzating.",

  whyTitle: `Nima uchun ${APP.brand}`,
  whySubtitle:
    "Uchta qaror butun mahsulotni belgilaydi: real vaqt, jiddiy huquqlar va arzon tartiblash.",

  whyRealtimeEyebrow: "Real vaqt",
  whyRealtimeTitle: "Har bir o'zgarish — bir zumda, hammada",
  whyRealtimeText:
    "Vazifa ko'chdimi, izoh qo'shildimi, kimdir ro'yxatga kirdimi — hodisa servis qatlamidan chiqadi va WebSocket orqali barcha ochiq oynalarga yetadi. O'z aks-sadolaringiz bostiriladi, shuning uchun kursor sakramaydi.",
  whyRealtimeBullets: [
    "Presence — kim onlayn",
    "Avtomatik qayta ulanish",
    "Izoh va fayl hodisalari",
  ],

  whyPermissionsEyebrow: "Huquqlar",
  whyPermissionsTitle: "Rollar tugmani yashirish bilan cheklanmaydi",
  whyPermissionsText: (codes: number | undefined) =>
    `${codes ?? "Har bir"} ta ruxsat kodi rol × huquq matritsasida sozlanadi. Frontend faqat tugmani ko'rsatadi yoki yashiradi; ruxsatni har bir endpoint mustaqil tekshiradi. Ish maydonidan tashqaridagi resurs har doim 404 qaytaradi — mavjudligi oshkor bo'lmaydi.`,
  whyPermissionsBullets: [
    "Egasi / Admin / A'zo / Mehmon",
    "Egasi qatori qulflangan",
    "404 va 403 qoidasi",
  ],

  whyOrderingEyebrow: "Tartiblash",
  whyOrderingTitle: "Sudrash tez — chunki bitta qator yangilanadi",
  whyOrderingText:
    "Ko'chirishda mijoz qo'shni elementlarni hisoblab, serverga faqat before/after yuboradi. Server kasr pozitsiya qaytaradi va ro'yxat optimistik yangilanadi; xato bo'lsa avvalgi holatga qaytadi.",
  whyOrderingBullets: [
    "Optimistik yangilanish",
    "Ustunlar orasida status almashadi",
    "dnd-kit klaviatura bilan",
  ],

  quickStartEyebrow: "Ishga tushirish",
  quickStartTitle: "Bir buyruq — to'liq stek",
  quickStartTextLead:
    "Docker Compose PostgreSQL 16, Redis 7, Django backend va React frontendni birga ko'taradi. Backend ",
  quickStartTextTail:
    " ni o'zi bajaradi — keyin ro'yxatdan o'tib birinchi ish maydoningizni yaratasiz.",
  quickStartDocs: "Docker qo'llanmasi",

  ctaTitle: "Jamoangizni bugun ko'chiring",
  ctaSubtitle: "Ish maydoni yarating, bo'limlarni qo'shing va jamoani taklif qiling.",
  ctaPrimary: "Bepul boshlash",

  footerTagline:
    "Jamoaviy vazifa boshqaruvi: ish maydonlari, real vaqtli hamkorlik va granular huquqlar. Interfeys to'liq o'zbek tilida.",
  footerProduct: "Mahsulot",
  footerDocs: "Hujjatlar",
  footerProject: "Loyiha",
  footerApiContract: "API shartnomasi",
  footerDataModel: "Ma'lumotlar modeli",
  footerUiSpec: "UI spetsifikatsiyasi",
  footerPermissions: "Huquqlar dizayni",
  footerSource: "Manba kodi",
  footerPrd: "Mahsulot talablari",
  footerSprintPlan: "Sprint rejasi",
  footerDocker: "Docker qo'llanmasi",
  footerCopyright: `© 2026 ${APP.brand} — ochiq kodli vazifa boshqaruvi.`,
  footerBuiltWith: "React, Vite va Django asosida qurilgan.",
} as const;

// ---------------------------------------------------------------------------
// NOT_FOUND — mavjud bo'lmagan manzil (SPA'ning 404 marshruti)
// ---------------------------------------------------------------------------
//
// Next'da bunday manzilni server `notFound()` bilan qaytarardi. SPA'da hech
// qanday marshrutga tushmagan URL shu ekranga keladi.

export const NOT_FOUND = {
  title: "Sahifa topilmadi",
  description: "Bunday manzil yo'q yoki u ko'chirilgan.",
  goHome: "Bosh sahifaga",
} as const;

// ---------------------------------------------------------------------------
// BOARD — doska ko'rinishi (ustunlar, bo'sh holat, xatolik)
// ---------------------------------------------------------------------------

export const BOARD = {
  loadingAria: "Doska yuklanmoqda",
  loadFailedTitle: "Doskani yuklab bo'lmadi",
  loadFailedHint: "Ulanishni tekshiring va qaytadan urinib ko'ring.",

  dropHere: "Vazifani shu yerga tashlang",
  emptyColumnTitle: "Bu ustun bo'sh",
  // Ustun sarlavhasi qiymatdan keladi, shuning uchun funksiya.
  emptyColumnHint: (statusName: string) =>
    `«${statusName}» holatidagi vazifalar shu yerda ko'rinadi.`,
  emptyColumnReadOnly: "Hozircha bu holatda vazifa yo'q.",
} as const;

// ---------------------------------------------------------------------------
// LIST — ro'yxat ko'rinishi (jadval sarlavhalari, bo'sh holat)
// ---------------------------------------------------------------------------

export const LIST = {
  emptyTitle: "Hozircha vazifalar yo'q.",
  // Tirnoqlar ATAYLAB tipografik (“ ”) — ekrandagi matn shunday edi.
  emptyHint:
    "Quyidagi holat guruhlaridan birida “+ Vazifa qo'shish” tugmasini bosing.",

  colAssignees: "Mas'ullar",
  colDue: "Muddat",
  colPriority: "Muhimlik",
  colTags: "Teglar",
  groupEmpty: "Vazifalar yo'q",
} as const;

// ---------------------------------------------------------------------------
// ENTITY — daraxt tugunlari (bo'lim / jild / ro'yxat)
// ---------------------------------------------------------------------------

/**
 * Daraxt tugunining turi. ATAYLAB shu yerda takrorlangan, `TreeNodeActions` dan
 * import qilinmagan: lug'at butun ilovaga import qilinadi va komponentga
 * bog'lanib qolsa aylanma import paydo bo'lardi.
 */
type TreeEntityKind = "space" | "folder" | "list";

export const ENTITY_KIND_LABEL: Record<TreeEntityKind, string> = {
  space: "Bo'lim",
  folder: "Jild",
  list: "Ro'yxat",
};

/** `ConfirmDeleteDialog` ga `warning` sifatida uzatiladi — gap davomi. */
export const ENTITY_DELETE_WARNING: Record<TreeEntityKind, string> = {
  space: "ichidagi barcha jildlar, ro'yxatlar va vazifalar bilan birga o'chiriladi.",
  folder: "o'chiriladi.",
  list: "barcha vazifalari va kommentlari bilan birga o'chiriladi.",
};

// ---------------------------------------------------------------------------
// CONFIRM_DELETE — umumiy o'chirish tasdig'i
// ---------------------------------------------------------------------------

export const CONFIRM_DELETE = {
  title: "Rostdan ham o'chirasizmi?",
  irreversible: "Bu amalni ortga qaytarib bo'lmaydi.",
  confirmNameLabel: "Tasdiqlash uchun nomini kiriting:",
  deleting: "O'chirilmoqda…",
} as const;

// ---------------------------------------------------------------------------
// TREE_ACTIONS — yon paneldagi tugun menyusi
// ---------------------------------------------------------------------------

export const TREE_ACTIONS = {
  rename: "Nomini o'zgartirish",
  renameTitle: (kindLabel: string) => `${kindLabel} nomini o'zgartirish`,
  folderStrategyLabel: "Ro'yxatlar bilan nima qilinsin?",
  folderCascade: "Ichidagilari bilan o'chirish",
  folderCascadeDenied: "Buning uchun alohida ruxsat kerak",
  folderDetach: "Ro'yxatlarni bo'limga chiqarish",
} as const;

// ---------------------------------------------------------------------------
// SIDEBAR — ish maydoni yon paneli
// ---------------------------------------------------------------------------

export const SIDEBAR = {
  // Sarlavha ATAYLAB katta harfda — ekranda shunday ko'rinadi.
  spacesHeading: "BO'LIMLAR",
  newSpaceAria: "Yangi bo'lim",
  spacesFailed: "Bo'limlarni yuklab bo'lmadi.",
  spacesEmpty: "Hozircha bo'limlar yo'q.",
  createSpace: COMMON.createSpace,
  createSpaceDenied: "Bo'lim yaratish uchun administratorga murojaat qiling.",
  noLists: "Bu yerda ro'yxatlar yo'q",
  noMembers: "A'zolar yo'q",
} as const;

// ---------------------------------------------------------------------------
// WORKSPACE_CREATE — birinchi ish maydoni kartasi
// ---------------------------------------------------------------------------

export const WORKSPACE_CREATE = {
  title: "Birinchi ish maydoningizni yarating",
  subtitle: "Ish maydonida bo'limlar, ro'yxatlar va vazifalar saqlanadi.",
  creating: "Yaratilmoqda…",
  submit: "Ish maydonini yaratish",
  failed: "Ish maydonini yaratib bo'lmadi.",
} as const;

// ---------------------------------------------------------------------------
// TASK — vazifa paneli va tanlagichlari
// ---------------------------------------------------------------------------

export const TASK = {
  watch: "Kuzatish",
  unwatch: "Kuzatishni to'xtatish",
  tagPlaceholder: "Teg qo'shish…",
  tagsEmpty: "Bu ish maydonida teglar yo'q.",
  /** `ConfirmDeleteDialog` ga `warning` sifatida uzatiladi — gap davomi. */
  deleteWarning: "vazifasi va uning kommentlari o'chiriladi.",
} as const;

// ---------------------------------------------------------------------------
// LANDING_PREVIEW — landing'dagi «skrinshot» qobig'i
// ---------------------------------------------------------------------------
//
// Bu — ilovaning MAKETI, haqiqiy ekran emas: qatorlar `public/showcase/` dan
// keladi, qobiq matni esa shu yerda. Manzil qatoridagi domen ham brend matni,
// haqiqiy manzil emas.

export const LANDING_PREVIEW = {
  addressBar: "uzwork.app",
  spaces: "Bo'limlar",
  addSpace: "Bo'lim qo'shish",
  emptyList: "Ro'yxat hozircha bo'sh — ro'yxatdan o'tib birinchi vazifangizni yarating.",
} as const;

// ---------------------------------------------------------------------------
// PROFILE_SETTINGS — «Sizning sozlamalaringiz»
// ---------------------------------------------------------------------------

export const PROFILE_SETTINGS = {
  title: "Sizning sozlamalaringiz",
  emailReadOnly: "Emailni o'zgartirish MVP versiyasida qo'llab-quvvatlanmaydi.",
  logout: "Chiqish",
  saveFailed: "Profilni saqlab bo'lmadi.",
} as const;

// ---------------------------------------------------------------------------
// PERMISSIONS_MATRIX — rol × huquq jadvali
// ---------------------------------------------------------------------------

export const PERMISSIONS_MATRIX = {
  notFound: "Bunday sahifa topilmadi.",
  loadFailed:
    "Huquqlar matritsasini yuklab bo'lmadi. Sahifani yangilab, qayta urinib ko'ring.",

  heading: "Huquqlar matritsasi",
  // Versiya raqami izohning oxirida turadi — shuning uchun funksiya.
  subtitle: (version: number) =>
    `Har bir rol nima qila olishini shu yerda boshqarasiz. O'zgarishlar darhol kuchga kiradi. Versiya: ${version}`,

  resetMenu: "Standartga qaytarish",
  resetRole: (roleLabel: string) => `${roleLabel} rolini qaytarish`,
  resetEveryRole: "Barcha rollarni qaytarish",
  saveWithCount: (count: number) => `Saqlash (${count})`,

  ownerLockTooltip: "Egasidan huquqlarni olib bo'lmaydi",
  changedInGroup: (count: number) => `${count} o'zgartirilgan`,
  colPermission: "Huquq",

  sensitiveLabel: "Xavfli huquq",
  sensitiveTooltip: "Xavfli huquq — qaytarib bo'lmaydigan oqibatlarga olib kelishi mumkin.",
  ownerOnlyLabel: "Faqat egasi uchun",
  ownerOnlyTooltip: "Bu huquq faqat egasida bo'ladi — boshqa rolga berib bo'lmaydi.",

  dirtyDot: "Saqlanmagan o'zgarish",
  changedDot: "O'zgartirilgan",
  changedDotTitle: "O'zgartirilgan (standartdan farqli)",

  legendChanged: "Standartdan farq qiladi (o'zgartirilgan)",
  legendOwnerOnly: "Faqat egasi uchun / qulflangan",

  resetTitle: "Standart huquqlarni tiklaysizmi?",
  resetTargetAll: "barcha rollar",
  resetTargetRole: (roleLabel: string) => `«${roleLabel}» roli`,
  // Boshi qalin `<span>` bilan ajratilgani uchun gap ikki bo'lak.
  resetDescription:
    "uchun barcha qo'lda kiritilgan o'zgarishlar bekor qilinadi va standart holat qaytariladi. Bu amal darhol kuchga kiradi.",
  resetting: "Tiklanmoqda…",
  resetConfirm: "Standartga qaytarish",
} as const;

// ---------------------------------------------------------------------------
// AI_ASSISTANT — «AI yordamchi» savol-javobi
// ---------------------------------------------------------------------------
//
// Javob matnlari ham shu yerda: ular ekranga chiqadi. `Intent.keywords`
// esa komponentda qoladi — u erkin matnni niyatga bog'laydigan QIDIRUV
// tokeni, foydalanuvchi uni hech qachon ko'rmaydi.

export const AI_ASSISTANT = {
  title: "AI yordamchi",
  description:
    "Javoblar ish maydonining o'z ma'lumotidan hisoblanadi — tashqi model chaqirilmaydi va ma'lumot tashqariga chiqmaydi.",
  inputPlaceholder: (firstName: string) => `${firstName}, nimani bilmoqchisiz?`,
  inputPlaceholderAnon: "Savolingizni yozing…",
  inputAria: "Savol",
  submit: "So'rash",
  idleTitle: "Savol bering yoki tayyorlaridan tanlang.",
  idleHint:
    "Masalan: «Muddati o'tgan vazifalar» yoki vazifa nomidan bir bo'lak — u bo'yicha qidiriladi.",

  promptMine: "Menga nima biriktirilgan?",
  promptOverdue: "Muddati o'tgan vazifalar",
  promptToday: "Bugun nima qilish kerak?",
  promptTeam: "Kim nima ustida ishlayapti?",
  promptSpaces: "Bo'limlar holati qanday?",

  taskCount: (count: number) => `${count} ta vazifa`,
  mineEmpty: "Sizga biriktirilgan ochiq vazifa yo'q.",
  mineText: (tasksLabel: string) => `Sizda ${tasksLabel} ochiq. Eng yaqin muddatlilari:`,
  mineOverdueDetail: (count: number) => `Shundan ${count} tasining muddati o'tgan.`,

  overdueEmpty: "Muddati o'tgan vazifa yo'q — hammasi jadval bo'yicha.",
  overdueText: (tasksLabel: string) => `Muddati o'tgan ${tasksLabel}:`,
  overdueScopeAll: "Butun ish maydoni bo'yicha (sizga ko'rinadigan bo'limlarda).",
  overdueScopeMine: "Faqat sizga biriktirilganlar bo'yicha.",

  todayEmpty: "Bugunga rejalashtirilgan vazifangiz yo'q.",
  todayText: (tasksLabel: string) =>
    `Bugun uchun ${tasksLabel} (muddati o'tganlar bilan):`,

  teamDenied: "Jamoa kesimini ko'rish uchun sizda yetarli ruxsat yo'q.",
  teamLine: (name: string, count: number) => `• ${name} — ${count} ta`,
  teamUnassignedLine: (count: number) => `• Biriktirilmagan — ${count} ta`,
  teamEmpty: "Jamoa a'zolari topilmadi.",
  teamText: "Ochiq vazifalar bo'yicha jamoa yuklamasi:",

  spaceLine: (name: string, open: number) => `• ${name} — ${open} ta ochiq`,
  spacesEmpty: "Hozircha bo'lim yo'q.",
  spacesText: "Bo'limlar bo'yicha ochiq vazifalar:",

  tooShort: "Savolni biroz to'liqroq yozing.",
  searchEmpty: (query: string) =>
    `«${query}» bo'yicha vazifa topilmadi. Quyidagi tayyor savollardan birini tanlang.`,
  searchText: (query: string, tasksLabel: string) =>
    `«${query}» bo'yicha ${tasksLabel} topildi:`,
} as const;

// ---------------------------------------------------------------------------
// DASHBOARD — «Tahlil» ekrani
// ---------------------------------------------------------------------------

export const DASHBOARD = {
  deniedTitle: "Tahlil sizga ochiq emas.",
  deniedHint:
    "Bu sahifa vazifalarni o'qish huquqiga tayanadi. Administratordan so'rang.",

  title: "Tahlil",
  subtitleSuffix: "— umumiy holat",
  /** Hamma vazifa yuklanmaganda sarlavhaga qo'shiladigan bo'lak (bo'sh ham bo'ladi). */
  partialSuffix: " (yuklangan vazifalar bo'yicha)",
  loadFailed: "Ma'lumotni yuklab bo'lmadi.",
  panelEmpty: "Ma'lumot yo'q.",

  statOpen: "Ochiq vazifalar",
  statOverdue: "Muddati o'tgan",
  statCompleted: "Bajarilgan",
  statMembers: "Jamoa a'zolari",

  panelStatus: "Status bo'yicha",
  panelPriority: "Muhimlik bo'yicha",
  panelSpaces: "Bo'limlar bo'yicha",
  panelTeam: "Jamoa yuklamasi",
} as const;

// ---------------------------------------------------------------------------
// PLANNER — «Rejalar» (14 kunlik oyna)
// ---------------------------------------------------------------------------

export const PLANNER = {
  title: "Rejalar",
  subtitle: "Sizga biriktirilgan ochiq vazifalar — muddati bo'yicha.",
  daysAria: "Kunlar tasmasi",
  allDates: "Barcha muddatlar",
  dayEmpty: "Bu kunga rejalashtirilgan vazifa yo'q.",
  emptyTitle: "Rejalashtiriladigan vazifa yo'q.",
  emptyHint:
    "O'zingizga vazifa biriktiring va unga muddat qo'ying — u shu yerdagi kunlar tasmasida paydo bo'ladi.",
} as const;

// ---------------------------------------------------------------------------
// WORKSPACE_HOME — ish maydonining bosh ekrani
// ---------------------------------------------------------------------------

export const WORKSPACE_HOME = {
  loadFailed: "Ish maydonini yuklab bo'lmadi.",
  greeting: (firstName: string) => `Salom, ${firstName}!`,
  greetingAnon: "Salom!",
  subtitleSuffix: "— kunlik ko'rinish",

  myTasksFailed: "Vazifalaringizni yuklab bo'lmadi.",
  myTasksEmptyTitle: "Sizga biriktirilgan ochiq vazifa yo'q.",
  myTasksEmptyHint:
    "Ro'yxatdan o'zingizga vazifa biriktiring — u shu yerda darhol paydo bo'ladi.",
  showTeamTasks: "Jamoa vazifalarini ko'rish",

  teamTasksFailed: "Jamoa vazifalarini yuklab bo'lmadi.",
  teamTasksEmptyTitle: "Ish maydonida hali vazifa yo'q — birinchisini yarating.",
  teamTasksEmptyHint:
    "Vazifa yaratilgach, u kim bajarayotganiga qarab shu yerda guruhlanadi.",
  createFirstTask: "Birinchi vazifani yaratish",
  showMyTasks: "Mening vazifalarim",
  memberEmpty: "Bu a'zoga biriktirilgan ochiq vazifa yo'q.",
  clearFilter: "Filtrni tozalash",

  membersFailed: "Jamoa a'zolarini yuklab bo'lmadi.",

  emptyTitle: "Ish maydoningizga xush kelibsiz",
  emptyHint:
    "Vazifa qo'shishni boshlash uchun yon paneldan bo'lim va ro'yxat yarating.",
  createList: COMMON.createList,
  createSpace: COMMON.createSpace,
} as const;

// ---------------------------------------------------------------------------
// MEMBER_PROFILE — a'zo profili va uning faoliyat tasmasi
// ---------------------------------------------------------------------------

export const MEMBER_PROFILE = {
  tabTasks: "Vazifalar",
  tabActivity: "Faoliyat",
  tabSpaces: "Bo'limlar",
  joinedLabel: "Qo'shilgan:",
  feedTruncated: (shown: number, total: number) =>
    `Oxirgi ${shown} ta yozuv ko'rsatildi (jami ${total} ta).`,
} as const;

/**
 * Faoliyat tasmasidagi gaplar. Bo'laklarga bo'lingan, chunki qiymat (status,
 * ism, fayl nomi) gapning O'RTASIDA qalin `<strong>` bilan chiziladi — bitta
 * satr bilan buni ifodalab bo'lmaydi.
 */
export const ACTIVITY = {
  created: "vazifasini yaratdi",
  statusChangedPrefix: "vazifasini",
  statusChangedSuffix: "ga o'tkazdi",
  completed: "vazifasini bajardi",
  assigneeAddedPrefix: "vazifasini",
  assigneeAddedSuffix: "ga biriktirdi",
  assigneeRemovedPrefix: "vazifasidan",
  assigneeRemovedSuffix: "ni olib tashladi",
  priorityChangedPrefix: "muhimligini",
  priorityChangedSuffix: "qildi",
  dueChangedPrefix: "muddatini",
  dueChangedSuffix: "ga o'zgartirdi",
  renamed: "vazifasining nomini o'zgartirdi",
  renamedFrom: (previous: string) => ` (avval «${previous}»)`,
  movedPrefix: "vazifasini",
  movedSuffix: "ro'yxatiga ko'chirdi",
  deleted: "vazifasini o'chirdi",
  attachmentAddedPrefix: "vazifasiga",
  attachmentAddedSuffix: "faylini biriktirdi",
  attachmentRemovedPrefix: "vazifasidan",
  attachmentRemovedSuffix: "faylini o'chirdi",
  restored: "vazifasini tikladi",
  updated: "vazifasini yangiladi",
} as const;

// ---------------------------------------------------------------------------
// ROLLAR VA KASBLAR — domen yorliqlari
// ---------------------------------------------------------------------------
//
// Bular ilgari `lib/roles.ts` da edi. Yorliq — matn, ya'ni uning joyi shu
// yerda; `lib/roles.ts` da faqat TARTIB (`ROLE_RANK`, `ROLE_COLUMNS`) qoldi.
// API har doim inglizcha qiymat yuboradi va qabul qiladi — bu faqat ko'rsatish.

export const ROLE_LABEL: Record<Role, string> = {
  owner: "Egasi",
  admin: "Admin",
  member: "A'zo",
  guest: "Mehmon",
};

/**
 * Kasb roli yorliqlari. DIQQAT: bu RUXSAT ROLI EMAS — `ROLE_LABEL` bilan
 * aralashtirmang. `profession` hech qanday vakolat bermaydi, u faqat profil
 * ma'lumoti (PM loyihaga mos odam tanlashi uchun).
 */
export const PROFESSION_LABEL: Record<Exclude<Profession, "">, string> = {
  project_manager: "Loyiha menejeri",
  developer: "Dasturchi",
  designer: "Dizayner",
  qa: "Tester",
  analyst: "Analitik",
  marketing: "Marketolog",
  other: "Boshqa",
};

/** Select uchun tartib — ro'yxatdan o'tish formasidagi ketma-ketlik. */
export const PROFESSION_OPTIONS = Object.entries(PROFESSION_LABEL) as [
  Exclude<Profession, "">,
  string,
][];

/** `SpaceMember.access` yorliqlari (DESIGN_PERMISSIONS §E.1). */
export const SPACE_ACCESS_LABEL: Record<SpaceAccess, string> = {
  viewer: "Ko'ruvchi",
  contributor: "Ishtirokchi",
  manager: "Menejer (PM)",
};

/**
 * Ruxsat katalogi guruhlarining yorliqlari. API guruh bilan birga tarjima
 * qilingan `label` ni ham qaytaradi; bu — oflayn zaxira va katalog hali
 * yuklanmaganda guruh tartibini barqaror ushlab turadi.
 */
export const PERMISSION_GROUP_LABEL: Record<PermissionGroupKey, string> = {
  workspace: "Ish maydoni",
  member: "A'zolar",
  space: "Bo'limlar",
  folder: "Jildlar",
  list: "Ro'yxatlar",
  task: "Vazifalar",
  comment: "Izohlar",
  attachment: "Biriktirmalar",
  tag: "Teglar",
};

// ---------------------------------------------------------------------------
// MUTATIONS — yozish amallarining toast xabarlari
// ---------------------------------------------------------------------------
//
// Bular `hooks/mutations.ts` dan keladi. Lint qoidasi ularni KO'RMAYDI (u
// faqat JSX matnini tekshiradi), lekin foydalanuvchi ularni ekranda o'qiydi,
// shuning uchun joyi shu yerda.

export const MUTATIONS = {
  errPermissionDenied: COMMON.errPermissionDenied,
  errNotFound: "Topilmadi — u allaqachon o'chirilgan bo'lishi mumkin.",
  errUploadThrottled: "Juda ko'p fayl yuklandi. Biroz kutib, qayta urinib ko'ring.",
  errUploadNetwork: "Tarmoq xatosi — faylni yuklab bo'lmadi. Aloqani tekshiring.",

  taskDeleted: "Vazifa o'chirildi",
  fileDeleted: "Fayl o'chirildi",
  workspaceUpdated: "Ish maydoni yangilandi",

  memberRemoved: "A'zo chiqarildi",
  // `name` ATAYLAB `string | null`: chaqiruvchi `full_name || email` beradi va
  // mehmonda ikkalasi ham bo'sh bo'lishi mumkin. Avval bu satr shablon ichida
  // interpolatsiya qilinardi, ya'ni xulq-atvor aynan shunday edi — ko'chirish
  // bosqichida uni o'zgartirmadik.
  memberAdded: (name: string | null) => `${name} jamoaga qo'shildi`,
  errAlreadyInTeam: "Bu foydalanuvchi allaqachon jamoada.",

  invitationSent: "Taklif yuborildi",
  invitationRevoked: "Taklif bekor qilindi",
  invitationResent: "Taklif qayta yuborildi",
  errAlreadyMemberOrInvited: "Bu foydalanuvchi allaqachon a'zo yoki taklifi yuborilgan.",
  errInviteThrottled: "Juda ko'p taklif yuborildi. Biroz kutib, qayta urinib ko'ring.",
  errResendLimit: "Bu taklif uchun yuborish chegarasi tugagan.",

  matrixConflict:
    "Boshqa admin matritsani o'zgartirdi. Eng so'nggi holat qayta yuklandi — o'zgarishlaringizni ko'rib chiqing va qaytadan saqlang.",
  permissionsSaved: "Huquqlar saqlandi",
  permissionsReset: "Standart huquqlar tiklandi",

  renamed: "Nomi o'zgartirildi",
  spaceDeleted: "Bo'lim o'chirildi",
  folderDeleted: "Jild o'chirildi",
  listDeleted: "Ro'yxat o'chirildi",

  errLastManager: "Bu yopiq bo'limning oxirgi menejeri — avval boshqa menejer tayinlang.",
  errAlreadySpaceMember: "Bu foydalanuvchi allaqachon bo'lim a'zosi.",
  spaceMemberAdded: "Bo'limga qo'shildi",
  spaceMemberRemoved: "Bo'limdan olib tashlandi",
  bulkAdded: (count: number) => `${count} ta qo'shildi`,
  bulkRemoved: (count: number) => `${count} ta olib tashlandi`,
  changesSaved: "O'zgarishlar saqlandi",

  channelCreated: "Kanal yaratildi",
  channelJoined: "Kanalga qo'shildingiz",
} as const;

// ---------------------------------------------------------------------------
// CREATE_ENTITY — «Bo'lim / Ro'yxat yaratish» dialogi
// ---------------------------------------------------------------------------

export const CREATE_ENTITY = {
  spaceDescription: "Bo'limlar jildlar va ro'yxatlarni jamlaydi.",
  listDescription: "Ro'yxatlarda vazifalaringiz saqlanadi.",
} as const;

// ---------------------------------------------------------------------------
// SETTINGS_SHELL — sozlamalar qobig'i
// ---------------------------------------------------------------------------

export const SETTINGS_SHELL = {
  navAria: "Sozlamalar bo'limlari",
} as const;
