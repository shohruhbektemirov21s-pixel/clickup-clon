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

/**
 * Marketing visuallari uchun ishlatiladigan statik ma'lumotlar. Hech qanday
 * rasm yuklanmaydi — mahsulot ko'rinishi to'liq HTML/CSS bilan chiziladi.
 */

type Person = { initials: string; className: string };

const PEOPLE: Record<string, Person> = {
  demo: { initials: "DA", className: "bg-primary text-white" },
  aziz: { initials: "AZ", className: "bg-brand-blue text-black/75" },
  jasur: { initials: "JA", className: "bg-brand-green text-black/75" },
  malika: { initials: "MA", className: "bg-brand-pink text-white" },
  nodira: { initials: "NO", className: "bg-brand-yellow text-black/75" },
};

const STATUS_DOT = {
  open: "bg-status-open",
  active: "bg-status-active",
  closed: "bg-status-closed",
} as const;

const PRIORITY_LABEL = {
  urgent: { text: "Shoshilinch", className: "fill-priority-urgent text-priority-urgent" },
  high: { text: "Yuqori", className: "fill-priority-high text-priority-high" },
  normal: { text: "O'rta", className: "fill-priority-normal text-priority-normal" },
} as const;

type PreviewTask = {
  title: string;
  status: keyof typeof STATUS_DOT;
  priority?: keyof typeof PRIORITY_LABEL;
  due: string;
  people: (keyof typeof PEOPLE)[];
  done?: boolean;
};

const TASKS: PreviewTask[] = [
  {
    title: "Taklif tokenini ro'yxatdan o'tish oqimiga ulash",
    status: "active",
    priority: "urgent",
    due: "12-avg",
    people: ["demo", "aziz"],
  },
  {
    title: "Rol × huquq matritsasiga saqlash tugmasi",
    status: "active",
    priority: "high",
    due: "13-avg",
    people: ["malika"],
  },
  {
    title: "Vazifa panelida fayl biriktirish",
    status: "open",
    priority: "normal",
    due: "15-avg",
    people: ["jasur", "nodira"],
  },
  {
    title: "Doskada ustunlar orasida sudrash",
    status: "open",
    due: "18-avg",
    people: ["aziz"],
  },
  {
    title: "Presence indikatori — kim onlayn",
    status: "closed",
    due: "09-avg",
    people: ["demo", "malika", "jasur"],
    done: true,
  },
];

const SIDEBAR: { label: string; dot: string; count: number; locked?: boolean }[] = [
  { label: "Mahsulot", dot: "bg-primary", count: 12 },
  { label: "Dizayn", dot: "bg-brand-pink", count: 7 },
  { label: "Marketing", dot: "bg-brand-blue", count: 4 },
  { label: "Yopiq bo'lim", dot: "bg-brand-yellow", count: 3, locked: true },
];

function AvatarStack({ people }: { people: (keyof typeof PEOPLE)[] }) {
  return (
    <div className="flex -space-x-1.5">
      {people.map((key) => {
        const person = PEOPLE[key];
        return (
          <span
            key={key}
            className={`inline-flex size-5 items-center justify-center rounded-full text-[9px] font-semibold ring-2 ring-card ${person.className}`}
          >
            {person.initials}
          </span>
        );
      })}
    </div>
  );
}

/**
 * Qahramon bo'limi ostidagi «skrinshot»: yon panel + vazifa qatorlari + status
 * nuqtalari + avatar to'plami. Butunlay dekorativ.
 */
