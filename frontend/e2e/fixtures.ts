import { expect, type Page } from "@playwright/test";

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

export interface ApiTask {
  id: string;
  list_id: string;
  title: string;
  status_id: string;
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

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * REST orqali kirish. Brauzersiz — `fetch` bilan token oladi, keyin shu token
 * bilan test ma'lumotini tayyorlash mumkin.
 *
 * Backend `auth/login/` ni cheklaydi (email bo'yicha 5/min, IP bo'yicha
 * 10/min), shuning uchun `429` da server aytgan muddat kutilib, bir marta
 * qayta uriniladi. Testlar login so'rovini isrof qilmasligi uchun
 * `sessionFor()` dan foydalaning.
 */
export async function apiLogin(
  email: string,
  password: string,
): Promise<AuthSession> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const res = await fetch(apiUrl("auth/login/"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (res.ok) return (await res.json()) as AuthSession;

    const text = await res.text();
    if (res.status === 429 && attempt === 0) {
      const seconds = Number(/available in (\d+) seconds/.exec(text)?.[1] ?? 60);
      await sleep((seconds + 2) * 1000);
      continue;
    }
    throw new Error(`apiLogin(${email}) muvaffaqiyatsiz: ${res.status} ${text}`);
  }
  throw new Error(`apiLogin(${email}) muvaffaqiyatsiz.`);
}

/**
 * Foydalanuvchi sessiyasi — worker jarayonida keshlanadi, ya'ni bitta run
 * davomida har bir hisob uchun **bitta** `auth/login/` so'rovi ketadi.
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

/** API orqali vazifa yaratadi. Nomi avtomatik `E2E ` prefiksini oladi. */
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

/** Vazifani o'chirish (soft delete). Tozalashda xatolarni yutadi. */
export async function deleteTaskQuietly(token: string, taskId: string): Promise<void> {
  try {
    await apiRequest(token, `tasks/${taskId}/`, { method: "DELETE" });
  } catch {
    // Tozalash — test natijasiga ta'sir qilmasin.
  }
}

/** Har bir testga noyob nom (testlar bir-biriga bog'liq bo'lmasligi uchun). */
export function uniqueTitle(label: string): string {
  return `${E2E_PREFIX}${label} ${Date.now()}-${Math.floor(Math.random() * 10_000)}`;
}

// ---------------------------------------------------------------------------
// UI orqali kirish
// ---------------------------------------------------------------------------

/**
 * Hidratsiyadan oldin yozilgan qiymatni React nazorat qilinadigan input
 * tozalab yuboradi. Shuning uchun qiymat `inputValue()` bilan tasdiqlanadi va
 * kerak bo'lsa qayta yoziladi.
 */
async function fillStable(page: Page, selector: string, value: string): Promise<void> {
  for (let attempt = 0; attempt < 8; attempt += 1) {
    await page.fill(selector, value);
    await page.waitForTimeout(200);
    if ((await page.inputValue(selector)) === value) return;
  }
  throw new Error(`"${selector}" maydoniga qiymat yozilmadi (hidratsiya muammosi).`);
}

/** Login formasini hidratsiya tugagach to'ldirib yuboradi. */
async function submitLoginForm(page: Page, user: DemoUser): Promise<void> {
  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400);

  await fillStable(page, "#email", user.email);
  await fillStable(page, "#password", user.password);

  await page.getByRole("button", { name: "Kirish" }).click();
}

/**
 * Login formasi orqali kirish.
 *
 * Hidratsiya tugashini kutadi (`networkidle` + kichik pauza), maydonlarni
 * to'ldirib qiymatni tasdiqlaydi, so'ng yuboradi. Muvaffaqiyatda `/login` dan
 * chiqib ketiladi.
 *
 * Backend loginni cheklaydi (email bo'yicha 5/min). "Urinishlar juda ko'p"
 * bannerini ko'rsa, oyna bo'shashini kutib bir marta qayta uriniladi.
 */
export async function login(page: Page, user: DemoUser): Promise<void> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await submitLoginForm(page, user);

    const left = await page
      .waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20_000 })
      .then(() => true)
      .catch(() => false);
    if (left) return;

    const banner = await page.getByRole("alert").textContent().catch(() => null);
    if (banner?.includes("Urinishlar juda ko'p") && attempt === 0) {
      await page.waitForTimeout(62_000);
      continue;
    }
    throw new Error(`login(${user.email}) muvaffaqiyatsiz. Banner: ${banner ?? "yo'q"}`);
  }
}

/** Kirgan foydalanuvchining birinchi ish maydoni sahifasini ochadi. */
export async function gotoFirstWorkspace(page: Page, user: DemoUser): Promise<string> {
  const session = await sessionFor(user);
  const workspace = await firstWorkspace(session.access);
  await login(page, user);
  await page.goto(`/w/${workspace.id}`);
  await page.waitForLoadState("networkidle");
  return workspace.id;
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
