import {
  E2E_PREFIX,
  USERS,
  apiLogin,
  apiRequest,
  deleteTask,
  firstWorkspace,
  resetRolePermissions,
  type ApiTask,
} from "./fixtures";

/**
 * Run tugagandan keyingi tozalash (`playwright.config.ts` → globalTeardown).
 *
 * To'plam `seed_demo` ning bitta ish maydonini bo'lishadi, ya'ni har qanday
 * qoldiq KEYINGI runga o'tadi. Shuning uchun bu yerda:
 *
 *   1. rol-huquq matritsasi standart holatga qaytariladi — **majburiy**.
 *      `permissions.spec.ts` uni ataylab o'zgartiradi va (fayllar alifbo
 *      tartibida ishlagani uchun) `realtime` va `smoke` dan OLDIN yuradi.
 *      Bu qadam yiqilsa run ham yiqiladi: jimgina o'tib ketish demo ish
 *      maydonini butunlay o'zgargan holda qoldiradi.
 *
 *   2. `E2E ` prefiksli qolgan vazifalar supuriladi. Qoldiq bo'lishining
 *      o'zi run yiqilishiga sabab EMAS — yiqilgan test o'zining `finally`
 *      blokiga yetmasligi tabiiy va bu xato allaqachon hisobotda bor. Lekin
 *      qoldiqni **o'chirib bo'lmasa** — bu haqiqiy nosozlik va run yiqiladi.
 */

interface SearchRow {
  count: number;
  results: ApiTask[];
}

export default async function globalTeardown(): Promise<void> {
  let access: string;
  try {
    access = (await apiLogin(USERS.demo.email, USERS.demo.password)).access;
  } catch (err) {
    throw new Error(
      "[e2e teardown] demo hisobiga kirib bo'lmadi, tozalash bajarilmadi — " +
        "demo ish maydoni O'ZGARGAN holda qolgan bo'lishi mumkin.\n" +
        (err as Error).message,
    );
  }

  const workspace = await firstWorkspace(access);

  // --- 1. Huquqlar matritsasi (majburiy) -----------------------------------
  await resetRolePermissions(access, workspace.id);

  // --- 2. Qolgan test vazifalari -------------------------------------------
  const found = await apiRequest<SearchRow>(access, `workspaces/${workspace.id}/tasks/`, {
    query: { q: E2E_PREFIX.trim(), page_size: 100 },
  });
  const leftovers = found.results.filter((task) => task.title.startsWith(E2E_PREFIX));
  if (leftovers.length === 0) {
    process.stdout.write("[e2e teardown] toza — qoldiq vazifa yo'q\n");
    return;
  }

  const undeletable: string[] = [];
  for (const task of leftovers) {
    try {
      await deleteTask(access, task.id);
    } catch (err) {
      undeletable.push(`${task.title} (${task.id}) — ${(err as Error).message}`);
    }
  }

  process.stdout.write(
    `[e2e teardown] ${leftovers.length} ta qoldiq vazifa topildi va supurildi:\n` +
      leftovers.map((t) => `  - ${t.title}`).join("\n") +
      "\n  (yiqilgan test o'z `finally` blokiga yetmagan bo'lsa bu kutilgan hol)\n",
  );

  if (undeletable.length > 0) {
    throw new Error(
      "[e2e teardown] quyidagi test vazifalarini o'chirib bo'lmadi — demo ish " +
        "maydoni ifloslangan holda qoldi:\n  " +
        undeletable.join("\n  "),
    );
  }
}
