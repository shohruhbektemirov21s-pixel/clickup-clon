import { expect, test, type Page } from "@playwright/test";
import {
  apiLogin,
  createTask,
  deleteTaskQuietly,
  firstListId,
  firstWorkspace,
  login,
  uniqueTitle,
  USERS,
  type AuthSession,
} from "./fixtures";

interface WsFrame {
  type: string;
  payload?: { data?: Record<string, unknown>; [key: string]: unknown };
}

/**
 * `/ws/list/{id}/` kanalidan kelgan freymlarni yig'adi. Navigatsiyadan OLDIN
 * ulanishi shart, aks holda `connection.ack` o'tkazib yuboriladi.
 */
function collectListFrames(page: Page): WsFrame[] {
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
  return frames;
}

async function waitForFrame(frames: WsFrame[], type: string, timeout = 20_000) {
  await expect
    .poll(() => frames.filter((f) => f.type === type).length, { timeout })
    .toBeGreaterThan(0);
}

/** Ikkala kanal ishtirokchisi uchun umumiy kontekst. */
async function demoContext(): Promise<{
  session: AuthSession;
  workspaceId: string;
  listId: string;
}> {
  const session = await apiLogin(USERS.demo.email, USERS.demo.password);
  const workspace = await firstWorkspace(session.access);
  const listId = await firstListId(session.access, workspace.id);
  return { session, workspaceId: workspace.id, listId };
}

test.describe("realtime list channel", () => {
  test("delivers connection.ack and presence.sync to both browser contexts", async ({
    browser,
  }) => {
    const { workspaceId, listId } = await demoContext();

    const contextA = await browser.newContext();
    const contextB = await browser.newContext();
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();

    try {
      await login(pageA, USERS.demo);
      await login(pageB, USERS.aziz);

      const framesA = collectListFrames(pageA);
      const framesB = collectListFrames(pageB);

      await pageA.goto(`/w/${workspaceId}/l/${listId}`);
      await pageB.goto(`/w/${workspaceId}/l/${listId}`);

      await waitForFrame(framesA, "connection.ack");
      await waitForFrame(framesA, "presence.sync");
      await waitForFrame(framesB, "connection.ack");
      await waitForFrame(framesB, "presence.sync");

      // UI holat nishoni ham "Jonli" ga o'tadi.
      await expect(pageA.getByText("Jonli")).toBeVisible();
      await expect(pageB.getByText("Jonli")).toBeVisible();
    } finally {
      await contextA.close();
      await contextB.close();
    }
  });

  test("propagates a task created over REST to an open list without a reload", async ({
    browser,
  }) => {
    const { session, workspaceId, listId } = await demoContext();
    const title = uniqueTitle("realtime task");

    const contextA = await browser.newContext();
    const contextB = await browser.newContext();
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();
    let taskId: string | null = null;

    try {
      await login(pageA, USERS.demo);
      await login(pageB, USERS.aziz);

      const framesB = collectListFrames(pageB);

      await pageA.goto(`/w/${workspaceId}/l/${listId}`);
      await pageB.goto(`/w/${workspaceId}/l/${listId}`);
      await waitForFrame(framesB, "connection.ack");
      await expect(pageB.getByText("Jonli")).toBeVisible();

      // A REST orqali yaratadi (brauzerdan alohida client id bilan).
      const task = await createTask(session.access, listId, title);
      taskId = task.id;

      await waitForFrame(framesB, "task.created");
      // B sahifani yangilamasdan vazifani ko'radi.
      await expect(pageB.getByText(title, { exact: true })).toBeVisible({
        timeout: 20_000,
      });
    } finally {
      if (taskId) await deleteTaskQuietly(session.access, taskId);
      await contextA.close();
      await contextB.close();
    }
  });

  test("sends presence.join to the first user when a second user connects", async ({
    browser,
  }) => {
    const { workspaceId, listId } = await demoContext();

    const contextA = await browser.newContext();
    const contextB = await browser.newContext();
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();

    try {
      await login(pageA, USERS.demo);
      await login(pageB, USERS.aziz);

      const framesA = collectListFrames(pageA);

      // A birinchi bo'lib ulanadi.
      await pageA.goto(`/w/${workspaceId}/l/${listId}`);
      await waitForFrame(framesA, "connection.ack");
      await waitForFrame(framesA, "presence.sync");

      // Keyin B ulanadi → A ga presence.join keladi.
      await pageB.goto(`/w/${workspaceId}/l/${listId}`);
      await waitForFrame(framesA, "presence.join");

      const join = framesA.find((f) => f.type === "presence.join");
      const user = join?.payload?.data?.user as { email?: string } | undefined;
      expect(user?.email).toBe(USERS.aziz.email);
    } finally {
      await contextA.close();
      await contextB.close();
    }
  });
});
