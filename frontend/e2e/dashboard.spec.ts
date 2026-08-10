import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import {
  createTask,
  deleteTaskAfterTest,
  firstListId,
  firstWorkspace,
  gotoWorkspace,
  signedInContext,
  uniqueTitle,
  USERS,
  type AuthSession,
} from "./fixtures";

/**
 * Ish maydoni bosh sahifasi (dashboard).
 *
 * Bitta autentifikatsiya qilingan kontekst bo'lishiladi — sessiya REST orqali
 * olinadi (`signedInContext`), login formasi bosilmaydi. Testlar bir-biriga
 * bog'liq emas: har biri o'z sahifasiga o'zi o'tadi va o'z ma'lumotini
 * yaratadi.
 */
let context: BrowserContext;
let page: Page;
let session: AuthSession;
let workspaceId: string;

test.beforeAll(async ({ browser }) => {
  ({ context, page, session } = await signedInContext(browser, USERS.demo));
  workspaceId = (await firstWorkspace(session.access)).id;
});

test.afterAll(async () => {
  await context?.close();
});

async function openDashboard() {
  await gotoWorkspace(page, workspaceId);
}

test.describe("workspace dashboard", () => {
  test("renders the dashboard at /w/{id} without redirecting away", async () => {
    await openDashboard();

    await expect(page).toHaveURL(new RegExp(`/w/${workspaceId}/?$`));
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Salom");
  });

  test("shows the four summary stat cards", async () => {
    await openDashboard();

    const stats = page.locator('section[aria-label="Qisqa statistika"]');
    await expect(stats).toBeVisible();
    for (const label of [
      "Ochiq vazifalar",
      "Muddati o'tgan",
      "Bugun",
      "Jamoa a'zolari",
    ]) {
      await expect(stats.getByText(label, { exact: true })).toBeVisible();
    }
    await expect(stats.locator("> div")).toHaveCount(4);
  });

  test('has a "Mening vazifalarim" section', async () => {
    await openDashboard();

    const myTasks = page.locator('section[aria-label="Mening vazifalarim"]');
    await expect(myTasks).toBeVisible();
    await expect(
      myTasks.getByRole("heading", { name: "Mening vazifalarim" }),
    ).toBeVisible();
  });

  test('lists team members with role badges in the "Jamoa" section', async () => {
    await openDashboard();

    const team = page.locator('section[aria-label="Jamoa"]');
    await expect(team).toBeVisible();
    await expect(team.getByText(USERS.demo.email, { exact: true })).toBeVisible();
    // Egasi (demo) va admin (aziz) rol nishonlari ko'rinadi.
    await expect(team.getByText("Egasi", { exact: true })).toBeVisible();
    await expect(team.getByText("Admin", { exact: true }).first()).toBeVisible();
  });

  test("navigates to the task's list page when a task row is clicked", async () => {
    const listId = await firstListId(session.access, workspaceId);
    const title = uniqueTitle("dashboard navigatsiya");
    const task = await createTask(session.access, listId, title, {
      assignee_ids: [session.user.id],
    });

    try {
      await openDashboard();

      const row = page
        .locator('section[aria-label="Mening vazifalarim"] a')
        .filter({ hasText: title });
      await expect(row).toBeVisible({ timeout: 20_000 });
      await row.click();

      await page.waitForURL(new RegExp(`/w/${workspaceId}/l/${listId}`));
      await expect(page).toHaveURL(new RegExp(`task=${task.id}`));
    } finally {
      await deleteTaskAfterTest(session.access, task.id);
    }
  });
});
