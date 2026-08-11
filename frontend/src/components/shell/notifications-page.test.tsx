/**
 * Async ko'rinishning to'rtta holati: yuklanish → xato → bo'sh → muvaffaqiyat
 * (reja §17.4 dagi komponent testi).
 *
 * `NotificationsPage` shu to'rt shoxobchani ochiq yozadi (`list.isPending`,
 * `list.isError`, `visible.length === 0`, ro'yxat), shuning uchun u
 * namunaviy holat mashinasi. Test faqat HTTP qatlamini mock qiladi —
 * TanStack Query, komponent va lug'at haqiqiy.
 */

import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { NOTIFICATIONS } from "@/i18n/uz";
import type { AppNotification, Paginated } from "@/types/api";

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  };
});

const { api } = await import("@/lib/api");
const { useAuthStore } = await import("@/stores/auth-store");
const { NotificationsPage } = await import("@/components/shell/notifications-page");

const WORKSPACE_ID = "ws-1";

function makeNotification(over: Partial<AppNotification> = {}): AppNotification {
  return {
    id: "n1",
    workspace_id: WORKSPACE_ID,
    actor: null,
    kind: "task_assigned",
    title: "Sizga vazifa biriktirildi",
    body: "Hisobot tayyorlash",
    url: `/w/${WORKSPACE_ID}/l/list-1`,
    is_read: false,
    read_at: null,
    created_at: "2026-08-11T09:00:00+05:00",
    ...over,
  };
}

function page(results: AppNotification[]): Paginated<AppNotification> {
  return { count: results.length, next: null, previous: null, results };
}

let queryClient: QueryClient;

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/w/${WORKSPACE_ID}/notifications`]}>
      <QueryClientProvider client={queryClient}>
        <NotificationsPage workspaceId={WORKSPACE_ID} />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  // Ro'yxat so'rovi `useAuthed()` bilan gate qilingan — sessiyasiz umuman
  // yuborilmaydi va test abadiy "yuklanmoqda" da qolardi.
  useAuthStore.setState({ status: "authenticated" });
});

/** Ikkita so'rov ketadi: ro'yxat va o'qilmaganlar soni. */
function mockApi(handler: (path: string) => Promise<unknown>) {
  vi.mocked(api.get).mockImplementation((path: string) => handler(path) as never);
}

describe("NotificationsPage", () => {
  it("yuklanayotganda skelet ko'rsatadi", () => {
    mockApi(() => new Promise(() => {}));
    const { container } = renderPage();

    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
    expect(screen.queryByText(NOTIFICATIONS.empty)).toBeNull();
    expect(screen.queryByText(NOTIFICATIONS.loadFailed)).toBeNull();
  });

  it("so'rov yiqilsa xato matni va qayta urinish tugmasi chiqadi", async () => {
    mockApi(() => Promise.reject(new Error("boom")));
    renderPage();

    expect(await screen.findByText(NOTIFICATIONS.loadFailed)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Qayta urinish" })).toBeInTheDocument();
  });

  it("ro'yxat bo'sh bo'lsa bo'sh holat matnini ko'rsatadi", async () => {
    mockApi((path) =>
      path.startsWith("notifications/unread-count")
        ? Promise.resolve({ count: 0 })
        : Promise.resolve(page([])),
    );
    renderPage();

    expect(await screen.findByText(NOTIFICATIONS.empty)).toBeInTheDocument();
    expect(screen.getByText(NOTIFICATIONS.emptyHint)).toBeInTheDocument();
  });

  it("ma'lumot kelganda qatorlarni va o'qilmagan hisoblagichni ko'rsatadi", async () => {
    const rows = [
      makeNotification(),
      makeNotification({ id: "n2", title: "Rolingiz o'zgardi", is_read: true }),
    ];
    mockApi((path) =>
      path.startsWith("notifications/unread-count")
        ? Promise.resolve({ count: 1 })
        : Promise.resolve(page(rows)),
    );
    renderPage();

    expect(await screen.findByText("Sizga vazifa biriktirildi")).toBeInTheDocument();
    expect(screen.getByText("Rolingiz o'zgardi")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText(NOTIFICATIONS.unreadCount(1))).toBeInTheDocument(),
    );
    // O'qilmagan qator nuqtacha bilan belgilanadi — bittasi o'qilgan.
    expect(screen.getAllByLabelText(NOTIFICATIONS.unreadDot)).toHaveLength(1);
    expect(screen.queryByText(NOTIFICATIONS.empty)).toBeNull();
  });
});
