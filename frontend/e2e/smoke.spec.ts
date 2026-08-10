import { expect, test } from "@playwright/test";
import {
  collectPageErrors,
  firstListId,
  firstWorkspace,
  login,
  sessionFor,
  USERS,
} from "./fixtures";

test.describe("smoke — sahifalar konsol xatosisiz yuklanadi", () => {
  test("public pages load cleanly", async ({ page }) => {
    const collector = collectPageErrors(page);

    for (const path of ["/login", "/register"]) {
      collector.reset();
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(500);

      await expect(page.locator("form")).toBeVisible();
      expect(collector.errors, `${path} → konsol/sahifa xatolari`).toEqual([]);
    }
  });

  test("authenticated pages load cleanly", async ({ page }) => {
    const session = await sessionFor(USERS.demo);
    const workspace = await firstWorkspace(session.access);
    const listId = await firstListId(session.access, workspace.id);

    await login(page, USERS.demo);

    const collector = collectPageErrors(page);
    const paths = [
      `/w/${workspace.id}`,
      `/w/${workspace.id}/settings`,
      `/w/${workspace.id}/l/${listId}`,
    ];

    for (const path of paths) {
      collector.reset();
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(500);

      // Ilova qobig'i chizildi (yon panel + hisob menyusi).
      await expect(page.getByRole("button", { name: "Hisob menyusi" })).toBeVisible();
      expect(collector.errors, `${path} → konsol/sahifa xatolari`).toEqual([]);
    }
  });
});
