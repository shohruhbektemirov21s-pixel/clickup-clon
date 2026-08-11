/**
 * MANZILLAR SHARTNOMASI.
 *
 * Bu ro'yxat Next'ning `src/app/**` fayl daraxtidan bir-bir ko'chirilgan.
 * E2E testlari, emaildagi taklif havolalari va bildirishnomalarning `url`
 * maydoni (server tomondan keladi) aynan shu manzillarga tayanadi — ya'ni
 * bittasini qayta nomlash foydalanuvchi havolasini o'ldiradi. Test route
 * jadvalini `matchRoutes` bilan tekshiradi: har bir manzil mos kelishi va
 * `*` (404) shoxobchasiga TUSHMASLIGI shart.
 */

import { describe, expect, it } from "vitest";
import { matchRoutes } from "react-router";
import { routes } from "@/routes/app-routes";

const URLS = [
  "/",
  "/login",
  "/register",
  "/invite",
  "/invite/abc123",
  "/settings/profile",
  "/w/ws-1",
  "/w/ws-1/dashboard",
  "/w/ws-1/chat",
  "/w/ws-1/ai",
  "/w/ws-1/notifications",
  "/w/ws-1/planner",
  "/w/ws-1/search",
  "/w/ws-1/l/list-1",
  "/w/ws-1/s/space-1/members",
  "/w/ws-1/u/user-1",
  "/w/ws-1/settings",
  "/w/ws-1/settings/members",
  "/w/ws-1/settings/invitations",
  "/w/ws-1/settings/permissions",
] as const;

describe("marshrut jadvali", () => {
  it.each(URLS)("%s manzili 404 ga tushmaydi", (url) => {
    const matches = matchRoutes(routes, url);
    expect(matches, `${url} umuman mos kelmadi`).not.toBeNull();
    expect(matches?.at(-1)?.route.path, `${url} 404 ga tushdi`).not.toBe("*");
  });

  it("yigirmata manzil qamrab olingan", () => {
    expect(new Set(URLS).size).toBe(20);
  });

  it("segmentlardan parametrlar to'g'ri ajratiladi", () => {
    const matches = matchRoutes(routes, "/w/ws-1/l/list-1");
    expect(matches?.at(-1)?.params).toEqual({ workspaceId: "ws-1", listId: "list-1" });

    const space = matchRoutes(routes, "/w/ws-1/s/space-1/members");
    expect(space?.at(-1)?.params).toEqual({ workspaceId: "ws-1", spaceId: "space-1" });

    const invite = matchRoutes(routes, "/invite/tok-1");
    expect(invite?.at(-1)?.params).toEqual({ token: "tok-1" });
  });

  it("noma'lum manzil 404 marshrutiga tushadi", () => {
    const matches = matchRoutes(routes, "/hech-qanday-sahifa");
    expect(matches?.at(-1)?.route.path).toBe("*");
  });
});
