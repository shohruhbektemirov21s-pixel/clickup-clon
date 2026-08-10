import {
  API_BASE_URL,
  APP_BASE_URL,
  USERS,
  apiLogin,
  firstWorkspace,
  resetRolePermissions,
} from "./fixtures";

/**
 * Run boshlanishidan oldingi tekshiruv (`playwright.config.ts` → globalSetup).
 *
 * Maqsad: noto'g'ri muhitni 23 ta chalkash timeout emas, BITTA aniq xabar
 * bilan aytish, va oldingi run yarim yo'lda uzilib qolgan bo'lsa demo ish
 * maydonini toza holatga qaytarish.
 */

const PREFLIGHT_TIMEOUT_MS = 10_000;

async function reachable(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, {
      signal: AbortSignal.timeout(PREFLIGHT_TIMEOUT_MS),
      redirect: "manual",
    });
    // 2xx/3xx/4xx — muhim emas, javob kelgani yetarli. 5xx esa "server bor,
    // lekin ishlamayapti" degani va uni aytib qo'yish kerak.
    return res.status >= 500 ? `HTTP ${res.status}` : null;
  } catch (err) {
    return (err as Error).message;
  }
}

function fail(lines: string[]): never {
  throw new Error(`\n${lines.join("\n")}\n`);
}

export default async function globalSetup(): Promise<void> {
  // --- 1. Serverlar ko'tarilganmi -----------------------------------------
  const [frontendErr, backendErr] = await Promise.all([
    reachable(`${APP_BASE_URL}/login`),
    reachable(`${API_BASE_URL.replace(/\/api\/v1\/?$/, "")}/api/v1/health/`),
  ]);

  if (frontendErr || backendErr) {
    fail([
      "E2E to'plami ishlab turgan stack'ni talab qiladi (Playwright serverlarni",
      "o'zi ko'tarmaydi — sababi `playwright.config.ts` da yozilgan).",
      "",
      ...(backendErr ? [`  ✗ backend  ${API_BASE_URL} → ${backendErr}`] : [`  ✓ backend  ${API_BASE_URL}`]),
      ...(frontendErr ? [`  ✗ frontend ${APP_BASE_URL} → ${frontendErr}`] : [`  ✓ frontend ${APP_BASE_URL}`]),
      "",
      "Ishga tushirish tartibi `frontend/e2e/README.md` da.",
    ]);
  }

  // --- 2. Demo ma'lumot ekilganmi ------------------------------------------
  let access: string;
  try {
    access = (await apiLogin(USERS.demo.email, USERS.demo.password)).access;
  } catch (err) {
    fail([
      `Demo hisobiga (${USERS.demo.email}) kirib bo'lmadi.`,
      "",
      (err as Error).message,
      "",
      "Ekilmagan bo'lsa:  ../.venv/Scripts/python.exe manage.py seed_demo",
    ]);
  }

  const workspace = await firstWorkspace(access);

  // --- 3. Oldingi run qoldirgan o'zgarishlarni qaytarish --------------------
  // `permissions.spec.ts` matritsani ataylab o'zgartiradi. Agar o'sha run
  // yiqilib teardown'gacha yetmagan bo'lsa, ish maydoni o'zgargan holda
  // qoladi va KEYINGI run sababsiz qizil bo'ladi. Shuning uchun har run
  // ma'lum holatdan boshlanadi.
  await resetRolePermissions(access, workspace.id);

  process.stdout.write(
    `[e2e] preflight ok — workspace "${workspace.name}" (${workspace.id}), matritsa standart holatda\n`,
  );
}
