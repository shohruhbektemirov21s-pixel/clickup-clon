import {
  Bell,
  ChevronRight,
  Flag,
  FolderTree,
  GripVertical,
  Lock,
  Plus,
  Search,
  Terminal,
} from "lucide-react";
import { APP, COMMON, LANDING_PREVIEW, PRIORITY_LABEL, STATUS_BG_CLASS } from "@/i18n/uz";
import type { Priority, ShowcasePerson, ShowcaseWorkspace } from "@/types/api";

/**
 * Qahramon bo'limi ostidagi «skrinshot». Barcha qatorlar bazadan keladi
 * (`GET public/showcase/`) — bu faylda namunaviy ma'lumot yo'q. Rasm ham
 * yuklanmaydi: ko'rinish to'liq HTML/CSS bilan chiziladi.
 */

/** Bayroqcha to'ldirilgan holda chiziladi — matn sinfi `PRIORITY_CLASS` da. */
const PRIORITY_FILL: Record<Exclude<Priority, "none">, string> = {
  urgent: "fill-priority-urgent text-priority-urgent",
  high: "fill-priority-high text-priority-high",
  medium: "fill-priority-medium text-priority-medium",
  low: "fill-priority-low text-priority-low",
};

function AvatarStack({ people }: { people: ShowcasePerson[] }) {
  return (
    <div className="flex -space-x-1.5">
      {people.map((person, i) => (
        <span
          key={`${person.initials}-${i}`}
          style={{ backgroundColor: person.color }}
          className="inline-flex size-5 items-center justify-center rounded-full text-[9px] font-semibold text-white ring-2 ring-card"
        >
          {person.initials}
        </span>
      ))}
    </div>
  );
}

