/**
 * Kanban optimistik yozuv va XATODA ORTGA QAYTISH (ADR 0013, reja §17.5).
 *
 * Nima isbotlanadi: doskadagi kartani sudrash (`useMoveTask`) va maydonni
 * o'zgartirish (`useUpdateTask`) keshni DARHOL yangilaydi, so'rov yiqilsa esa
 * kesh **avvalgi holatiga bit-ma-bit qaytadi** — ekranda "ko'chdi, keyin
 * sekin orqaga sakradi" holati qolmaydi.
 *
 * Haqiqiy `QueryClient` ishlatiladi (mock emas): tekshirilayotgan narsa aynan
 * `onMutate`/`onError` konteksti bilan keshning o'zaro ishlashi. Faqat HTTP
 * qatlami (`@/lib/api`) va toast mock qilingan.
 */

import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { keys } from "@/lib/keys";
import type { GroupedTasksResponse, MoveTaskResponse, Task, TaskStatus } from "@/types/api";

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
const { useMoveTask, useUpdateTask } = await import("@/hooks/mutations");

const LIST_ID = "list-1";

function makeTask(id: string, status: TaskStatus, position: string): Task {
  return {
    id,
    list_id: LIST_ID,
    title: `Vazifa ${id}`,
    description_html: null,
    description_json: null,
    status,
    priority: "none",
    position,
    due_date: null,
    start_date: null,
    time_estimate_minutes: null,
    archived: false,
    is_deleted: false,
    completed_at: null,
    comment_count: 0,
    attachment_count: 0,
    assignees: [],
    watchers: [],
    tags: [],
    created_by: null,
    updated_by: null,
    created_at: "2026-08-01T10:00:00+05:00",
    updated_at: "2026-08-01T10:00:00+05:00",
  };
}

function makeGrouped(): GroupedTasksResponse {
  return {
    group_by: "status",
    groups: [
      {
        status: "todo",
        label: "Bajarilishi kerak",
        count: 2,
        tasks: [makeTask("t1", "todo", "a0"), makeTask("t2", "todo", "a1")],
      },
      { status: "in_progress", label: "Jarayonda", count: 0, tasks: [] },
      { status: "review", label: "Tekshiruvda", count: 0, tasks: [] },
      { status: "done", label: "Bajarildi", count: 0, tasks: [] },
    ],
  };
}

/** Guruhdagi vazifa id'lari — tekshiruvlar shu ko'rinishda o'qiladi. */
function idsIn(data: GroupedTasksResponse | undefined, status: TaskStatus): string[] {
  return data?.groups.find((g) => g.status === status)?.tasks.map((t) => t.id) ?? [];
}

let queryClient: QueryClient;

function wrapper({ children }: { children: React.ReactNode }) {
  // MemoryRouter — `useRouteWorkspaceId()` (React Router'ning `useParams`)
  // uchun. Marshrut mos kelmagani uchun id `null` bo'ladi va ish maydoni
  // rollup taymeri ishga tushmaydi; test aynan keshning o'zini o'lchaydi.
  return (
    <MemoryRouter initialEntries={["/w/ws-1/l/list-1"]}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
});

describe("useMoveTask — doska optimistik ko'chirishi", () => {
  it("kartani darhol ko'chiradi va server xatosida keshni qaytaradi", async () => {
    const before = makeGrouped();
    queryClient.setQueryData(keys.tasksGrouped(LIST_ID), makeGrouped());

    let reject: (err: unknown) => void = () => {};
    vi.mocked(api.patch).mockReturnValueOnce(
      new Promise((_resolve, rej) => {
        reject = rej;
      }),
    );

    const { result } = renderHook(() => useMoveTask(LIST_ID), { wrapper });

    result.current.mutate({
      taskId: "t1",
      toStatus: "in_progress",
      toIndex: 0,
      beforeId: null,
      afterId: null,
    });

    // 1-bosqich: javob kelmasdan turib karta yangi ustunda.
    await waitFor(() => {
      const data = queryClient.getQueryData<GroupedTasksResponse>(
        keys.tasksGrouped(LIST_ID),
      );
      expect(idsIn(data, "in_progress")).toEqual(["t1"]);
      expect(idsIn(data, "todo")).toEqual(["t2"]);
    });

    // 2-bosqich: so'rov yiqiladi.
    reject(new Error("network down"));

    await waitFor(() => expect(result.current.isError).toBe(true));

    // 3-bosqich: kesh AYNAN avvalgi holat.
    expect(queryClient.getQueryData(keys.tasksGrouped(LIST_ID))).toEqual(before);
  });

  it("muvaffaqiyatda serverdan kelgan vazifani yozadi", async () => {
    queryClient.setQueryData(keys.tasksGrouped(LIST_ID), makeGrouped());

    const moved: MoveTaskResponse = {
      ...makeTask("t1", "in_progress", "b0"),
      rebalanced: false,
    };
    vi.mocked(api.patch).mockResolvedValueOnce(moved);

    const { result } = renderHook(() => useMoveTask(LIST_ID), { wrapper });
    result.current.mutate({
      taskId: "t1",
      toStatus: "in_progress",
      toIndex: 0,
      beforeId: null,
      afterId: null,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const data = queryClient.getQueryData<GroupedTasksResponse>(
      keys.tasksGrouped(LIST_ID),
    );
    expect(idsIn(data, "in_progress")).toEqual(["t1"]);
    // `rebalanced` — javob bayrog'i, vazifa maydoni emas: keshga tushmasin.
    expect(queryClient.getQueryData<Task>(keys.task("t1"))).not.toHaveProperty(
      "rebalanced",
    );
  });
});

describe("useUpdateTask — maydonni optimistik yangilash", () => {
  it("xatoda ham guruhlangan keshni, ham vazifa keshini qaytaradi", async () => {
    const beforeGrouped = makeGrouped();
    const beforeTask = makeTask("t1", "todo", "a0");
    queryClient.setQueryData(keys.tasksGrouped(LIST_ID), makeGrouped());
    queryClient.setQueryData(keys.task("t1"), makeTask("t1", "todo", "a0"));

    let reject: (err: unknown) => void = () => {};
    vi.mocked(api.patch).mockReturnValueOnce(
      new Promise((_resolve, rej) => {
        reject = rej;
      }),
    );

    const { result } = renderHook(() => useUpdateTask(LIST_ID), { wrapper });
    result.current.mutate({ taskId: "t1", patch: { title: "Yangi sarlavha" } });

    await waitFor(() => {
      expect(queryClient.getQueryData<Task>(keys.task("t1"))?.title).toBe(
        "Yangi sarlavha",
      );
    });

    reject(new Error("500"));
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(queryClient.getQueryData(keys.tasksGrouped(LIST_ID))).toEqual(beforeGrouped);
    expect(queryClient.getQueryData(keys.task("t1"))).toEqual(beforeTask);
  });
});
