import { expect, type Browser, type BrowserContext, type Page } from "@playwright/test";

// ---------------------------------------------------------------------------
// Muhit
// ---------------------------------------------------------------------------

/** Frontend manzili — `playwright.config.ts` dagi `baseURL` bilan bir xil. */
export const APP_BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

/**
 * Backend REST bazasi. Frontend `src/lib/env.ts` da xuddi shu standart qiymat
 * ishlatiladi, shuning uchun testlar ham `localhost:8000` ga boradi.
 */
export const API_BASE_URL =
  process.env.E2E_API_BASE_URL ?? "http://localhost:8000/api/v1";

/** Test ma'lumotlarining nomi shu prefiks bilan boshlanadi (tozalash oson). */
export const E2E_PREFIX = "E2E ";

/** `src/stores/auth-store.ts` — sessiya shu kalitda saqlanadi. */
const REFRESH_STORAGE_KEY = "clickish.refresh";

// ---------------------------------------------------------------------------
// Demo hisoblar (backend `seed_demo` buyrug'idan)
// ---------------------------------------------------------------------------

export const DEMO_PASSWORD = "clickish-demo-2026";

export interface DemoUser {
  email: string;
  password: string;
}

export const USERS = {
  demo: { email: "demo@clickish.dev", password: DEMO_PASSWORD },
  aziz: { email: "aziz@clickish.dev", password: DEMO_PASSWORD },
  jasur: { email: "jasur@clickish.dev", password: DEMO_PASSWORD },
  malika: { email: "malika@clickish.dev", password: DEMO_PASSWORD },
  nodira: { email: "nodira@clickish.dev", password: DEMO_PASSWORD },
  /**
   * Faqat o'qish hisobi (`is_readonly=True`). Roli `member`, ya'ni ROL
   * bo'yicha qaraganda yozish huquqi bor ko'rinadi — aynan shu sababdan
   * u UI affordance'lari uchun eng qimmatli sinov sub'ekti: rolga qarab
   * chizilgan interfeys unga yozish tugmalarini ko'rsatib qo'yadi.
   */
  mehmon: { email: "mehmon@clickish.dev", password: DEMO_PASSWORD },
} as const satisfies Record<string, DemoUser>;

// ---------------------------------------------------------------------------
// API turlari (faqat testlarga kerak bo'lgan maydonlar)
// ---------------------------------------------------------------------------

export interface ApiUser {
  id: string;
  email: string;
  full_name: string;
}

export interface AuthSession {
  access: string;
  refresh: string;
  user: ApiUser;
}

export interface ApiWorkspace {
  id: string;
  name: string;
  my_role: string;
}

/** Kontrakt §9: holat — to'rtta qat'iy koddan biri, uuid EMAS. */
export type ApiTaskStatus = "todo" | "in_progress" | "review" | "done";

export interface ApiTask {
  id: string;
  list_id: string;
  title: string;
  status: ApiTaskStatus;
}

interface TreeList {
  id: string;
  name: string;
}

interface TreeSpace {
  id: string;
  name: string;
  lists: TreeList[];
  folders: { id: string; name: string; lists: TreeList[] }[];
}

export interface ApiTree {
  id: string;
  name: string;
  spaces: TreeSpace[];
}

interface Paginated<T> {
  count: number;
  results: T[];
}

// ---------------------------------------------------------------------------
// REST yordamchilari (test ma'lumotini API orqali tayyorlash uchun)
// ---------------------------------------------------------------------------