export function AppPreview({ data }: { data: ShowcaseWorkspace | null }) {
  // Backend yetib kelmadi yoki namoyish ish maydoni sozlanmagan: oyna
  // ramkasi qoladi, ichi esa bo'sh holat matni bilan almashadi.
  const spaces = data?.spaces ?? [];
  const tasks = data?.tasks ?? [];

  return (
    <div
      aria-hidden
      className="overflow-hidden rounded-xl border bg-card shadow-2xl shadow-black/10 ring-1 ring-black/[0.04] dark:shadow-black/60 dark:ring-white/[0.06]"
    >
      {/* Oyna sarlavhasi */}
      <div className="flex items-center gap-2 border-b bg-muted/40 px-3 py-2">
        <span className="flex gap-1.5">
          <span className="size-2.5 rounded-full bg-priority-urgent/70" />
          <span className="size-2.5 rounded-full bg-priority-high/70" />
          <span className="size-2.5 rounded-full bg-status-done/70" />
        </span>
        <span className="ml-2 hidden flex-1 items-center gap-1.5 truncate rounded-md border bg-background px-2 py-1 font-mono text-[10px] text-muted-foreground sm:flex">
          {LANDING_PREVIEW.addressBar}
        </span>
        <span className="ml-auto flex items-center gap-2 text-muted-foreground sm:ml-0">
          <Search className="size-3.5" />
          <Bell className="size-3.5" />
          <AvatarStack people={tasks[0]?.people ?? []} />
        </span>
      </div>

      <div className="flex">
        {/* Yon panel */}
        <div className="hidden w-52 shrink-0 border-r bg-muted/20 p-3 sm:block">
          <div className="mb-3 flex items-center gap-2 rounded-md border bg-background px-2 py-1.5">
            <span className="flex size-5 items-center justify-center rounded bg-primary text-[10px] font-bold text-primary-foreground">
              {APP.brandInitial}
            </span>
            <span className="truncate text-xs font-semibold">{data?.name ?? "Ish maydoni"}</span>
          </div>
          <p className="mb-2 px-1 text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
            {LANDING_PREVIEW.spaces}
          </p>
          <ul className="space-y-0.5">
            {spaces.map((space, i) => (
              <li key={space.name}>
                <span
                  className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-xs ${
                    i === 0 ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground"
                  }`}
                >
                  <ChevronRight className="size-3 opacity-60" />
                  <span
                    className="size-2 rounded-[3px]"
                    style={{ backgroundColor: space.color }}
                  />
                  <span className="truncate">{space.name}</span>
                  {space.locked ? <Lock className="size-2.5 shrink-0 opacity-70" /> : null}
                  <span className="ml-auto text-[10px] opacity-70">{space.count}</span>
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground">
            <Plus className="size-3" />
            {LANDING_PREVIEW.addSpace}
          </div>
        </div>

        {/* Asosiy panel */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 border-b px-3 py-2">
            <FolderTree className="size-3.5 text-muted-foreground" />
            <span className="truncate text-xs font-semibold">
              {data?.list_name ?? COMMON.list}
            </span>
            <span className="ml-2 hidden gap-1 sm:flex">
              <span className="rounded-md bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                {COMMON.list}
              </span>
              <span className="rounded-md px-2 py-0.5 text-[10px] text-muted-foreground">
                {COMMON.board}
              </span>
            </span>
            {data ? (
              <span className="ml-auto flex items-center gap-1.5 text-[10px] text-muted-foreground">
                <span className="size-1.5 animate-pulse rounded-full bg-status-done" />
                {data.member_count} a&apos;zo
              </span>
            ) : null}
          </div>

          {tasks.length ? (
            <ul className="divide-y">
              {tasks.map((task) => (
                <li
                  key={task.title}
                  className="flex items-center gap-2 px-3 py-2.5 first:bg-primary/[0.04]"
                >
                  <GripVertical className="size-3 shrink-0 text-muted-foreground/40" />
                  <span className={`size-2 shrink-0 rounded-full ${STATUS_BG_CLASS[task.status]}`} />
                  <span
                    className={`min-w-0 flex-1 truncate text-xs ${
                      task.done ? "text-muted-foreground line-through" : "text-foreground"
                    }`}
                  >
                    {task.title}
                  </span>
                  {task.priority !== "none" ? (
                    <span className="hidden items-center gap-1 text-[10px] font-medium text-muted-foreground md:inline-flex">
                      <Flag className={`size-2.5 ${PRIORITY_FILL[task.priority]}`} />
                      {PRIORITY_LABEL[task.priority]}
                    </span>
                  ) : null}
                  {task.due ? (
                    <span className="hidden text-[10px] text-muted-foreground sm:inline">
                      {task.due}
                    </span>
                  ) : null}
                  <AvatarStack people={task.people} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-10 text-center text-xs text-muted-foreground">
              {LANDING_PREVIEW.emptyList}
            </p>
          )}

          <div className="flex items-center gap-2 border-t px-3 py-2 text-[11px] text-muted-foreground">
            <Plus className="size-3" />
            {COMMON.addTask}
          </div>
        </div>
      </div>
    </div>
  );
}

/** «Bir buyruq bilan» bo'limidagi terminal bloki. */
export function TerminalBlock() {
  return (
    <div
      aria-hidden
      className="overflow-hidden rounded-xl border bg-card shadow-lg shadow-black/5 dark:shadow-black/40"
    >
      <div className="flex items-center gap-2 border-b bg-muted/40 px-3 py-2">
        <Terminal className="size-3.5 text-muted-foreground" />
        <span className="font-mono text-[11px] text-muted-foreground">bash</span>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[11px] leading-relaxed sm:text-xs">
        <code>
          <span className="text-muted-foreground">
            # PostgreSQL 16 + Redis 7 + backend + frontend{"\n"}
          </span>
          <span className="text-primary">$ </span>
          <span className="text-foreground">docker compose up -d --build</span>
          {"\n"}
          <span className="text-muted-foreground">
            {" "}
            ✔ Container uzwork-db Healthy{"\n"} ✔ Container uzwork-redis Healthy{"\n"} ✔
            Container uzwork-backend Started{"\n"} ✔ Container uzwork-frontend Started{"\n"}
          </span>
          <span className="text-primary">$ </span>
          <span className="text-foreground">
            docker compose exec backend python manage.py migrate
          </span>
          {"\n"}
          <span className="text-brand-green"> Ilova tayyor → http://localhost:3000</span>
        </code>
      </pre>
    </div>
  );
}