export function AppPreview() {
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
          <span className="size-2.5 rounded-full bg-status-closed/70" />
        </span>
        <span className="ml-2 hidden flex-1 items-center gap-1.5 truncate rounded-md border bg-background px-2 py-1 font-mono text-[10px] text-muted-foreground sm:flex">
          clickish.app/w/1/l/4
        </span>
        <span className="ml-auto flex items-center gap-2 text-muted-foreground sm:ml-0">
          <Search className="size-3.5" />
          <Bell className="size-3.5" />
          <AvatarStack people={["demo", "aziz", "malika"]} />
        </span>
      </div>

      <div className="flex">
        {/* Yon panel */}
        <div className="hidden w-52 shrink-0 border-r bg-muted/20 p-3 sm:block">
          <div className="mb-3 flex items-center gap-2 rounded-md border bg-background px-2 py-1.5">
            <span className="flex size-5 items-center justify-center rounded bg-primary text-[10px] font-bold text-primary-foreground">
              C
            </span>
            <span className="text-xs font-semibold">Clickish jamoasi</span>
          </div>
          <p className="mb-2 px-1 text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
            Bo&apos;limlar
          </p>
          <ul className="space-y-0.5">
            {SIDEBAR.map((space, i) => (
              <li key={space.label}>
                <span
                  className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-xs ${
                    i === 0 ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground"
                  }`}
                >
                  <ChevronRight className="size-3 opacity-60" />
                  <span className={`size-2 rounded-[3px] ${space.dot}`} />
                  <span className="truncate">{space.label}</span>
                  {space.locked ? <Lock className="size-2.5 shrink-0 opacity-70" /> : null}
                  <span className="ml-auto text-[10px] opacity-70">{space.count}</span>
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground">
            <Plus className="size-3" />
            Bo&apos;lim qo&apos;shish
          </div>
        </div>

        {/* Asosiy panel */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 border-b px-3 py-2">
            <FolderTree className="size-3.5 text-muted-foreground" />
            <span className="truncate text-xs font-semibold">Sprint 4 — Ro&apos;yxat</span>
            <span className="ml-2 hidden gap-1 sm:flex">
              <span className="rounded-md bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                Ro&apos;yxat
              </span>
              <span className="rounded-md px-2 py-0.5 text-[10px] text-muted-foreground">
                Doska
              </span>
            </span>
            <span className="ml-auto flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <span className="size-1.5 animate-pulse rounded-full bg-status-closed" />
              3 kishi onlayn
            </span>
          </div>

          <ul className="divide-y">
            {TASKS.map((task) => (
              <li
                key={task.title}
                className="flex items-center gap-2 px-3 py-2.5 first:bg-primary/[0.04]"
              >
                <GripVertical className="size-3 shrink-0 text-muted-foreground/40" />
                <span className={`size-2 shrink-0 rounded-full ${STATUS_DOT[task.status]}`} />
                <span
                  className={`min-w-0 flex-1 truncate text-xs ${
                    task.done ? "text-muted-foreground line-through" : "text-foreground"
                  }`}
                >
                  {task.title}
                </span>
                {task.priority ? (
                  <span className="hidden items-center gap-1 text-[10px] font-medium text-muted-foreground md:inline-flex">
                    <Flag className={`size-2.5 ${PRIORITY_LABEL[task.priority].className}`} />
                    {PRIORITY_LABEL[task.priority].text}
                  </span>
                ) : null}
                <span className="hidden text-[10px] text-muted-foreground sm:inline">
                  {task.due}
                </span>
                <AvatarStack people={task.people} />
              </li>
            ))}
          </ul>

          <div className="flex items-center gap-2 px-3 py-2 text-[11px] text-muted-foreground">
            <Plus className="size-3" />
            Vazifa qo&apos;shish
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
            ✔ Container clickish-db Healthy{"\n"} ✔ Container clickish-redis Healthy{"\n"} ✔
            Container clickish-backend Started{"\n"} ✔ Container clickish-frontend Started{"\n"}
          </span>
          <span className="text-primary">$ </span>
          <span className="text-foreground">
            docker compose exec backend python manage.py seed_demo
          </span>
          {"\n"}
          <span className="text-brand-green">
            {" "}
            Demo ma&apos;lumot tayyor → http://localhost:3000
          </span>
        </code>
      </pre>
    </div>
  );
}