function apiUrl(path: string, query?: Record<string, string | number>): string {
  const clean = path.replace(/^\/+/, "");
  const withSlash = clean.endsWith("/") ? clean : `${clean}/`;
  const url = new URL(`${API_BASE_URL}/${withSlash}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    url.searchParams.set(key, String(value));
  }
  return url.toString();
}

/**
 * Throttle ishga tushganda beriladigan xabar.
 *
 * Bu yerda ATAYLAB kutilmaydi. Rate limiter'ni uxlab o'tkazish testni
 * sekinlashtiradi va (avvalgi tahrirda shunday bo'lgan) test byudjetidan
 * uzunroq uyquga ketib, sababni yashiradigan timeout'ga olib keladi. Throttle
 * urilishi = konfiguratsiya xatosi, uni darhol aytish kerak.
 *
 * IKKI xil yo'l bor va ikkalasi ham shu yerga keladi:
 *
 *   `auth/login/`   — test jarayoni `fetch` bilan uradi va 429 ni o'zi ko'radi.
 *   `auth/refresh/` — BRAUZER uradi, har to'liq sahifa yuklanishida bir marta
 *                    (`src/app/providers.tsx` → `SessionBootstrap`). 429 kelsa
 *                    ilova sessiyani tozalab `/login` ga otadi, test esa
 *                    "Hisob menyusi ko'rinmadi" deb yiqiladi — sabab butunlay
 *                    yashirin qoladi. `watchThrottling()` aynan shuning uchun.
 */
function throttleAdvice(where: string, detail: string): Error {
  return new Error(
    [
      `Throttled (${where}): ${detail}`,
      "",
      "E2E to'plami cheklovni kutib o'tirmaydi. Backend'ni shunday ishga",
      "tushiring (CI ham xuddi shunday qiladi):",
      "",
      "  AUTH_THROTTLE_RATE=1000/min \\",
      "  AUTH_BURST_THROTTLE_RATE=1000/min \\",
      "  REFRESH_THROTTLE_RATE=1000/min \\",
      "    ../.venv/Scripts/python.exe manage.py runserver",
      "",
      "Uchala kalit ham `config/settings.py` dagi DEFAULT_THROTTLE_RATES",
      "bilan bir xil nomlanadi; standartlari 10/min, 5/min va 30/min.",
      "",
      "Throttle mantig'ining o'zi backend testlarida tekshiriladi",
      "(apps/accounts) — uni E2E'da qayta tekshirish shart emas.",
    ].join("\n"),
  );
}

// ---------------------------------------------------------------------------
// Brauzerdagi 429 larni kuzatish
// ---------------------------------------------------------------------------

/** Sahifada ko'rilgan `auth/*` 429 lari. WeakMap — Page bilan birga yo'qoladi. */
const seenAuthThrottles = new WeakMap<Page, Set<string>>();

/**
 * Sahifadagi `auth/*` 429 javoblarini yozib boradi.
 *
 * Bularsiz `auth/refresh/` throttle'i oddiy "element ko'rinmadi" timeout'i
 * bo'lib chiqadi va sababini bilish uchun trace ochib tarmoq panelini
 * varaqlash kerak bo'ladi. `signIn()` va `signedInContext()` buni o'zi ulaydi.
 */
export function watchThrottling(page: Page): void {
  if (seenAuthThrottles.has(page)) return;
  const seen = new Set<string>();
  seenAuthThrottles.set(page, seen);
  page.on("response", (res) => {
    if (res.status() !== 429) return;
    try {
      const { pathname } = new URL(res.url());
      if (pathname.includes("/auth/")) seen.add(pathname);
    } catch {
      // URL emas — e'tiborsiz.
    }
  });
}

/** Shu sahifada `auth/*` 429 ko'rilgan bo'lsa tushunarli xato, aks holda null. */
function throttleErrorFor(page: Page): Error | null {
  const seen = seenAuthThrottles.get(page);
  if (!seen || seen.size === 0) return null;
  return throttleAdvice("brauzer", `429 ← ${[...seen].join(", ")}`);
}

/**
 * REST orqali kirish. Brauzersiz — `fetch` bilan token juftligini oladi.
 *
 * Har chaqiruv **yangi** sessiya yaratadi. Keshlash `sessionFor()` da; brauzer
 * uchun esa har doim yangisi kerak (pastdagi `signIn` izohiga qarang).
 */
export async function apiLogin(
  email: string,
  password: string,
): Promise<AuthSession> {
  const res = await fetch(apiUrl("auth/login/"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (res.ok) return (await res.json()) as AuthSession;

  const text = await res.text();
  if (res.status === 429) {
    throw throttleAdvice(`auth/login/ ${email}`, text.slice(0, 200));
  }
  throw new Error(`apiLogin(${email}) muvaffaqiyatsiz: ${res.status} ${text}`);
}

/**
 * REST chaqiruvlari uchun sessiya — worker jarayonida keshlanadi, ya'ni bitta
 * run davomida har bir hisob uchun **bitta** `auth/login/` so'rovi ketadi.
 *
 * Bu sessiyaning `refresh` tokeni brauzerga BERILMAYDI: SimpleJWT
 * (`ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`) tokenni birinchi
 * ishlatilishida almashtirib eskisini qora ro'yxatga qo'yadi, shuning uchun
 * bitta refresh token faqat bitta iste'molchiga yetadi.
 */
const sessionCache = new Map<string, AuthSession>();

export async function sessionFor(user: DemoUser): Promise<AuthSession> {
  const cached = sessionCache.get(user.email);
  if (cached) return cached;
  const session = await apiLogin(user.email, user.password);
  sessionCache.set(user.email, session);
  return session;
}

/** Autentifikatsiyalangan REST so'rovi. `204` da `undefined` qaytadi. */
export async function apiRequest<T>(
  token: string,
  path: string,
  init: {
    method?: string;
    body?: unknown;
    query?: Record<string, string | number>;
  } = {},
): Promise<T> {
  const { method = "GET", body, query } = init;
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  // Frontend ham har bir mutatsiyada shu sarlavhani yuboradi; test aktori
  // brauzerdan farqli client id bilan yozadi, shunda WS echo bostirilmaydi.
  if (method !== "GET") headers["X-Client-Id"] = "e2e-rest-client";

  const res = await fetch(apiUrl(path, query), {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`${method} ${path} → ${res.status} ${await res.text()}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Foydalanuvchining birinchi ish maydoni. */
export async function firstWorkspace(token: string): Promise<ApiWorkspace> {
  const page = await apiRequest<Paginated<ApiWorkspace>>(token, "workspaces/");
  const workspace = page.results[0];
  if (!workspace) throw new Error("Ish maydoni topilmadi — `seed_demo` bajarilganmi?");
  return workspace;
}

/** Daraxtdagi birinchi ro'yxat (avval jildlardagi, keyin bo'lim ostidagilar). */
export async function firstListId(
  token: string,
  workspaceId: string,
): Promise<string> {
  const tree = await apiRequest<ApiTree>(token, `workspaces/${workspaceId}/tree/`);
  for (const space of tree.spaces) {
    for (const folder of space.folders) {
      if (folder.lists[0]) return folder.lists[0].id;
    }
    if (space.lists[0]) return space.lists[0].id;
  }
  throw new Error("Ro'yxat topilmadi — `seed_demo` bajarilganmi?");
}

/**
 * API orqali vazifa yaratadi. Nomi avtomatik `E2E ` prefiksini oladi.
 *
 * `extra` ga holat berish kerak bo'lsa — `{ status: "in_progress" }`, ya'ni
 * KOD; uuid qabul qiluvchi eski maydon endi yo'q. Berilmasa server `todo`
 * qo'yadi.
 */
export async function createTask(
  token: string,
  listId: string,
  title: string,
  extra: Record<string, unknown> = {},
): Promise<ApiTask> {
  return apiRequest<ApiTask>(token, `lists/${listId}/tasks/`, {
    method: "POST",
    body: { title: title.startsWith(E2E_PREFIX) ? title : `${E2E_PREFIX}${title}`, ...extra },
  });
}

/** Vazifani o'chirish (soft delete). Xatoni YUTMAYDI. */
export async function deleteTask(token: string, taskId: string): Promise<void> {
  await apiRequest(token, `tasks/${taskId}/`, { method: "DELETE" });
}

/**
 * `finally` blokidagi tozalash.
 *
 * `finally` ichidan otilgan xato testning HAQIQIY xatosini bosib ketadi,
 * shuning uchun bu yerda qayta otilmaydi — lekin jimgina ham yutilmaydi:
 * xabar konsolga chiqadi va `global-teardown.ts` `E2E ` prefiksli qolgan
 * vazifalarni supurib, biror nima qolib ketgan bo'lsa **runni yiqitadi**.
 */
export async function deleteTaskAfterTest(token: string, taskId: string): Promise<void> {
  try {
    await deleteTask(token, taskId);
  } catch (err) {
    console.error(
      `[e2e cleanup] tasks/${taskId}/ o'chmadi: ${(err as Error).message}\n` +
        "  → global-teardown bu vazifani supurishga urinadi va uddalay olmasa run yiqiladi.",
    );
  }
}

/** Har bir testga noyob nom (testlar bir-biriga bog'liq bo'lmasligi uchun). */
export function uniqueTitle(label: string): string {
  return `${E2E_PREFIX}${label} ${Date.now()}-${Math.floor(Math.random() * 10_000)}`;
}

// ---------------------------------------------------------------------------
// Huquqlar matritsasi (permissions.spec.ts + global-teardown.ts)
// ---------------------------------------------------------------------------

/**
 * Rol-huquq matritsasini standart holatga qaytaradi. Xatoni YUTMAYDI —
 * yutilgan reset demo ish maydonini butun run davomida (va keyin ham)
 * o'zgargan holda qoldiradi, keyingi spec'lar esa buni sababsiz qizil
 * natijada ko'radi.
 */
export async function resetRolePermissions(
  token: string,
  workspaceId: string,
): Promise<void> {
  await apiRequest<void>(token, `workspaces/${workspaceId}/role-permissions/reset/`, {
    method: "POST",
    body: { role: null },
  });
}

// ---------------------------------------------------------------------------
// Sessiyani brauzerga berish (login formasidan o'tmasdan)
// ---------------------------------------------------------------------------

/**
 * `storageState` — `clickish.refresh` kaliti bilan.
 *
 * Ilova yuklanganda `src/app/providers.tsx` dagi `SessionBootstrap` shu
 * tokenni o'qib `auth/refresh/` ga boradi va sessiyani tiklaydi. `auth/refresh/`
 * throttle qilinmagan (`apps/accounts/views.py:RefreshView`), demak bu yo'l
 * rate limiter'ga umuman tegmaydi.
 */
export function storageStateFor(session: AuthSession) {
  return {
    cookies: [],
    origins: [
      {
        origin: new URL(APP_BASE_URL).origin,
        localStorage: [{ name: REFRESH_STORAGE_KEY, value: session.refresh }],
      },
    ],
  };
}

/**
 * Autentifikatsiya qilingan brauzer konteksti — login formasisiz.
 *
 * NEGA forma emas: login formasi orqali kirish sahifa yuklash + hidratsiya +
 * throttle degani va u testning aynan tekshirmoqchi bo'lgan narsasi EMAS
 * (login formasining o'zi `auth.spec.ts` da tekshiriladi). Bu yerda esa
 * sessiya REST orqali olinadi va `localStorage` ga qo'yiladi — deterministik
 * va bir necha barobar tez.
 *
 * Har kontekstga YANGI sessiya: refresh token birinchi ishlatilishida
 * rotatsiya qilinib eskisi blacklist'ga tushadi, ya'ni bitta tokenni ikkita
 * kontekst bo'lisha olmaydi.
 */
export async function signedInContext(
  browser: Browser,
  user: DemoUser,
): Promise<{ context: BrowserContext; page: Page; session: AuthSession }> {
  const session = await apiLogin(user.email, user.password);
  const context = await browser.newContext({ storageState: storageStateFor(session) });
  const page = await context.newPage();
  watchThrottling(page);
  return { context, page, session };
}

/**
 * Mavjud sahifani (masalan Playwright bergan `page` fixture'ini) login
 * formasidan o'tmasdan autentifikatsiya qiladi.
 *
 * `localStorage` origin'ga bog'langan, shuning uchun avval ilova origin'i
 * yuklanishi kerak — buning uchun eng arzoni `/login`.
 */
export async function signIn(page: Page, user: DemoUser): Promise<AuthSession> {
  watchThrottling(page);
  const session = await apiLogin(user.email, user.password);

  // Token har qanday sahifa skriptidan OLDIN joyiga qo'yiladi.
  //
  // Ilgari bu yerda `page.goto("/login")` + `page.evaluate(setItem)` turardi
  // va u poygaga olib kelardi: `goto` "load" da qaytadi, `SessionBootstrap`
  // effekti esa hidratsiyadan KEYIN ishlaydi — ya'ni tokenni biz yozib
  // bo'lganimizdan keyin. O'sha bootstrap uni ishlatib yuboradi, refresh
  // token esa birinchi ishlatilishida rotatsiya qilinib eskisi blacklist'ga
  // tushadi. Keyingi navigatsiya endi YAROQSIZ token bilan borib `401`
  // olardi, sessiya tozalanardi va test login sahifasida tugardi.
  //
  // `addInitScript` skriptni har navigatsiyada hujjat skriptlaridan oldin
  // bajaradi, shuning uchun "bor bo'lsa tegma" sharti SHART: aks holda u
  // har yuklanishda allaqachon rotatsiya qilingan tokenni eskisi bilan
  // qayta yozib, xuddi shu xatoni qaytarardi.
  await page.context().addInitScript(
    ([key, value]) => {
      if (!window.localStorage.getItem(key)) window.localStorage.setItem(key, value);
    },
    [REFRESH_STORAGE_KEY, session.refresh] as const,
  );

  const appOrigin = new URL(APP_BASE_URL).origin;
  let current: string | null = null;
  try {
    current = new URL(page.url()).origin;
  } catch {
    current = null; // about:blank
  }
  // Origin hali ochilmagan bo'lsa `addInitScript` ishlashi uchun bir marta
  // yuklaymiz; ochiq bo'lsa `localStorage` ni to'g'ridan-to'g'ri urug'lantiramiz.
  if (current !== appOrigin) {
    await page.goto("/login");
  } else {
    await page.evaluate(
      ([key, value]) => {
        if (!window.localStorage.getItem(key)) window.localStorage.setItem(key, value);
      },
      [REFRESH_STORAGE_KEY, session.refresh] as const,
    );
  }
  return session;
}

// ---------------------------------------------------------------------------
// UI orqali kirish (FAQAT login formasining o'zini tekshiradigan testlar uchun)
// ---------------------------------------------------------------------------

/**
 * React hidratsiyasi tugaganini kutadi.
 *
 * React hidratsiya paytida DOM tuguniga `__reactFiber$<hash>` xususiyatini
 * o'rnatadi — u paydo bo'lgani "bu element endi React nazoratida" degani.
 * Shu sababli hidratsiyadan oldin yozilgan qiymatni React tozalab yuborishi
 * mumkin bo'lgan poyga yo'q bo'ladi: avvalgi tahrirdagi "8 marta yozib ko'r,
 * orasida 200 ms kut" sikli aynan shu poygani yashirar edi.
 */
export async function waitForHydration(page: Page, selector: string): Promise<void> {
  await page.waitForFunction(
    (sel) => {
      const el = document.querySelector(sel);
      if (!el) return false;
      return Object.keys(el).some((key) => key.startsWith("__reactFiber$"));
    },
    selector,
    { timeout: 20_000 },
  );
}

/** Hidratsiyadan keyin yozadi va qiymat o'rnida qolganini tasdiqlaydi. */
export async function fillHydrated(
  page: Page,
  selector: string,
  value: string,
): Promise<void> {
  await waitForHydration(page, selector);
  await page.fill(selector, value);
  await expect(page.locator(selector)).toHaveValue(value);
}

/** Login formasi to'liq tayyor (hidratsiya tugagan). */
export async function gotoLoginForm(page: Page): Promise<void> {
  await page.goto("/login");
  await expect(page.locator("form")).toBeVisible();
  await waitForHydration(page, "#email");
}

/**
 * Login formasi orqali kirish — HAQIQIY forma yo'li.
 *
 * Faqat login oqimining o'zini tekshiradigan testlar uchun. Boshqa hamma joyda
 * `signIn()` / `signedInContext()` ishlating: ular tezroq va throttle'ga
 * tegmaydi.
 */
export async function login(page: Page, user: DemoUser): Promise<void> {
  await gotoLoginForm(page);
  await fillHydrated(page, "#email", user.email);
  await fillHydrated(page, "#password", user.password);

  // `exact` bo'lmasa "Demo rejimda kirish" tugmasi ham mos keladi.
  await page.getByRole("button", { name: "Kirish", exact: true }).click();

  const left = await page
    .waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20_000 })
    .then(() => true)
    .catch(() => false);
  if (left) return;

  // Sahifadagi boshqa `role="alert"` elementlari aralashmasin —
  // shuning uchun aynan formadagi banner o'qiladi.
  const banner = await page
    .locator('form p[role="alert"]')
    .first()
    .textContent()
    .catch(() => null);
  if (banner?.includes("Urinishlar juda ko'p")) {
    throw throttleAdvice(
      `auth/login/ ${user.email}`,
      "forma banneri: Urinishlar juda ko'p",
    );
  }
  throw new Error(`login(${user.email}) muvaffaqiyatsiz. Banner: ${banner ?? "yo'q"}`);
}

// ---------------------------------------------------------------------------
// Deterministik kutishlar (`networkidle` o'rniga)
// ---------------------------------------------------------------------------

/**
 * Ilova qobig'i chizilganini kutadi.
 *
 * `waitForLoadState("networkidle")` ATAYLAB ishlatilmaydi: Playwright uni
 * tavsiya qilmaydi va bu sahifalar ochiq WebSocket ushlab turadi — "500 ms
 * jimlik" hech qachon kafolatlanmaydi. Ko'rinadigan element esa aynan
 * testga kerak bo'lgan shart.
 */
export async function waitForAppShell(page: Page): Promise<void> {
  try {
    await expect(page.getByRole("button", { name: "Hisob menyusi" })).toBeVisible({
      timeout: 30_000,
    });
  } catch (err) {
    // Qobiq chizilmasligining eng chalg'ituvchi sababi — `auth/refresh/` ga
    // kelgan 429: ilova sessiyani tozalab `/login` ga otadi va bu yerda
    // shunchaki "element ko'rinmadi" bo'lib ko'rinadi. Ko'rilgan bo'lsa,
    // haqiqiy sabab aytiladi.
    throw throttleErrorFor(page) ?? err;
  }
}

/** Ish maydoni sahifasiga o'tib, qobiq chizilishini kutadi. */
export async function gotoWorkspace(page: Page, workspaceId: string): Promise<void> {
  await page.goto(`/w/${workspaceId}`);
  await waitForAppShell(page);
}

/**
 * Yon paneldagi birinchi ro'yxatni bosib ochadi va uning id sini qaytaradi.
 * `/w/{workspaceId}` sahifasida bo'lish shart emas — kerak bo'lsa o'zi o'tadi.
 */
export async function gotoFirstList(page: Page, workspaceId: string): Promise<string> {
  if (!page.url().includes(`/w/${workspaceId}`)) {
    await page.goto(`/w/${workspaceId}`);
  }
  const listLink = page
    .locator(`aside a[href^="/w/${workspaceId}/l/"]`)
    .first();
  await expect(listLink).toBeVisible({ timeout: 20_000 });

  const href = await listLink.getAttribute("href");
  const listId = href?.split("/l/")[1]?.split("?")[0];
  if (!listId) throw new Error("Yon panelda ro'yxat havolasi topilmadi.");

  await listLink.click();
  await page.waitForURL(new RegExp(`/w/${workspaceId}/l/${listId}`));
  return listId;
}

// ---------------------------------------------------------------------------
// Konsol / sahifa xatolarini yig'ish (smoke testlar uchun)
// ---------------------------------------------------------------------------

export interface PageErrorCollector {
  errors: string[];
  reset: () => void;
}

/** `pageerror` va `console.error` xabarlarini yig'adi. */
export function collectPageErrors(page: Page): PageErrorCollector {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(`console.error: ${msg.text()}`);
  });
  return { errors, reset: () => errors.splice(0, errors.length) };
}
