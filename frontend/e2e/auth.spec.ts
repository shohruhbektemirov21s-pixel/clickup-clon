import { expect, test } from "@playwright/test";
import {
  firstWorkspace,
  fillHydrated,
  gotoLoginForm,
  login,
  sessionFor,
  signIn,
  USERS,
  waitForAppShell,
} from "./fixtures";

/**
 * Login oqimi.
 *
 * Bu — HAQIQIY login formasini bosib o'tadigan YAGONA fayl. Qolgan hamma
 * spec `signIn()` orqali sessiyani REST bilan oladi, shuning uchun bu yerda
 * `auth/login/` throttle chelagiga deyarli bosim yo'q va hech qayerda
 * back-off kutilmaydi (`fixtures.ts` → `throttleAdvice` izohiga qarang).
 */
test.describe("authentication", () => {
  test("logs in with valid credentials and lands in a workspace", async ({ page }) => {
    const session = await sessionFor(USERS.demo);
    const workspace = await firstWorkspace(session.access);

    await login(page, USERS.demo);

    await expect(page).toHaveURL(new RegExp(`/w/${workspace.id}`));
    // Ish maydoni qobig'i yuklandi: yon panel va hisob menyusi joyida.
    await waitForAppShell(page);
    await expect(page.locator("aside")).toBeVisible();
  });

  test("shows an error and stays on /login for a wrong password", async ({ page }) => {
    await gotoLoginForm(page);
    await fillHydrated(page, "#email", USERS.jasur.email);
    await fillHydrated(page, "#password", "definitely-not-the-password");

    // `exact` bo'lmasa "Demo rejimda kirish" tugmasi ham mos keladi.
    await page.getByRole("button", { name: "Kirish", exact: true }).click();

    // Next.js o'zining `__next-route-announcer__` elementiga ham role="alert"
    // beradi — shuning uchun aynan formadagi banner tanlanadi.
    const alert = page.locator('form p[role="alert"]');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("Bunday email va parolga ega faol hisob topilmadi.");
    await expect(page).toHaveURL(/\/login/);
  });

  /**
   * Hisob menyusi bir vaqtlar `Base UI: MenuGroupContext is missing` bilan
   * yiqilardi. Tuzatildi: `src/components/ui/dropdown-menu.tsx` dagi
   * `DropdownMenuLabel` endi o'z `Menu.Group`ini olib yuradi va `top-bar.tsx`
   * guruh ichida `DropdownMenuGroupLabel` ishlatadi. Bu test o'sha
   * regressiyaning qorovuli — YASHIL bo'lishi kutiladi.
   */
  test("logs out and returns to /login", async ({ page }) => {
    // Chiqish tekshirilyapti, kirish emas — sessiya REST orqali beriladi.
    await signIn(page, USERS.malika);
    await page.goto("/");
    await waitForAppShell(page);

    await page.getByRole("button", { name: "Hisob menyusi" }).click();
    await page.getByRole("menuitem", { name: "Chiqish" }).click();

    await page.waitForURL(/\/login/);
    await expect(page.locator("#email")).toBeVisible();
    // Sessiya haqiqatan tozalandi.
    await expect
      .poll(() =>
        page.evaluate(() => window.localStorage.getItem("clickish.refresh")),
      )
      .toBeNull();
  });

  test("redirects an unauthenticated visitor from a protected URL to /login", async ({
    page,
  }) => {
    const session = await sessionFor(USERS.demo);
    const workspace = await firstWorkspace(session.access);
    const target = `/w/${workspace.id}/settings`;

    await page.goto(target);

    await page.waitForURL(/\/login/);
    await expect(page).toHaveURL(new RegExp(`next=${encodeURIComponent(target)}`));
  });
});
