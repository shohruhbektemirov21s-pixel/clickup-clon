import { expect, test } from "@playwright/test";
import { firstWorkspace, login, sessionFor, USERS } from "./fixtures";

/**
 * Login endpoint'i cheklangan (email bo'yicha 5/min, IP bo'yicha 10/min),
 * shuning uchun bu faylda har bir test **boshqa** demo hisobidan foydalanadi —
 * shunda bitta email bo'yicha oyna to'lib qolmaydi.
 */
test.describe("authentication", () => {
  test("logs in with valid credentials and lands in a workspace", async ({ page }) => {
    const session = await sessionFor(USERS.demo);
    const workspace = await firstWorkspace(session.access);

    await login(page, USERS.demo);

    await expect(page).toHaveURL(new RegExp(`/w/${workspace.id}`));
    // Ish maydoni qobig'i yuklandi: yon panel va hisob menyusi joyida.
    await expect(page.getByRole("button", { name: "Hisob menyusi" })).toBeVisible();
    await expect(page.locator("aside")).toBeVisible();
  });

  test("shows an error and stays on /login for a wrong password", async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(400);

    await page.fill("#email", USERS.jasur.email);
    await page.fill("#password", "definitely-not-the-password");
    // Hidratsiyadan keyin qiymat saqlanganini tasdiqlaymiz.
    await expect(page.locator("#email")).toHaveValue(USERS.jasur.email);

    await page.getByRole("button", { name: "Kirish" }).click();

    const alert = page.getByRole("alert");
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("Bunday email va parolga ega faol hisob topilmadi.");
    await expect(page).toHaveURL(/\/login/);
  });

  test("logs out and returns to /login", async ({ page }) => {
    await login(page, USERS.malika);

    await page.getByRole("button", { name: "Hisob menyusi" }).click();
    await page.getByRole("menuitem", { name: "Chiqish" }).click();

    await page.waitForURL(/\/login/);
    await expect(page.locator("#email")).toBeVisible();
    // Sessiya haqiqatan tozalandi.
    const refresh = await page.evaluate(() =>
      window.localStorage.getItem("clickish.refresh"),
    );
    expect(refresh).toBeNull();
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
