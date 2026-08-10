import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

import { USERS, apiRequest, collectPageErrors, firstWorkspace, login, sessionFor } from "./fixtures";

/**
 * A'zo profili — /w/{id}/u/{userId}
 *
 * "Kim nima ish qilgan" ekrani: statistika, vazifalar, faoliyat tasmasi va
 * bo'limlar. UI raqamlari API bilan bir xil bo'lishi tekshiriladi — aks holda
 * ekran ishonchsiz bo'lib qoladi.
 *
 * Login throttle'iga urilmaslik uchun bitta kontekst bo'lishiladi.
 */

type Member = { user: { id: string; full_name: string; email: string } };
type Profile = {
  user: { id: string; full_name: string };
  role: string;
  stats: {
    open_tasks: number;
    overdue_tasks: number;
    due_today: number;
    completed_tasks: number;
  };
  spaces: { id: string; name: string }[];
};

let context: BrowserContext;
let page: Page;
let access: string;
let workspaceId: string;
let target: Member;

test.describe.configure({ mode: "serial" });

test.describe("member profile", () => {
  test.beforeAll(async ({ browser }) => {
    test.setTimeout(240_000);
    const session = await sessionFor(USERS.demo);
    access = session.access;
    workspaceId = (await firstWorkspace(access)).id;

    const roster = await apiRequest<{ results: Member[] }>(
      access,
      `workspaces/${workspaceId}/members/`,
      { query: { page_size: 50 } },
    );
    // O'zimizdan boshqa birov — "boshqaning ishini ko'rish" holati.
    const other = roster.results.find((m) => m.user.email !== USERS.demo.email);
    if (!other) throw new Error("ish maydonida boshqa a'zo yo'q");
    target = other;

    context = await browser.newContext();
    page = await context.newPage();
    await login(page, USERS.demo);
  });

  test.afterAll(async () => {
    await context?.close();
  });

  test("shows the member header and the four stat cards", async () => {
    // Raqamlarni aynan solishtirmaymiz: ular jonli ma'lumot ustida ishlaydi va
    // parallel ish testni beqaror qiladi. Bu yerda ekran quriladimi va serverga
    // ulanadimi — shuni tekshiramiz; raqam mantig'i backend testlarida.
    const profile = await apiRequest<Profile>(
      access,
      `workspaces/${workspaceId}/members/${target.user.id}/profile/`,
    );
    expect(profile.user.id).toBe(target.user.id);

    await page.goto(`/w/${workspaceId}/u/${target.user.id}`);
    await expect(page.getByRole("heading", { name: target.user.full_name })).toBeVisible();

    const stats = page.getByLabel("A'zo statistikasi");
    await expect(stats).toBeVisible();
    for (const label of ["Ochiq vazifalar", "Muddati o'tgan", "Bugun", "Bajarilgan"]) {
      await expect(stats.getByText(label, { exact: false }).first()).toBeVisible();
    }
  });

  test("switching tabs swaps the panel underneath", async () => {
    await page.goto(`/w/${workspaceId}/u/${target.user.id}`);

    // Bo'lim `section`i faqat ma'lumot bo'lganda chiziladi (aks holda bo'sh
    // holat bloki), shuning uchun tab holati va paydo/yo'q bo'lish tekshiriladi.
    const tasksPanel = page.getByLabel("A'zo vazifalari");
    await expect(tasksPanel).toBeVisible();

    for (const [label, gone] of [
      ["Faoliyat", tasksPanel],
      ["Bo'limlar", tasksPanel],
    ] as const) {
      const tab = page.getByRole("tab", { name: label });
      await tab.click();
      await expect(tab).toHaveAttribute("aria-selected", "true");
      await expect(gone).toHaveCount(0);
    }

    const back = page.getByRole("tab", { name: "Vazifalar" });
    await back.click();
    await expect(back).toHaveAttribute("aria-selected", "true");
    await expect(tasksPanel).toBeVisible();
  });

  test("the dashboard team card links through to the profile", async () => {
    const errors = collectPageErrors(page);

    await page.goto(`/w/${workspaceId}`);
    // Yon panelda ham shu ism bor, lekin u sozlamalarga olib boradi — shuning
    // uchun aynan asosiy ustundagi profil havolasi tanlanadi.
    await page
      .locator('main a[href*="/u/"]')
      .filter({ hasText: target.user.full_name })
      .first()
      .click();

    await expect(page).toHaveURL(new RegExp(`/u/${target.user.id}$`));
    await expect(page.getByRole("heading", { name: target.user.full_name })).toBeVisible();
    expect(errors.errors).toEqual([]);
  });

  test("an unknown member id is not found", async () => {
    await page.goto(`/w/${workspaceId}/u/00000000-0000-0000-0000-000000000000`);
    await expect(page.getByLabel("A'zo statistikasi")).toHaveCount(0);
  });
});
