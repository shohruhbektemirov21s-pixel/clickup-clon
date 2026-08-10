import { expect, test } from "@playwright/test";
import {
  collectPageErrors,
  firstListId,
  firstWorkspace,
  sessionFor,
  signIn,
  USERS,
  waitForAppShell,
  waitForHydration,
} from "./fixtures";

/**
 * Sahifalar konsol/sahifa xatosisiz yuklanadimi.
 *
 * `waitForLoadState("networkidle")` va `waitForTimeout()` ATAYLAB
 * ishlatilmaydi: ilova qobig'i WebSocket ushlab turadi, ya'ni tarmoq hech
 * qachon "jim" bo'lmaydi, qat'iy uyqu esa sekin mashinada baribir yetmaydi.
 * O'rniga sahifaning aynan kutilgan holati kutiladi — konsol xatolarining
 * aksariyati hidratsiya paytida tug'ilgani uchun tekshiruv hidratsiyadan
 * KEYIN bajariladi.
 */
test.describe("smoke — sahifalar konsol xatosisiz yuklanadi", () => {
  test("public pages load cleanly", async ({ page }) => {
    const collector = collectPageErrors(page);

    for (const path of ["/login", "/register"]) {
      collector.reset();
      await page.goto(path);

      await expect(page.locator("form")).toBeVisible();
      // Nusxaga bog'lanmagan hidratsiya signali: formaning birinchi inputi
      // React nazoratiga o'tdi.
      await waitForHydration(page, "form input");
      expect(collector.errors, `${path} → konsol/sahifa xatolari`).toEqual([]);
    }
  });

  test("authenticated pages load cleanly", async ({ page }) => {
    // Ilgari bu test `test.setTimeout(240_000)` so'rardi, chunki login
    // formasi throttle back-off'ini kutib o'tirardi. Endi sessiya REST orqali
    // beriladi — kutish yo'q, standart 60 s yetib ortadi.
    const session = await sessionFor(USERS.demo);
    const workspace = await firstWorkspace(session.access);
    const listId = await firstListId(session.access, workspace.id);

    await signIn(page, USERS.demo);

    const collector = collectPageErrors(page);
    const paths = [
      `/w/${workspace.id}`,
      `/w/${workspace.id}/settings`,
      `/w/${workspace.id}/l/${listId}`,
    ];

    for (const path of paths) {
      collector.reset();
      await page.goto(path);

      await waitForAppShell(page);
      expect(collector.errors, `${path} → konsol/sahifa xatolari`).toEqual([]);
    }
  });
});
