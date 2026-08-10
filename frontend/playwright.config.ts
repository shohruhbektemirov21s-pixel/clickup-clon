import { defineConfig, devices } from "@playwright/test";

/**
 * E2E konfiguratsiyasi.
 *
 * `webServer` ATAYLAB yo'q: backend (`http://127.0.0.1:8000`) ham, frontend
 * (`http://localhost:3000`) ham ishlab turgan holda test qilinadi. Serverlarni
 * Playwright ko'tarmaydi — `e2e/README.md` ga qarang.
 */
export default defineConfig({
  testDir: "./e2e",
  // Realtime testlari ikkita brauzer kontekstini teng ushlab turadi — parallel
  // ishga tushirish presence hisoblagichini buzadi, shuning uchun fayl ichida
  // ketma-ket.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
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
