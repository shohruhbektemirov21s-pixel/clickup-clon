import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import {
  createTask,
  deleteTaskQuietly,
  firstListId,
  firstWorkspace,
  login,
  sessionFor,
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
  reset: () => void;
}

/**
 * `/ws/list/{id}/` kanalidan kelgan freymlarni yig'adi. Sahifa ochilishidan
 * OLDIN ulanishi shart, aks holda `connection.ack` o'tkazib yuboriladi.
 */
function collectListFrames(page: Page): FrameCollector {
  const frames: WsFrame[] = [];
  page.on("websocket", (ws) => {
    if (!ws.url().includes("/ws/list/")) return;
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
  return { frames, reset: () => frames.splice(0, frames.length) };
}

async function waitForFrame(collector: FrameCollector, type: string, timeout = 25_000) {
  await expect
    .poll(() => collector.frames.filter((f) => f.type === type).length, { timeout })
    .toBeGreaterThan(0);
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
let workspaceId: string;
let listId: string;

test.beforeAll(async ({ browser }) => {
  // Two UI logins land in the same per-IP auth throttle bucket as the rest of
  // the suite, so this hook may have to sit through a 429 back-off window.
  test.setTimeout(240_000);
  session = await sessionFor(USERS.demo);
  workspaceId = (await firstWorkspace(session.access)).id;
  listId = await firstListId(session.access, workspaceId);

  contextA = await browser.newContext();
  contextB = await browser.newContext();
  pageA = await contextA.newPage();
  pageB = await contextB.newPage();

  await login(pageA, USERS.demo);
  await login(pageB, USERS.aziz);

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
  await pageA.waitForTimeout(1_000);
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
      if (taskId) await deleteTaskQuietly(session.access, taskId);
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
    await pageB.goto(listUrl());
    const joinedEmails = () =>
      framesA.frames
        .filter((f) => f.type === "presence.join")
        .map((f) => (f.payload?.data?.user as { email?: string } | undefined)?.email);

    await expect.poll(joinedEmails, { timeout: 25_000 }).toContain(USERS.aziz.email);
  });
});
