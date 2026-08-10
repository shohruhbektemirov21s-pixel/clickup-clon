import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

import {
  USERS,
  apiRequest,
  collectPageErrors,
  firstWorkspace,
  login,
  sessionFor,
} from "./fixtures";

/**
 * Huquqlar matritsasi — /w/{id}/settings/permissions
 *
 * Egasi (demo) matritsani ko'radi va tahrirlaydi; `workspace.manage_permissions`
 * huquqiga ega bo'lmagan admin (aziz) uchun bo'lim umuman mavjud emas.
 *
 * Login `auth`/`auth_burst` throttle'iga tushadi, shuning uchun egasi uchun
 * bitta kontekst `beforeAll` da ochiladi va barcha testlar shuni bo'lishadi.
 * Har bir test o'zidan keyin matritsani standart holatga qaytaradi.
 */

const NAV_PERMISSIONS = "Huquqlar";
const SAVE = /^Saqlash/;
const OWNER_LOCK = "Egasidan huquqlarni olib bo'lmaydi";

/** Matritsa checkbox'lari `{Rol} — {huquq nomi}` yorlig'i bilan belgilanadi. */
const MEMBER_SPACE_CREATE = "A'zo — Bo'lim yaratish";
const ADMIN_MANAGE_PERMS = "Admin — Ruxsatlar matritsasini boshqarish";

type MatrixOverride = { role: string; permission: string; allowed: boolean };
type Matrix = {
  version: number;
  roles: Record<string, { locked: boolean; permissions: string[] }>;
  overrides: MatrixOverride[];
};
type Catalog = { groups: { permissions: unknown[] }[] };

let ownerContext: BrowserContext;
let ownerPage: Page;
let access: string;
let workspaceId: string;

async function resetMatrix() {
  await apiRequest<void>(access, `workspaces/${workspaceId}/role-permissions/reset/`, {
    method: "POST",
    body: { role: null },
  });
}

function readMatrix() {
  return apiRequest<Matrix>(access, `workspaces/${workspaceId}/role-permissions/`);
}

async function openPermissions(page: Page) {
  await page.goto(`/w/${workspaceId}/settings`);
  await page.getByRole("link", { name: NAV_PERMISSIONS }).click();
  await expect(page).toHaveURL(/\/settings\/permissions$/);
}

test.describe.configure({ mode: "serial" });

test.describe("permissions matrix", () => {
  test.beforeAll(async ({ browser }) => {
    // Bu login butun to'plam bilan bitta per-IP auth throttle chelagini
    // bo'lishadi, shuning uchun hook 429 back-off oynasini kutishi mumkin.
    test.setTimeout(240_000);
    const session = await sessionFor(USERS.demo);
    access = session.access;
    workspaceId = (await firstWorkspace(access)).id;

    ownerContext = await browser.newContext();
    ownerPage = await ownerContext.newPage();
    await login(ownerPage, USERS.demo);
  });

  test.afterAll(async () => {
    await resetMatrix().catch(() => {});
    await ownerContext?.close();
  });

  test("owner sees every role column and the whole catalog is rendered", async () => {
    await openPermissions(ownerPage);

    for (const column of ["Huquq", "Egasi", "Admin", "A'zo", "Mehmon"]) {
      await expect(
        ownerPage.getByRole("columnheader", { name: column }).first()
      ).toBeVisible();
    }

    // Qattiq son yozilmaydi: katalog o'sganda test o'zi moslashadi, lekin
    // ekranda serverdagi kodlarning HAMMASI borligini talab qiladi.
    const catalog = await apiRequest<Catalog>(access, "permissions/");
    const codeCount = catalog.groups.reduce((n, g) => n + g.permissions.length, 0);
    expect(codeCount).toBeGreaterThanOrEqual(44);

    await expect
      .poll(async () => ownerPage.getByLabel(OWNER_LOCK).count())
      .toBe(codeCount);
  });

  test("the owner column is locked and owner-only codes are disabled elsewhere", async () => {
    await openPermissions(ownerPage);

    const ownerCells = ownerPage.getByLabel(OWNER_LOCK);
    await expect(ownerCells.first()).toBeDisabled();

    // `workspace.manage_permissions` — owner_only, boshqa rolga berib bo'lmaydi.
    await expect(ownerPage.getByLabel(ADMIN_MANAGE_PERMS)).toBeDisabled();
  });

  test("toggling a permission persists across a reload and lands in overrides", async () => {
    await resetMatrix();
    await openPermissions(ownerPage);

    const cell = ownerPage.getByLabel(MEMBER_SPACE_CREATE);
    await expect(cell).not.toBeChecked();

    await cell.check();
    await ownerPage.getByRole("button", { name: SAVE }).click();

    await expect
      .poll(async () => (await readMatrix()).roles.member.permissions.includes("space.create"))
      .toBe(true);

    const matrix = await readMatrix();
    expect(
      matrix.overrides.some(
        (row) => row.role === "member" && row.permission === "space.create" && row.allowed
      )
    ).toBe(true);

    await ownerPage.reload();
    await expect(ownerPage.getByLabel(MEMBER_SPACE_CREATE)).toBeChecked();
  });

  test("reset returns the matrix to its defaults", async () => {
    await apiRequest<Matrix>(access, `workspaces/${workspaceId}/role-permissions/`, {
      method: "PUT",
      body: {
        expected_version: (await readMatrix()).version,
        roles: { member: { "space.create": true } },
      },
    });

    await openPermissions(ownerPage);
    await expect(ownerPage.getByLabel(MEMBER_SPACE_CREATE)).toBeChecked();

    await resetMatrix();

    const matrix = await readMatrix();
    expect(matrix.overrides).toHaveLength(0);
    expect(matrix.roles.member.permissions).not.toContain("space.create");
  });

  test("an admin without manage_permissions cannot reach the section", async ({ page }) => {
    const collected = collectPageErrors(page);
    await login(page, USERS.aziz);

    await page.goto(`/w/${workspaceId}/settings`);
    await expect(page.getByRole("link", { name: NAV_PERMISSIONS })).toHaveCount(0);

    // To'g'ridan-to'g'ri URL ham matritsani oshkor qilmaydi.
    await page.goto(`/w/${workspaceId}/settings/permissions`);
    await expect(page.getByRole("columnheader", { name: "Mehmon" })).toHaveCount(0);
    await expect(page.getByLabel(MEMBER_SPACE_CREATE)).toHaveCount(0);

    expect(collected.errors).toEqual([]);
  });
});
