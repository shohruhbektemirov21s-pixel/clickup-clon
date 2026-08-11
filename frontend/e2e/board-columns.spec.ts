import { expect, test } from "@playwright/test";
import {
  firstListId,
  firstWorkspace,
  signedInContext,
  USERS,
  waitForAppShell,
} from "./fixtures";

/**
 * Doska ustunlari SERVERDAN keladi (kontrakt §10.4).
 *
 * v1.4.0 gacha ustunlar `GET lists/{id}/status-set/` javobidan yasalardi va
 * har bir ish maydonining o'z nomlari/tartibi bo'lardi. Endi holat — to'rtta
 * qat'iy kod, `?group_by=status` esa **doim aynan to'rtta guruhni** va
 * **doim `todo → in_progress → review → done`** tartibida qaytaradi, guruh
 * bo'sh bo'lsa ham.
 *
 * Shu testning asosiy qiymati — **bo'sh ustun ham chizilishi**. Migratsiya
 * hech qanday eski vazifani `review` ga ko'chirmagan (§9.2), ya'ni
 * "Tekshirilmoqda" demo bazada bo'sh; agar ustunlar ma'lumotdagi kodlardan
 * yig'ilib qolsa, o'sha ustun yo'qoladi va u yerga hech narsani tashlab
 * bo'lmaydi. Aynan shu regressiya ushlab turiladi.
 */
test.describe("doska — ustunlar javobdan keladi", () => {
  /** `src/i18n/uz.ts` dagi `STATUS_LABEL`, `STATUS_ORDER` tartibida. */
  const COLUMNS = ["Boshlanmagan", "Jarayonda", "Tekshirilmoqda", "Bajarildi"];

  test("to'rtta holat ustuni doim ko'rinadi, bo'shi ham", async ({ browser }) => {
    const { context, page, session } = await signedInContext(browser, USERS.demo);
    try {
      const workspace = await firstWorkspace(session.access);
      const listId = await firstListId(session.access, workspace.id);

      await page.goto(`/w/${workspace.id}/l/${listId}?view=board`);
      await waitForAppShell(page);

      // Ustun `<section aria-label="<Nom> ustuni, N ta vazifa">` — ya'ni
      // nomlangan `region`. Nom bo'yicha qidiramiz, DOM tartibi bo'yicha emas.
      for (const label of COLUMNS) {
        await expect(
          page.getByRole("region", { name: new RegExp(`^${label} ustuni,`) }),
          `«${label}» ustuni doskada yo'q`,
        ).toBeVisible({ timeout: 20_000 });
      }

      // Tartib ham shartnomaviy: chapdan o'ngga `STATUS_ORDER`.
      const rendered = await page
        .getByRole("region", { name: /ustuni, \d+ ta vazifa$/ })
        .evaluateAll((nodes) =>
          nodes.map((node) => node.getAttribute("aria-label")?.split(" ustuni,")[0] ?? ""),
        );
      expect(rendered).toEqual(COLUMNS);
    } finally {
      await context.close();
    }
  });
});
