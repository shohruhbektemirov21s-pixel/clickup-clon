import { defineConfig, devices } from "@playwright/test";

/**
 * E2E konfiguratsiyasi.
 *
 * `webServer` ATAYLAB yo'q — serverlarni chaqiruvchi tomon ko'taradi
 * (`.github/workflows/ci.yml` dagi `e2e` job yoki `e2e/README.md` dagi qo'lda
 * ishga tushirish). Sabablari:
 *
 *   1. Backend'ni ko'tarish bitta buyruq emas: `migrate` → `seed_demo` →
 *      Daphne, hammasi Python venv va `DJANGO_SETTINGS_MODULE` bilan.
 *      `webServer` bunday tartibni ifodalay olmaydi.
 *   2. `webServer` jarayonlarini Playwright o'zi o'ldiradi, ya'ni Daphne va
 *      Next loglari yo'qoladi. Workflow'dan ko'tarilganda esa ular faylga
 *      yozilib, yiqilishda **artefakt** sifatida yuklanadi — WS testi
 *      yiqilganda birinchi qaraladigan narsa aynan backend logi.
 *   3. `reuseExistingServer` CI'da va lokalda boshqacha ishlaydi; bu "test
 *      kechagi serverga tegib yashil bo'ldi" turkumidagi xatolarning manbai.
 *
 * Buning evaziga `globalSetup` ikkala serverni tekshiradi va ko'tarilmagan
 * bo'lsa 23 ta timeout emas, bitta aniq xabar beradi.
 */
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  // Realtime testlari ikkita brauzer kontekstini teng ushlab turadi — parallel
  // ishga tushirish presence hisoblagichini buzadi, shuning uchun fayl ichida
  // ketma-ket.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // Login endi forma orqali emas, REST orqali beriladi (`e2e/fixtures.ts` →
  // `signIn`), shuning uchun hech bir test rate limiter'ni uxlab o'tkazmaydi
  // va 60 s hamma narsaga yetadi. Ilgari to'rtta spec 240 s so'rar edi.
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI
    ? [
        ["list"],
        ["html", { open: "never" }],
        ["junit", { outputFile: "playwright-report/junit.xml" }],
        ["github"],
      ]
    : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: process.env.CI ? "retain-on-failure" : "off",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
