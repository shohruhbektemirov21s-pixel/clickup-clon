import { expect, test, type BrowserContext, type Page, type WebSocket } from "@playwright/test";
import {
  createTask,
  deleteTaskAfterTest,
  firstListId,
  firstWorkspace,
  signedInContext,
  uniqueTitle,
  USERS,
  type AuthSession,
} from "./fixtures";

interface WsFrame {
  type: string;
  payload?: { data?: Record<string, unknown>; [key: string]: unknown };
}

interface FrameCollector {
  frames: WsFrame[];
  /** Kuzatilgan `/ws/list/` soketlari — yopilishini kutish uchun. */
  sockets: WebSocket[];
  reset: () => void;
}

/**
 * `/ws/list/{id}/` kanalidan kelgan freymlarni yig'adi. Sahifa ochilishidan
 * OLDIN ulanishi shart, aks holda `connection.ack` o'tkazib yuboriladi.
 */
function collectListFrames(page: Page): FrameCollector {
  const frames: WsFrame[] = [];
  const sockets: WebSocket[] = [];
  page.on("websocket", (ws) => {
    if (!ws.url().includes("/ws/list/")) return;
    sockets.push(ws);
    ws.on("framereceived", (event) => {
      const payload =
        typeof event.payload === "string"
          ? event.payload
          : event.payload.toString("utf8");
      try {
        frames.push(JSON.parse(payload) as WsFrame);
      } catch {
        // Freym JSON emas — e'tiborsiz.
      }
    });
  });
  return { frames, sockets, reset: () => frames.splice(0, frames.length) };
}

async function waitForFrame(collector: FrameCollector, type: string, timeout = 25_000) {
  await expect
    .poll(() => collector.frames.filter((f) => f.type === type).length, { timeout })
    .toBeGreaterThan(0);
}

/**
 * Ro'yxat kanalidagi hamma soket yopilganini kutadi.
 *
 * Ilgari bu yerda `waitForTimeout(1_000)` turardi — "soketlar yopilib
 * presence hisoblagichi nolga tushsin" degan umid bilan. Soketning haqiqiy
 * holati Playwright'da bor, shuning uchun kutish endi taxminiy emas.
 */
async function waitForListSocketsClosed(...collectors: FrameCollector[]) {
  await expect
    .poll(
      () =>
        collectors.reduce(
          (open, c) => open + c.sockets.filter((ws) => !ws.isClosed()).length,
          0,
        ),
      { timeout: 15_000 },
    )
    .toBe(0);
  for (const c of collectors) c.sockets.length = 0;
}

// ---------------------------------------------------------------------------
// Ikkita brauzer konteksti: A = demo (egasi), B = aziz (admin)
// ---------------------------------------------------------------------------

let contextA: BrowserContext;
let contextB: BrowserContext;
let pageA: Page;
let pageB: Page;
let framesA: FrameCollector;
let framesB: FrameCollector;
let session: AuthSession;
let azizId: string;
let workspaceId: string;
let listId: string;

test.beforeAll(async ({ browser }) => {
  // Ikkala kontekst ham sessiyani REST orqali oladi (login formasi emas), ya'ni
  // bu hook endi throttle back-off kutmaydi va `test.setTimeout(240_000)`
  // kerak emas.
  const a = await signedInContext(browser, USERS.demo);
  const b = await signedInContext(browser, USERS.aziz);
  contextA = a.context;
  contextB = b.context;
  pageA = a.page;
  pageB = b.page;
  session = a.session;
  azizId = b.session.user.id;

  workspaceId = (await firstWorkspace(session.access)).id;
  listId = await firstListId(session.access, workspaceId);

  framesA = collectListFrames(pageA);
  framesB = collectListFrames(pageB);
});

test.afterAll(async () => {
  await contextA?.close();
  await contextB?.close();
});

/** Har bir testdan oldin: ikkala sahifa kanaldan chiqadi, buferlar tozalanadi. */
test.beforeEach(async () => {
  await Promise.all([
    pageA.goto(`/w/${workspaceId}`),
    pageB.goto(`/w/${workspaceId}`),
  ]);
  // Soketlar yopilib, presence hisoblagichi nolga tushishi uchun.
  await waitForListSocketsClosed(framesA, framesB);
  framesA.reset();
  framesB.reset();
});

const listUrl = () => `/w/${workspaceId}/l/${listId}`;

test.describe("realtime list channel", () => {
  test("delivers connection.ack and presence.sync to both browser contexts", async () => {
    await pageA.goto(listUrl());
    await pageB.goto(listUrl());

    await waitForFrame(framesA, "connection.ack");
    await waitForFrame(framesA, "presence.sync");
    await waitForFrame(framesB, "connection.ack");
    await waitForFrame(framesB, "presence.sync");

    // Kanal ochilgani UI holat nishonida ham ko'rinadi.
    await expect(pageA.getByText("Jonli")).toBeVisible();
    await expect(pageB.getByText("Jonli")).toBeVisible();
  });

  test("propagates a task created over REST to an open list without a reload", async () => {
    const title = uniqueTitle("realtime task");
    let taskId: string | null = null;

    await pageA.goto(listUrl());
    await pageB.goto(listUrl());
    await waitForFrame(framesB, "connection.ack");
    await expect(pageB.getByText("Jonli")).toBeVisible();

    try {
      // A REST orqali yaratadi (brauzerdan boshqa client id bilan, shuning
      // uchun echo bostirish ishlamaydi va B freymni ko'radi).
      const task = await createTask(session.access, listId, title);
      taskId = task.id;

      await waitForFrame(framesB, "task.created");
      // B sahifani yangilamasdan vazifani ko'radi.
      await expect(pageB.getByText(title, { exact: true })).toBeVisible({
        timeout: 20_000,
      });
    } finally {
      if (taskId) await deleteTaskAfterTest(session.access, taskId);
    }
  });

  test("sends presence.join to the first user when a second user connects", async () => {
    // A birinchi bo'lib ulanadi.
    await pageA.goto(listUrl());
    await waitForFrame(framesA, "connection.ack");
    await waitForFrame(framesA, "presence.sync");

    // Keyin B ulanadi → A ga aziz uchun presence.join keladi.
    // (Server `presence.join` ni butun guruhga yuboradi, shu jumladan
    // ulangan foydalanuvchining o'ziga ham — shuning uchun aynan aziz
    // uchun kelgan freym qidiriladi.)
    // Presence payload'ida ATAYLAB email yo'q: mehmon boshqa a'zolarning ish
    // pochtasini WS orqali yig'ib olmasligi uchun server faqat
    // {id, full_name, avatar, avatar_color} yuboradi (§15.3 PresenceUser).
    await pageB.goto(listUrl());
    const joinedIds = () =>
      framesA.frames
        .filter((f) => f.type === "presence.join")
        .map((f) => (f.payload?.data?.user as { id?: string } | undefined)?.id);

    await expect.poll(joinedIds, { timeout: 25_000 }).toContain(azizId);
  });
});
