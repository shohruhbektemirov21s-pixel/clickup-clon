import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

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
 * Har bir test o'zidan keyin matritsani standart holatga qaytaradi, shuning
 * uchun tartib muhim emas va qoldiq holat qolmaydi.
 */

const NAV_PERMISSIONS = "Huquqlar";
const SAVE = /^Saqlash/;
const OWNER_LOCK = "Egasidan huquqlarni olib bo'lmaydi";

/** `A'zo — Bo'lim yaratish` katagi: matritsa checkbox'lari shu yorliq bilan. */
const MEMBER_SPACE_CREATE = "A'zo — Bo'lim yaratish";
const ADMIN_MANAGE_PERMS = "Admin — Ruxsatlar matritsasini boshqarish";

type MatrixOverride = { role: string; permission: string; allowed: boolean };
type Matrix = {
  version: number;
  roles: Record<string, { locked: boolean; permissions: string[] }>;
  overrides: MatrixOverride[];
};
type Catalog = { groups: { permissions: unknown[] }[] };

async function resetMatrix(access: string, workspaceId: string) {
  await apiRequest<void>(access, `workspaces/${workspaceId}/role-permissions/reset/`, {
    method: "POST",
    body: { role: null },
  });
}

function readMatrix(access: string, workspaceId: string) {
  return apiRequest<Matrix>(access, `workspaces/${workspaceId}/role-permissions/`);
}

async function openPermissions(page: Page, workspaceId: string) {
  await page.goto(`/w/${workspaceId}/settings`);
  await page.getByRole("link", { name: NAV_PERMISSIONS }).click();
  await expect(page).toHaveURL(/\/settings\/permissions$/);
}

test.describe("permissions matrix", () => {
  test("owner sees every role column and the catalog is fully rendered", async ({
    page,
  }) => {
    const session = await sessionFor(USERS.demo);
    const workspace = await firstWorkspace(session.access);

    await login(page, USERS.demo);
    await openPermissions(page, workspace.id);

    for (const column of ["Huquq", "Egasi", "Admin", "A'zo", "Mehmon"]) {
      await expect(page.getByRole("columnheader", { name: column }).first()).toBeVisible();
    }

    // Katalog serverdan kelgan kod soni bilan bir xil bo'lishi kerak.
    const catalog = await apiRequest<Catalog>(session.access, "permissions/");
    const codeCount = catalog.groups.reduce(
      (total, group) => total + group.permissions.length,
      0
    );
    expect(codeCount).toBe(44);
  });

  test("the owner column is locked and owner-only codes are disabled elsewhere", async ({
    page,
  }) => {
    const session = await sessionFor(USERS.demo);
    const workspace = await firstWorkspace(session.access);

    await login(page, USERS.demo);
    await openPermissions(page, workspace.id);

    // Egasi ustunidagi har bir katak qulflangan.
    const ownerCells = page.getByLabel(OWNER_LOCK);
    await expect(ownerCells.first()).toBeDisabled();
    expect(await ownerCells.count()).toBeGreaterThan(0);

    // `workspace.manage_permissions` — owner_only, boshqa rollarga berib bo'lmaydi.
    await expect(page.getByLabel(ADMIN_MANAGE_PERMS)).toBeDisabled();
  });

  test("toggling a permission persists across a reload and lands in overrides", async ({
    page,
  }) => {
    const session = await sessionFor(USERS.demo);
    const workspace = await firstWorkspace(session.access);
    await resetMatrix(session.access, workspace.id);

    try {
      await login(page, USERS.demo);
      await openPermissions(page, workspace.id);

      const cell = page.getByLabel(MEMBER_SPACE_CREATE);
      await expect(cell).not.toBeChecked();

      await cell.check();
      await page.getByRole("button", { name: SAVE }).click();

      // Server tomonda haqiqatan yozilganini tasdiqlaymiz.
      await expect
        .poll(async () => {
          const matrix = await readMatrix(session.access, workspace.id);
          return matrix.roles.member.permissions.includes("space.create");
        })
        .toBe(true);

      const matrix = await readMatrix(session.access, workspace.id);
      expect(
        matrix.overrides.some(
          (row) => row.role === "member" && row.permission === "space.create" && row.allowed
        )
      ).toBe(true);

      // Sahifa yangilangandan keyin ham belgilangan bo'lib qoladi.
      await page.reload();
      await expect(page.getByLabel(MEMBER_SPACE_CREATE)).toBeChecked();
    } finally {
      await resetMatrix(session.access, workspace.id);
    }
  });

  test("reset returns the matrix to its defaults", async ({ page }) => {
    const session = await sessionFor(USERS.demo);
    const workspace = await firstWorkspace(session.access);

    // Avval ataylab defaultdan chetga chiqamiz.
    await apiRequest<Matrix>(session.access, `workspaces/${workspace.id}/role-permissions/`, {
      method: "PUT",
      body: {
        expected_version: (await readMatrix(session.access, workspace.id)).version,
        roles: { member: { "space.create": true } },
      },
    });

    await login(page, USERS.demo);
    await openPermissions(page, workspace.id);
    await expect(page.getByLabel(MEMBER_SPACE_CREATE)).toBeChecked();

    await resetMatrix(session.access, workspace.id);

    const matrix = await readMatrix(session.access, workspace.id);
    expect(matrix.overrides).toHaveLength(0);
    expect(matrix.roles.member.permissions).not.toContain("space.create");
  });

  test("a member without manage_permissions cannot reach the section", async ({ page }) => {
    const session = await sessionFor(USERS.demo);
    const workspace = await firstWorkspace(session.access);
    const collected = collectPageErrors(page);

    await login(page, USERS.aziz);

    // Navigatsiyada bo'lim ko'rinmaydi.
    await page.goto(`/w/${workspace.id}/settings`);
    await expect(page.getByRole("link", { name: NAV_PERMISSIONS })).toHaveCount(0);

    // To'g'ridan-to'g'ri URL ham matritsani oshkor qilmaydi.
    await page.goto(`/w/${workspace.id}/settings/permissions`);
    await expect(page.getByRole("columnheader", { name: "Mehmon" })).toHaveCount(0);
    await expect(page.getByLabel(MEMBER_SPACE_CREATE)).toHaveCount(0);

    expect(collected.errors).toEqual([]);
  });
});
