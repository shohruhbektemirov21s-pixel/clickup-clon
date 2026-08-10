import { Check, GripVertical, Lock, Minus } from "lucide-react";

/**
 * «Nima uchun» bo'limidagi navbatlashuvchi bloklarning vizuallari.
 * Barchasi dekorativ — matn mazmuni yonidagi paragraflarda takrorlanadi.
 */

const ROLES = ["Egasi", "Admin", "A'zo", "Mehmon"] as const;

const MATRIX: { code: string; allow: boolean[] }[] = [
  { code: "task.create", allow: [true, true, true, false] },
  { code: "task.delete", allow: [true, true, false, false] },
  { code: "member.invite", allow: [true, true, false, false] },
  { code: "role.permission.update", allow: [true, false, false, false] },
];

/** 48 ta ruxsat kodidan to'rttasi — rol × huquq matritsasi ko'rinishi. */
export function PermissionMatrixVisual() {
  return (
    <div
      aria-hidden
      className="overflow-hidden rounded-xl border bg-card shadow-lg shadow-black/5 dark:shadow-black/40"
    >
      <div className="flex items-center gap-2 border-b bg-muted/40 px-4 py-2.5">
        <Lock className="size-3.5 text-muted-foreground" />
        <span className="text-xs font-medium">Rol × huquq matritsasi</span>
        <span className="ml-auto font-mono text-[10px] text-muted-foreground">48 kod</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[22rem] text-left">
          <thead>
            <tr className="border-b">
              <th className="px-4 py-2 text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
                Ruxsat kodi
              </th>
              {ROLES.map((role) => (
                <th
                  key={role}
                  className="px-2 py-2 text-center text-[10px] font-medium tracking-wide text-muted-foreground uppercase"
                >
                  {role}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {MATRIX.map((row) => (
              <tr key={row.code}>
                <td className="px-4 py-2 font-mono text-[11px] text-foreground">{row.code}</td>
                {row.allow.map((allowed, i) => (
                  <td key={ROLES[i]} className="px-2 py-2 text-center">
                    {allowed ? (
                      <Check
                        className={`mx-auto size-3.5 ${i === 0 ? "text-muted-foreground" : "text-status-closed"}`}
                      />
                    ) : (
                      <Minus className="mx-auto size-3.5 text-muted-foreground/40" />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t bg-muted/30 px-4 py-2 text-[11px] text-muted-foreground">
        Egasi ustuni qulflangan — bazadagi cheklov buni kafolatlaydi.
      </p>
    </div>
  );
}

const FEED = [
  {
    who: "Aziz",
    what: "«Taklif tokeni» vazifasini Bajarilmoqda ga o'tkazdi",
    when: "hozir",
    tone: "bg-status-active",
  },
  {
    who: "Malika",
    what: "izoh qoldirdi: «Matritsa saqlanmayapti»",
    when: "12 s",
    tone: "bg-brand-pink",
  },
  {
    who: "Jasur",
    what: "spec.pdf faylini biriktirdi",
    when: "48 s",
    tone: "bg-brand-green",
  },
  {
    who: "Nodira",
    what: "ro'yxatga qo'shildi",
    when: "1 daq",
    tone: "bg-brand-yellow",
  },
];

/** Presence + faoliyat tasmasi ko'rinishi. */
export function ActivityFeedVisual() {
  return (
    <div
      aria-hidden
      className="overflow-hidden rounded-xl border bg-card shadow-lg shadow-black/5 dark:shadow-black/40"
    >
      <div className="flex items-center gap-2 border-b bg-muted/40 px-4 py-2.5">
        <span className="relative flex size-2">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-status-closed opacity-70" />
          <span className="relative inline-flex size-2 rounded-full bg-status-closed" />
        </span>
        <span className="text-xs font-medium">Faoliyat tasmasi</span>
        <span className="ml-auto font-mono text-[10px] text-muted-foreground">
          ws://…/ws/list/4/
        </span>
      </div>
      <ul className="divide-y">
        {FEED.map((item) => (
          <li key={item.who} className="flex items-start gap-3 px-4 py-3">
            <span className={`mt-1.5 size-2 shrink-0 rounded-full ${item.tone}`} />
            <p className="min-w-0 flex-1 text-xs leading-relaxed text-muted-foreground">
              <span className="font-medium text-foreground">{item.who}</span> {item.what}
            </p>
            <span className="shrink-0 font-mono text-[10px] text-muted-foreground/70">
              {item.when}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const ORDER_ROWS = [
  { title: "Ro'yxat sarlavhasini tahrirlash", position: "1.000", state: "idle" },
  { title: "Doskada sudrash animatsiyasi", position: "1.500", state: "dragging" },
  { title: "Filtrlar paneli", position: "2.000", state: "idle" },
];

/** Kasr pozitsiyalar bilan sudrab tartiblash ko'rinishi. */
export function OrderingVisual() {
  return (
    <div
      aria-hidden
      className="overflow-hidden rounded-xl border bg-card shadow-lg shadow-black/5 dark:shadow-black/40"
    >
      <div className="flex items-center gap-2 border-b bg-muted/40 px-4 py-2.5">
        <GripVertical className="size-3.5 text-muted-foreground" />
        <span className="text-xs font-medium">Sudrab tartiblash</span>
        <span className="ml-auto font-mono text-[10px] text-muted-foreground">
          PATCH /tasks/42/move/
        </span>
      </div>
      <ul className="space-y-2 p-4">
        {ORDER_ROWS.map((row) => {
          const dragging = row.state === "dragging";
          return (
            <li
              key={row.title}
              className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 ${
                dragging
                  ? "border-primary/50 bg-primary/5 shadow-lg shadow-primary/15 sm:translate-x-3"
                  : "bg-background"
              }`}
            >
              <GripVertical
                className={`size-3.5 shrink-0 ${dragging ? "text-primary" : "text-muted-foreground/40"}`}
              />
              <span className="min-w-0 flex-1 truncate text-xs">{row.title}</span>
              <span
                className={`shrink-0 rounded-md px-1.5 py-0.5 font-mono text-[10px] ${
                  dragging ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"
                }`}
              >
                {row.position}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="border-t bg-muted/30 px-4 py-2 text-[11px] text-muted-foreground">
        Faqat bitta qator yangilanadi — jadval qayta raqamlanmaydi.
      </p>
    </div>
  );
}
