import { expect, test } from "@playwright/test";
import type { Browser, BrowserContext, Page } from "@playwright/test";

import {
  USERS,
  apiRequest,
  collectPageErrors,
  firstWorkspace,
  gotoFirstList,
  resetRolePermissions,
  signIn,
  signedInContext,
} from "./fixtures";

/**
 * Huquqlar matritsasi — /w/{id}/settings/permissions
 *
 * Egasi (demo) matritsani ko'radi va tahrirlaydi; `workspace.manage_permissions`
 * huquqiga ega bo'lmagan admin (aziz) uchun bo'lim umuman mavjud emas.
 *
 * ⚠ Bu spec ish maydonining HAQIQIY rol-huquq matritsasini o'zgartiradi va
 * fayllar alifbo tartibida ishlagani uchun `realtime` va `smoke` dan OLDIN
 * yuradi. Shu sababli tozalash uch qavatli:
 *
 *   1. har bir yozadigan test o'zidan keyin `resetRolePermissions` chaqiradi;
 *   2. `afterAll` yana bir marta qaytaradi va xatoni **yutmaydi** — reset
 *      yiqilsa spec qizil bo'ladi (ilgari `.catch(() => {})` bor edi va
 *      yiqilgan reset demo ish maydonini butunlay o'zgargan holda qoldirardi);
 *   3. `e2e/global-teardown.ts` butun run oxirida yakuniy kafolat sifatida
 *      yana qaytaradi, `e2e/global-setup.ts` esa run boshida — shunda oldingi
 *      uzilib qolgan run keyingisini ifloslantirmaydi.
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
    const signedIn = await signedInContext(browser, USERS.demo);
    ownerContext = signedIn.context;
    ownerPage = signedIn.page;
    access = signedIn.session.access;
    workspaceId = (await firstWorkspace(access)).id;
  });

  test.afterAll(async () => {
    try {
      // Xato ATAYLAB yutilmaydi — yutilgan reset keyingi spec'larni sababsiz
      // yiqitadi va demo ish maydonini o'zgargan holda qoldiradi.
      await resetRolePermissions(access, workspaceId);
    } finally {
      await ownerContext?.close();
    }
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
    await resetRolePermissions(access, workspaceId);
    await openPermissions(ownerPage);

    const cell = ownerPage.getByLabel(MEMBER_SPACE_CREATE);
    await expect(cell).not.toBeChecked();

    try {
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
    } finally {
      // Keyingi test toza matritsadan boshlansin.
      await resetRolePermissions(access, workspaceId);
    }
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

    await resetRolePermissions(access, workspaceId);

    const matrix = await readMatrix();
    expect(matrix.overrides).toHaveLength(0);
    expect(matrix.roles.member.permissions).not.toContain("space.create");
  });

  test("an admin without manage_permissions cannot reach the section", async ({ page }) => {
    const collected = collectPageErrors(page);
    await signIn(page, USERS.aziz);

    await page.goto(`/w/${workspaceId}/settings`);
    await expect(page.getByRole("link", { name: NAV_PERMISSIONS })).toHaveCount(0);

    // To'g'ridan-to'g'ri URL ham matritsani oshkor qilmaydi.
    await page.goto(`/w/${workspaceId}/settings/permissions`);
    await expect(page.getByRole("columnheader", { name: "Mehmon" })).toHaveCount(0);
    await expect(page.getByLabel(MEMBER_SPACE_CREATE)).toHaveCount(0);

    expect(collected.errors).toEqual([]);
  });
});

/**
 * Faqat o'qish hisobi: yozish affordance'lari UMUMAN chizilmasligi kerak.
 *
 * Nega alohida `describe`: yuqoridagi blok matritsani o'zgartiradi va
 * `beforeAll` da egasi bilan kontekst ochadi. Bu testlar esa matritsaga
 * TEGMAYDI — ular standart holatni tekshiradi, shuning uchun aralashmasin.
 *
 * Regressiya konteksti (5abb0b7): list-view fasadi bir marta revert
 * qilingan va o'shanda `mehmon` (roli `member`, `is_readonly=True`) list
 * ko'rinishida "Vazifa qo'shish" ni ko'rardi, bosganda esa server `403`
 * qaytarardi. Server hech qachon buzilmagan; yolg'on gapirgan narsa UI edi.
 * Bu ikki test aynan shu holatning qaytmasligini ushlab turadi.
 */
test.describe("faqat o'qish hisobi — list view affordance'lari", () => {
  const ADD_TASK = /Vazifa qo'shish/;

  /**
   * `signedInContext` — `signIn` EMAS, va bu ataylab.
   *
   * `signIn` tokenni allaqachon yuklangan `/login` sahifasiga yozadi. O'sha
   * sahifaning `SessionBootstrap` effekti (hidratsiyadan keyin ishga tushadi)
   * tokenni ko'rib qoladi va uni ishlatib yuboradi; refresh token esa birinchi
   * ishlatilishida rotatsiya qilinib eskisi blacklist'ga tushadi. Keyingi
   * navigatsiya o'sha eskisi bilan borsa `401` oladi va sessiya tozalanadi —
   * test login sahifasida tugaydi.
   *
   * `signedInContext` `storageState` ni kontekst yaratilishida beradi, ya'ni
   * token BIRINCHI sahifa yuklanishidan oldin joyida bo'ladi va bootstrap
   * bir marta ishlaydi.
   */
  async function openFirstList(browser: Browser, user: (typeof USERS)[keyof typeof USERS]) {
    const { context, page, session } = await signedInContext(browser, user);
    const workspace = await firstWorkspace(session.access);
    await gotoFirstList(page, workspace.id);
    return { context, page };
  }

  test("readonly hisob 'Vazifa qo'shish' ni ko'rmaydi", async ({ browser }) => {
    const { context, page } = await openFirstList(browser, USERS.mehmon);
    try {
      const collected = collectPageErrors(page);

      // Ro'yxat MAZMUNI ko'rinadi — cheklov ko'rishga emas, yozishga.
      await expect(page.locator("main")).toBeVisible();

      // `toHaveCount(0)` ataylab `toBeDisabled()` emas: talab — affordance
      // umuman render bo'lmasin, "bosib bo'lmaydigan tugma" bo'lib turmasin.
      await expect(page.getByRole("button", { name: ADD_TASK })).toHaveCount(0);

      expect(collected.errors).toEqual([]);
    } finally {
      await context.close();
    }
  });

  test("oddiy a'zo esa 'Vazifa qo'shish' ni ko'radi", async ({ browser }) => {
    // Nazorat testi: yuqoridagi assertion faqat readonly tufayli o'tayotganini
    // isbotlaydi. Usiz "tugma umuman yo'q" degan holat ham testni yashil
    // qilardi va regressiya sezilmay qolardi.
    const { context, page } = await openFirstList(browser, USERS.jasur);
    try {
      await expect(page.getByRole("button", { name: ADD_TASK }).first()).toBeVisible({
        timeout: 20_000,
      });
    } finally {
      await context.close();
    }
  });
});
