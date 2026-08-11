# Clickish — UI Specification (MVP)

> **Brend eslatmasi.** Mahsulot nomi endi **UzWork**. Bu fayl tarixiy hujjat —
> undagi "Clickish" / "ClickUp clone" iboralari yozilgan paytdagi holatni
> aks ettiradi va o'zgartirilmagan. Amaldagi brend chegarasi:
> `docs/adr/0014-mahsulot-nomi.md`.

> # ⛔ SUPERSEDED — HISTORICAL, NOT BINDING
>
> **Do not implement from this document, and do not cite it in review.** It was written on
> 2026-08-07 against a plan the product then diverged from, and it has not been maintained since.
> `API_CONTRACT.md` **R31** demotes it: where this file disagrees with `docs/API_CONTRACT.md` or with
> the code, **it loses, silently and always**. Rewriting 193 KB to match reality is not worth it, so
> it is being kept as a design-history record and marked instead. It is still genuinely useful for
> *design intent* — spacing, wireframes, interaction detail, drag & drop semantics, accessibility
> notes — and those parts have largely survived contact with the implementation.
>
> ## What is stale (verified against the code on 2026-08-10)
>
> | Area | This document says | Reality |
> |---|---|---|
> | **CSS framework** | Tailwind **v3**: a `tailwind.config.ts` (§2.2) and `hsl(var(--x) / <alpha-value>)` tokens (26 occurrences), `@tailwind base/components/utilities` (§2.3) | Tailwind **v4**, CSS-first. **There is no `tailwind.config.*` file anywhere in `frontend/`.** `frontend/src/app/globals.css` starts `@import "tailwindcss"` and declares tokens in `@theme`. `<alpha-value>` is a v3-only token and is meaningless in v4. The token *values* are still broadly right; the mechanism is not. |
> | **UI copy language** | **English** throughout every wireframe (`Log in`, `Add a description…`, `Search members…`) | The shipped product is **entirely Uzbek** (`<html lang="uz">`). Treat every string here as a placeholder for the Uzbek copy in the components. |
> | **WebSocket auth** | `ws://<host>/ws/list/{list_id}/?token=<access>` (TL;DR) | `?ticket=<opaque>` — a single-use 30-second handshake ticket from `POST /api/v1/realtime/ticket/`. `?token=` still works but is **deprecated** (it puts a full access token in every proxy log). See `API_CONTRACT.md` §15.1. |
> | **WebSocket channels** | one list socket only | Two channels: `/ws/list/{list_id}/` **and** `/ws/workspaces/{workspace_id}/`, over four server-side groups. Frames are space-scoped and never carry `email`. `API_CONTRACT.md` §15. |
> | **Permission model** | roles gate the UI: "`owner > admin > member > guest` gate UI affordances" (TL;DR) | The UI gates on **permission codes** from `GET workspaces/{id}/my-permissions/` (`frontend/src/lib/permissions.ts::can` / `canInSpace`), because the role→permission matrix is **editable per workspace**. Space-local `manager`/`viewer` access has no representation here at all. As of 2026-08-10 exactly one component still branches on `my_role` (`shell/workspace-home.tsx`); that is the tail of a migration, not the design. |
> | **Framework version** | Next.js 15 (doc control, §3.1) | Next **16.3.0**, React **19.2.8**. |
> | **Drag & drop deps** | mandates `@dnd-kit/accessibility` | Not a dependency. Shipped: `@dnd-kit/core`, `/sortable`, `/modifiers`, `/utilities`. |
> | **Task detail route** | intercepting route `/w/[id]/l/[listId]/t/[taskId]` with an `@panel` slot | Shipped as a **`?task=` search param** on the list page — same slide-over, different routing. |
> | **Error/loading boundaries** | §3.2 mandates `loading.tsx` / `error.tsx` / `not-found.tsx` / `global-error.tsx` per segment | **None of these files exist.** |
>
> ## Screens that shipped and are specified NOWHERE here
>
> This document contains **zero** occurrences of `attachment`, `profession`, `ticket`,
> `permission matrix` or `member profile`. The following are live product surfaces with no spec:
>
> - **Permission matrix editor** — `/w/[id]/settings/permissions` (`components/settings/permissions-matrix.tsx`)
> - **Member profile** — `/w/[id]/u/[userId]` (role, tenure, counters, per-space breakdown)
> - **Space members / PM assignment** — `/w/[id]/s/[spaceId]/members`
> - **Task attachments** — upload, list and delete inside the task panel
> - **Workspace activity feed** — `GET workspaces/{id}/activity/`
> - **Demo login** — the read-only demo account entry point
> - **Marketing landing page** — `components/marketing/`
>
> Conversely, several routes specified in §3.1 were never built (`/settings/general`,
> `/settings/tags`, the two status-editor routes, `/settings/account`, `/logout`).
>
> ## The document is also incomplete
>
> It **ends at §6.8** (drag & drop). §7–§18 do not exist, yet §21 of the doc-control block cites
> "§10" for the component inventory and the TL;DR cites "§5" for query keys. Any cross-reference in
> this file to a section above §6 is a dangling pointer.
>
> ## What to read instead
>
> | For | Read |
> |---|---|
> | Endpoints, payloads, permissions, WebSocket frames | **`docs/API_CONTRACT.md`** (binding) |
> | The permission model in depth | `docs/DESIGN_PERMISSIONS.md` |
> | Persistence, field names and types | `docs/DATA_MODEL.md` |
> | What the UI actually does | **the components under `frontend/src/`** — they are the only current UI truth |

Binding front-end specification. Derived from and subordinate to the **Decision Sheet** and `docs/API_CONTRACT.md`.
Every field name, role, priority value, status type, endpoint, WebSocket event and design token used here is copied verbatim from the Decision Sheet.

## Doc control

| Field | Value |
| --- | --- |
| Document | `docs/UI_SPEC.md` |
| Product | Clickish (ClickUp clone MVP) |
| Version | 1.0.0 (frozen) |
| Status | **SUPERSEDED — historical, not binding** (`API_CONTRACT.md` R31). Frozen 2026-08-10. |
| Date | 2026-08-07 (last substantive edit); superseded 2026-08-10 |
| Owner | Product Design + Frontend Architecture |
| Authority | **None.** Formerly "Decision Sheet > `docs/API_CONTRACT.md` > this document > implementation". `docs/API_CONTRACT.md` and the code both outrank it now. |
| Stack | ~~Next.js 15, Tailwind CSS (v3 config)~~ → **Next.js 16.3, React 19.2, Tailwind v4 (CSS-first, no config file)**, TypeScript, shadcn/ui, TanStack Query, Zustand, native WebSocket |
| Drag & drop library | **dnd-kit** (`@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/modifiers`, `@dnd-kit/accessibility`) — chosen, no alternative permitted |
| Icon set | `lucide-react` (ships with shadcn/ui) |
| Screens specced | 12 (S1–S12) |
| Reusable components | 68 (see §10) |
| Supersedes | none |
| Superseded by | `docs/API_CONTRACT.md` (contract) + `frontend/src/` (UI truth) |

## TL;DR

* Clickish is a **single-workspace-at-a-time** app shell: fixed top bar (56px), fixed left sidebar (**260px**) containing the `Workspace > Space > Folder > List` hierarchy tree, and a main panel that renders either the **List view** or the **Board (Kanban) view** of one `TaskList`.
* Task detail is **never a full page navigation**; it is a **720px slide-over panel from the right** at route `/w/[workspaceId]/l/[listId]/t/[taskId]`, rendered as an intercepting route so the underlying list/board stays mounted.
* Server state lives **exclusively** in TanStack Query, keyed by the canonical keys in §5. UI state (sidebar open, active view, panel state, drag state, filter draft) lives in Zustand. There is no third state container.
* Drag & drop is **optimistic**: compute neighbours in the client, send `before_id`/`after_id` to `PATCH /api/v1/tasks/{id}/move/`, reconcile with the server-returned `position`, roll back on error. Cross-column drops also change `status_id`.
* Realtime is a native `WebSocket` to `ws://<host>/ws/list/{list_id}/?token=<access>` with exponential-backoff reconnect and a full refetch on resume. Own echoes are suppressed with `X-Client-Id` matched against `actor.client_id`. — **STALE:** auth is now `?ticket=<opaque>` (single-use, 30 s) and there is a second `/ws/workspaces/{id}/` channel. Echo suppression is still correct. See `API_CONTRACT.md` §15.
* Design system is shadcn/ui over Tailwind with the ClickUp-purple `#7B68EE` primary, HSL-channel CSS variables, and a `dark` class strategy. Brand purple does not invert.
* Roles `owner > admin > member > guest` gate UI affordances; the client hides what the API would reject, and always still handles a `403 permission_denied` envelope. — **STALE:** gating is by **permission code** from `GET workspaces/{id}/my-permissions/`, not by role name, because the role→permission matrix is editable per workspace. "Still handles the `403`" remains correct and is still mandatory.

---

# 2. Design tokens

All values below are copied **exactly** from the Decision Sheet. Hex is the source of truth; the HSL triplets are the same colours expressed in shadcn/ui channel form (`H S% L%`, no `hsl()` wrapper) so they can be composed with `hsl(var(--token) / <alpha-value>)`.

## 2.1 Token table

### Brand & semantic colour

| Token | Light value | Dark value | Usage |
| --- | --- | --- | --- |
| `--primary` | `#7B68EE` / `248 79% 67%` | `#7B68EE` / `248 79% 67%` (unchanged) | Primary buttons, active nav item, focus ring, selected state, brand marks |
| `--primary-hover` | `#6B58DE` / `248 67% 61%` | `#6B58DE` / `248 67% 61%` (unchanged) | Hover/active of primary buttons and links |
| `--primary-fg` | `#FFFFFF` / `0 0% 100%` | `#FFFFFF` / `0 0% 100%` | Text/icon on primary fill |
| `--accent-pink` | `#FD71AF` / `333 97% 72%` | same | Tag chips, avatar fallback ring variant 1 |
| `--accent-blue` | `#49CCF9` / `195 94% 63%` | same | Info callouts, "watching" indicator, avatar variant 2 |
| `--accent-yellow` | `#FFC800` / `47 100% 50%` | same | Warning banner, due-today marker, avatar variant 3 |
| `--accent-green` | `#2ECD6F` / `145 63% 49%` | same | Success toast, connection-healthy dot, avatar variant 4 |
| `--danger` | `#E5484D` / `358 75% 59%` | same | Destructive buttons, inline field errors, overdue date, offline dot |

### Priority colours (`Task.priority`)

| Token | Priority value | Value | HSL | Usage |
| --- | --- | --- | --- | --- |
| `--priority-urgent` | `"urgent"` | `#F50000` | `0 100% 48%` | Priority flag icon, list-row flag column, board card flag |
| `--priority-high` | `"high"` | `#FFCC00` | `48 100% 50%` | idem |
| `--priority-normal` | `"normal"` | `#6FDDFF` | `194 100% 72%` | idem |
| `--priority-low` | `"low"` | `#D8D8D8` | `0 0% 85%` | idem |
| `--priority-none` | `"none"` | `#A0A0A0` | `0 0% 63%` | Default; rendered as an outline flag, not a filled one |

Sorting uses `priority_order` (urgent=1, high=2, normal=3, low=4, none=5) — the UI never sorts by the string.

### Status-type colours (`Status.type`)

| Token | Status type | Value | HSL | Usage |
| --- | --- | --- | --- | --- |
| `--status-open` | `open` | `#87909E` | `216 11% 57%` | Default dot/pill for open statuses when a `Status.color` is absent |
| `--status-active` | `active` | `#4194F6` | `212 91% 61%` | idem |
| `--status-closed` | `closed` | `#6BC950` | `107 53% 55%` | idem; closed tasks also get `line-through` on title |

> A `Status` carries its own `color` (hex) from the API. **`Status.color` always wins**; the status-type token is the fallback and is also used for the type legend in the Status-set editor (S11).

### Neutrals

| Token | Light value | Dark value | Usage |
| --- | --- | --- | --- |
| `--background` | `#FFFFFF` / `0 0% 100%` | `#16161A` / `240 8% 9%` | App canvas, main panel |
| `--surface` | `#F7F8F9` / `210 14% 97%` | `#1E1F25` / `231 10% 13%` | Sidebar, top bar, cards, board columns, popovers |
| `--border` | `#E8EAED` / `216 12% 92%` | `#2C2E36` / `228 10% 19%` | All 1px hairlines, dividers, input borders |
| `--foreground` | `#1F2937` / `215 28% 17%` | `#E7E9EE` / `223 17% 92%` | Primary text |
| `--muted-foreground` | `#6B7280` / `220 9% 46%` | `#9096A2` / `220 9% 60%` | Secondary text, placeholders, metadata, icon default |

### Spacing (4px base)

| Token | px | Usage |
| --- | --- | --- |
| `space-0` | 0 | reset |
| `space-2` | 2 | icon nudges, focus-ring offset |
| `space-4` | 4 | chip inner padding, tree indent step unit |
| `space-8` | 8 | icon↔label gap, board card inner gap |
| `space-12` | 12 | list-row horizontal padding, form field gap |
| `space-16` | 16 | card padding, panel section gap |
| `space-20` | 20 | board column padding |
| `space-24` | 24 | panel gutter, page gutter |
| `space-32` | 32 | section separation in settings |
| `space-40` | 40 | auth card inner padding |
| `space-48` | 48 | empty-state vertical padding |
| `space-64` | 64 | full-page empty state / hero |

### Radii

| Token | Value | Usage |
| --- | --- | --- |
| `rounded-sm` | 4px | chips, tags, checkboxes, small badges |
| `rounded-md` | 6px | inputs, buttons, list rows on hover |
| `rounded-lg` | 8px | board cards, popovers, dropdown menus |
| `rounded-xl` | 12px | dialogs, auth card, slide-over panel edge |
| `rounded-full` | 9999px | avatars, status dots, presence rings, pills |

### Typography — Inter var

| Token | Size / line-height | Weight | Usage |
| --- | --- | --- | --- |
| `text-xs` | 12px / 1.4 | 400–500 | Metadata, timestamps, breadcrumb, table headers |
| `text-13` | 13px / 1.4 | 400–500 | Sidebar tree items, board card title, list-row secondary |
| `text-sm` | 14px / 1.4 | 400–600 | **Body default**, list-row title, inputs, buttons |
| `text-base` | 16px / 1.4 | 400–600 | Task panel body, comment body |
| `text-lg` | 20px / 1.2 | 600 | Task title in panel, dialog title |
| `text-xl` | 24px / 1.2 | 600–700 | Screen headings (settings, auth) |
| `text-2xl` | 30px / 1.2 | 700 | Marketing/auth hero only |

Weights available: `400` regular, `500` medium, `600` semibold, `700` bold. Line-height **1.4 body**, **1.2 headings**.

### Fixed dimensions (binding)

| Token | Value | Applies to |
| --- | --- | --- |
| `--row-h-list` | **36px** | List view row height (S5) |
| `--card-min-h-board` | **68px** | Board card minimum height (S6) |
| `--sidebar-w` | **260px** | Left sidebar (S4) |
| `--panel-w-task` | **720px** | Task detail slide-over (S7) |
| `--topbar-h` | 56px | App chrome top bar |
| `--board-col-w` | 288px | Board column width (derived; not in Decision Sheet) |

### Elevation / shadows

| Token | Light value | Dark value | Usage |
| --- | --- | --- | --- |
| `shadow-sm` | `0 1px 2px 0 rgb(31 41 55 / 0.06)` | *none* → `1px` `--border` outline | Board card at rest, hoverable rows |
| `shadow-md` | `0 4px 12px -2px rgb(31 41 55 / 0.10), 0 2px 4px -2px rgb(31 41 55 / 0.06)` | *none* → `1px` `--border` outline + `--surface` fill | Popovers, dropdowns, dragging card |
| `shadow-lg` | `0 12px 32px -8px rgb(31 41 55 / 0.18), 0 4px 8px -4px rgb(31 41 55 / 0.08)` | *none* → `1px` `--border` outline + `--surface` fill | Dialogs, command palette, task slide-over |

### Z-index scale

| Token | Value | Layer |
| --- | --- | --- |
| `z-base` | 0 | Main panel content |
| `z-sticky` | 10 | Sticky list group headers, board column headers |
| `z-sidebar` | 20 | Left sidebar |
| `z-topbar` | 30 | Top bar |
| `z-drag` | 40 | dnd-kit `DragOverlay` |
| `z-overlay` | 50 | Sidebar scrim (<1024px), dialog scrim |
| `z-panel` | 60 | Task detail slide-over |
| `z-dropdown` | 70 | Popover / dropdown / select content |
| `z-palette` | 80 | Command palette (Cmd+K) |
| `z-toast` | 90 | Toaster |
| `z-tooltip` | 100 | Tooltips |

### Motion

| Token | Value | Usage |
| --- | --- | --- |
| `duration-fast` | **120ms** | Hover, focus ring, checkbox, chip toggle, tooltip |
| `duration-base` | **180ms** | Dropdowns, popovers, toasts, accordion tree expand |
| `duration-slow` | **240ms** | Slide-over panel, dialog, sidebar overlay, view transition |
| `ease-standard` | `cubic-bezier(0.4, 0.0, 0.2, 1)` | Default for size/opacity changes |
| `ease-out` | `cubic-bezier(0.0, 0.0, 0.2, 1)` | Entering elements (panel in, toast in) |
| `ease-in` | `cubic-bezier(0.4, 0.0, 1, 1)` | Exiting elements (panel out, toast out) |
| `ease-spring` | `cubic-bezier(0.2, 0.8, 0.2, 1)` | Drag drop-settle, board card reflow |

Drag transforms are exempt from duration tokens: while a pointer drag is active the transform is **untweened** (0ms); only the drop-settle uses `duration-base` + `ease-spring`.

## 2.2 `tailwind.config.ts` theme extension

```ts
// frontend/tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"], // <html class="dark">
  content: ["./src/**/*.{ts,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background) / <alpha-value>)",
        surface: "hsl(var(--surface) / <alpha-value>)",
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        border: "hsl(var(--border) / <alpha-value>)",
        input: "hsl(var(--border) / <alpha-value>)",
        ring: "hsl(var(--ring) / <alpha-value>)",
        muted: {
          DEFAULT: "hsl(var(--surface) / <alpha-value>)",
          foreground: "hsl(var(--muted-foreground) / <alpha-value>)",
        },
        primary: {
          DEFAULT: "hsl(var(--primary) / <alpha-value>)",   // #7B68EE
          hover: "hsl(var(--primary-hover) / <alpha-value>)", // #6B58DE
          foreground: "hsl(var(--primary-fg) / <alpha-value>)", // #FFFFFF
        },
        accent: {
          pink: "hsl(var(--accent-pink) / <alpha-value>)",     // #FD71AF
          blue: "hsl(var(--accent-blue) / <alpha-value>)",     // #49CCF9
          yellow: "hsl(var(--accent-yellow) / <alpha-value>)", // #FFC800
          green: "hsl(var(--accent-green) / <alpha-value>)",   // #2ECD6F
        },
        danger: {
          DEFAULT: "hsl(var(--danger) / <alpha-value>)",       // #E5484D
          foreground: "hsl(var(--primary-fg) / <alpha-value>)",
        },
        priority: {
          urgent: "hsl(var(--priority-urgent) / <alpha-value>)", // #F50000
          high: "hsl(var(--priority-high) / <alpha-value>)",     // #FFCC00
          normal: "hsl(var(--priority-normal) / <alpha-value>)", // #6FDDFF
          low: "hsl(var(--priority-low) / <alpha-value>)",       // #D8D8D8
          none: "hsl(var(--priority-none) / <alpha-value>)",     // #A0A0A0
        },
        status: {
          open: "hsl(var(--status-open) / <alpha-value>)",     // #87909E
          active: "hsl(var(--status-active) / <alpha-value>)", // #4194F6
          closed: "hsl(var(--status-closed) / <alpha-value>)", // #6BC950
        },
      },
      spacing: {
        0: "0px", 0.5: "2px", 1: "4px", 2: "8px", 3: "12px", 4: "16px",
        5: "20px", 6: "24px", 8: "32px", 10: "40px", 12: "48px", 16: "64px",
      },
      borderRadius: {
        sm: "4px", md: "6px", lg: "8px", xl: "12px", full: "9999px",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter var", "system-ui", "sans-serif"],
      },
      fontSize: {
        xs: ["12px", { lineHeight: "1.4" }],
        "13": ["13px", { lineHeight: "1.4" }],
        sm: ["14px", { lineHeight: "1.4" }],
        base: ["16px", { lineHeight: "1.4" }],
        lg: ["20px", { lineHeight: "1.2" }],
        xl: ["24px", { lineHeight: "1.2" }],
        "2xl": ["30px", { lineHeight: "1.2" }],
      },
      fontWeight: { normal: "400", medium: "500", semibold: "600", bold: "700" },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      zIndex: {
        base: "0", sticky: "10", sidebar: "20", topbar: "30", drag: "40",
        overlay: "50", panel: "60", dropdown: "70", palette: "80",
        toast: "90", tooltip: "100",
      },
      width: {
        sidebar: "260px",   // --sidebar-w
        panel: "720px",     // --panel-w-task
        boardcol: "288px",
      },
      height: {
        topbar: "56px",
        row: "36px",        // list view row height
      },
      minHeight: {
        card: "68px",       // board card min height
      },
      transitionDuration: { fast: "120ms", base: "180ms", slow: "240ms" },
      transitionTimingFunction: {
        standard: "cubic-bezier(0.4, 0.0, 0.2, 1)",
        out: "cubic-bezier(0.0, 0.0, 0.2, 1)",
        in: "cubic-bezier(0.4, 0.0, 1, 1)",
        spring: "cubic-bezier(0.2, 0.8, 0.2, 1)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
```

## 2.3 `globals.css` CSS variables (shadcn/ui HSL channel triplets)

```css
/* frontend/src/app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* --- brand: identical in both themes --- */
    --primary: 248 79% 67%;        /* #7B68EE */
    --primary-hover: 248 67% 61%;  /* #6B58DE */
    --primary-fg: 0 0% 100%;       /* #FFFFFF */

    --accent-pink: 333 97% 72%;    /* #FD71AF */
    --accent-blue: 195 94% 63%;    /* #49CCF9 */
    --accent-yellow: 47 100% 50%;  /* #FFC800 */
    --accent-green: 145 63% 49%;   /* #2ECD6F */
    --danger: 358 75% 59%;         /* #E5484D */

    /* --- priority --- */
    --priority-urgent: 0 100% 48%;   /* #F50000 */
    --priority-high: 48 100% 50%;    /* #FFCC00 */
    --priority-normal: 194 100% 72%; /* #6FDDFF */
    --priority-low: 0 0% 85%;        /* #D8D8D8 */
    --priority-none: 0 0% 63%;       /* #A0A0A0 */

    /* --- status types --- */
    --status-open: 216 11% 57%;    /* #87909E */
    --status-active: 212 91% 61%;  /* #4194F6 */
    --status-closed: 107 53% 55%;  /* #6BC950 */

    /* --- neutrals: light --- */
    --background: 0 0% 100%;         /* #FFFFFF */
    --surface: 210 14% 97%;          /* #F7F8F9 */
    --border: 216 12% 92%;           /* #E8EAED */
    --foreground: 215 28% 17%;       /* #1F2937 */
    --muted-foreground: 220 9% 46%;  /* #6B7280 */

    --ring: 248 79% 67%;             /* focus ring = brand purple */

    /* --- elevation --- */
    --shadow-sm: 0 1px 2px 0 rgb(31 41 55 / 0.06);
    --shadow-md: 0 4px 12px -2px rgb(31 41 55 / 0.10), 0 2px 4px -2px rgb(31 41 55 / 0.06);
    --shadow-lg: 0 12px 32px -8px rgb(31 41 55 / 0.18), 0 4px 8px -4px rgb(31 41 55 / 0.08);

    /* --- fixed dimensions --- */
    --topbar-h: 56px;
    --sidebar-w: 260px;
    --panel-w-task: 720px;
    --row-h-list: 36px;
    --card-min-h-board: 68px;
    --board-col-w: 288px;

    /* --- motion --- */
    --duration-fast: 120ms;
    --duration-base: 180ms;
    --duration-slow: 240ms;
    --ease-standard: cubic-bezier(0.4, 0.0, 0.2, 1);
    --ease-out: cubic-bezier(0.0, 0.0, 0.2, 1);
    --ease-in: cubic-bezier(0.4, 0.0, 1, 1);
    --ease-spring: cubic-bezier(0.2, 0.8, 0.2, 1);
  }

  .dark {
    /* brand, priority and status-type channels are intentionally NOT redefined */
    --background: 240 8% 9%;         /* #16161A */
    --surface: 231 10% 13%;          /* #1E1F25 */
    --border: 228 10% 19%;           /* #2C2E36 */
    --foreground: 223 17% 92%;       /* #E7E9EE */
    --muted-foreground: 220 9% 60%;  /* #9096A2 */

    /* shadows become borders in dark mode */
    --shadow-sm: 0 0 0 1px hsl(var(--border));
    --shadow-md: 0 0 0 1px hsl(var(--border));
    --shadow-lg: 0 0 0 1px hsl(var(--border));
  }

  * { @apply border-border; }
  html { color-scheme: light; }
  html.dark { color-scheme: dark; }
  body {
    @apply bg-background text-foreground font-sans text-sm antialiased;
    font-feature-settings: "cv11", "ss01";
  }

  /* focus ring — one rule, applied everywhere */
  :where(a, button, input, textarea, select, [tabindex]):focus-visible {
    @apply outline-none ring-2 ring-ring ring-offset-2 ring-offset-background rounded-sm;
    transition: box-shadow var(--duration-fast) var(--ease-standard);
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
}
```

## 2.4 Dark-mode notes (binding)

1. **Strategy**: class based — `darkMode: ["class"]`, toggled by adding/removing `dark` on `<html>`. No media-query-only mode. Preference is `light | dark | system`, persisted in `localStorage["clickish.theme"]`, applied by a blocking inline script in `app/layout.tsx` to avoid FOUC. `system` resolves via `matchMedia("(prefers-color-scheme: dark)")` and re-resolves live.
2. **What does NOT invert**:
   * **Brand purple** `#7B68EE` and `#6B58DE` are identical in both themes. The product's identity colour must not shift.
   * `--primary-fg` stays `#FFFFFF` — white on purple in both themes.
   * All five **priority** colours and all three **status-type** colours are identical in both themes, because they double as data encoding and must be recognisable across themes and across screenshots.
   * `Status.color` values coming from the API are never adjusted client-side.
3. **What DOES invert**: the five neutrals only — `--background`, `--surface`, `--border`, `--foreground`, `--muted-foreground` swap to the dark set.
4. **Borders lighten**: in light mode `--border` (`#E8EAED`) is *darker* than `--surface`; in dark mode `--border` (`#2C2E36`) is *lighter* than `--surface` (`#1E1F25`). Border contrast is therefore achieved by lightening, never by darkening, in dark mode.
5. **Shadows become borders**: `--shadow-sm/md/lg` all collapse to `0 0 0 1px hsl(var(--border))` in dark mode. Elevation in dark mode is expressed by (a) that hairline and (b) stepping the fill from `--background` to `--surface`. Never render a drop shadow on a dark canvas.
6. **Surfaces on surfaces**: a popover over the sidebar (both `--surface`) is separated by the hairline only; never introduce a third neutral.
7. **Dragging card** in dark mode: `--surface` fill + `2px` `--primary` outline instead of `shadow-md`, so the lift is visible without a shadow.
8. **Images/avatars**: no filter inversion. Avatar fallback backgrounds use the accent tokens at 100% with `--primary-fg` text in both themes.
9. **Selection**: `::selection` is `hsl(var(--primary) / 0.28)` in both themes.

---

# 3. Information architecture & routes

## 3.1 Route table (Next.js 15 App Router)

Base directory: `frontend/src/app`. `(auth)` and `(app)` are route groups. Every route below is listed with its rendering mode; "Server" means an RSC that may fetch on the server and hydrate a TanStack Query cache, "Client" means the file itself carries `"use client"`.

| Route | File | Mode | Auth | Purpose |
| --- | --- | --- | --- | --- |
| `/` | `app/page.tsx` | Server | any | Redirects: signed-in → last workspace (`/w/{id}`), else → `/login` |
| `/login` | `app/(auth)/login/page.tsx` | Server shell + Client form | public | S1 |
| `/register` | `app/(auth)/register/page.tsx` | Server shell + Client form | public | S2 |
| `/invite/[token]` | `app/(auth)/invite/[token]/page.tsx` | Server (lookup) + Client (accept) | public / any | S3 |
| `/w/[workspaceId]` | `app/(app)/w/[workspaceId]/page.tsx` | Server | member+ | Workspace home; redirects to first list or shows S4 empty state |
| `/w/[workspaceId]/s/[spaceId]` | `app/(app)/w/[workspaceId]/s/[spaceId]/page.tsx` | Server | member+ | Space overview (list of lists/folders) |
| `/w/[workspaceId]/l/[listId]` | `app/(app)/w/[workspaceId]/l/[listId]/page.tsx` | Server | member+ | S5/S6 — `?view=list\|board` selects; default `list` |
| `/w/[workspaceId]/l/[listId]/t/[taskId]` | `app/(app)/w/[workspaceId]/l/[listId]/t/[taskId]/page.tsx` | Server | member+ | S7 full-page fallback (deep link / no-JS / refresh) |
| — intercepted | `app/(app)/w/[workspaceId]/l/[listId]/@panel/(.)t/[taskId]/page.tsx` | Client | member+ | S7 as slide-over over the live list/board |
| `/w/[workspaceId]/search` | `app/(app)/w/[workspaceId]/search/page.tsx` | Client | member+ | S8 full results page (cross-list) |
| `/w/[workspaceId]/settings` | `app/(app)/w/[workspaceId]/settings/layout.tsx` | Server | member+ | Settings shell with left nav |
| `/w/[workspaceId]/settings/general` | `.../settings/general/page.tsx` | Client | admin+ | Workspace name, delete workspace (owner only) |
| `/w/[workspaceId]/settings/members` | `.../settings/members/page.tsx` | Client | admin+ (guest: 404) | S9 |
| `/w/[workspaceId]/settings/invitations` | `.../settings/invitations/page.tsx` | Client | admin+ | S9 tab 2 |
| `/w/[workspaceId]/settings/tags` | `.../settings/tags/page.tsx` | Client | member+ | Workspace tag manager |
| `/w/[workspaceId]/s/[spaceId]/settings/statuses` | `.../s/[spaceId]/settings/statuses/page.tsx` | Client | admin+ | S11 (space scope) |
| `/w/[workspaceId]/l/[listId]/settings/statuses` | `.../l/[listId]/settings/statuses/page.tsx` | Client | admin+ | S11 (list scope) |
| `/settings/profile` | `app/(app)/settings/profile/page.tsx` | Client | any | S10 |
| `/settings/account` | `app/(app)/settings/account/page.tsx` | Client | any | S10 tab 2 — password change |
| `/logout` | `app/(app)/logout/route.ts` | Route Handler | any | Calls `POST auth/logout/`, clears storage, redirects `/login` |

S4 (workspace shell) and S12 (command palette) are not routes: S4 is `app/(app)/w/[workspaceId]/layout.tsx`, S12 is a globally mounted client component.

## 3.2 Layouts, boundaries and special files

| File | Mode | Responsibility |
| --- | --- | --- |
| `app/layout.tsx` | Server | `<html lang="en">`, Inter font, theme bootstrap script, `<Providers>` |
| `app/providers.tsx` | Client | `QueryClientProvider`, `ThemeProvider`, `Toaster`, `TooltipProvider`, `CommandPalette`, `RealtimeProvider` |
| `app/(auth)/layout.tsx` | Server | Centred card layout, no chrome |
| `app/(app)/layout.tsx` | Server | Auth guard (reads session, redirects to `/login?next=`) |
| `app/(app)/w/[workspaceId]/layout.tsx` | Server | **S4 shell**: TopBar + Sidebar + `{children}` + `{panel}` parallel slot |
| `app/(app)/w/[workspaceId]/@panel/default.tsx` | Server | Returns `null` — required for the parallel route slot |
| `app/(app)/w/[workspaceId]/loading.tsx` | Server | Sidebar skeleton + main-panel skeleton |
| `app/(app)/w/[workspaceId]/error.tsx` | Client | Workspace-level error boundary; `reset()` retries |
| `app/(app)/w/[workspaceId]/not-found.tsx` | Server | "Workspace not found or you no longer have access" |
| `app/(app)/w/[workspaceId]/l/[listId]/loading.tsx` | Server | 12 × 36px row skeletons (list) / 3 × column skeletons (board) |
| `app/(app)/w/[workspaceId]/l/[listId]/error.tsx` | Client | List-level error boundary; keeps sidebar usable |
| `app/(app)/w/[workspaceId]/settings/members/loading.tsx` | Server | 6 member-row skeletons |
| `app/(auth)/invite/[token]/error.tsx` | Client | Invalid/expired invite fallback |
| `app/global-error.tsx` | Client | Last-resort boundary with `request_id` display |
| `app/not-found.tsx` | Server | 404 |

**Rule**: every route segment that fetches gets a sibling `loading.tsx`. Every route segment that can 403/404 gets a sibling `error.tsx`. Boundaries must never swallow the shell — the sidebar stays interactive when the main panel errors.

## 3.3 Server vs client split policy

* **Server components by default.** `"use client"` only where interactivity requires it (forms, dnd-kit, WebSocket, Zustand consumers, popovers).
* Server components may prefetch with `queryClient.prefetchQuery` and pass a dehydrated state via `<HydrationBoundary>`; the client component then uses `useQuery` with the identical key and gets an instant cache hit.
* Never pass a `QueryClient` or a Zustand store across the RSC boundary — only serialisable dehydrated state.
* `searchParams` (`?view=`, filters) are read in the server page and forwarded as plain props; the client keeps them in sync with `useRouter().replace(..., { scroll: false })`.

---

# 4. Global layout / workspace shell

## 4.1 Full-chrome wireframe (≥1024px)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TOP BAR                                                                                    height 56px   │
│ ┌────────────────────────┬──────────────────────────────────┬─────────────────────────────────────────┐  │
│ │ [☰] [C] Acme Inc.  ▾   │  Space / Folder / List ▸ breadcrumb│ [🔍 Search  /]  ●●●+2  [🔔] [◐] [ AB ▾] │  │
│ │  workspace switcher    │  ← ← ← truncates middle first     │ presence  theme  avatar menu            │  │
│ └────────────────────────┴──────────────────────────────────┴─────────────────────────────────────────┘  │
├───────────────────────────┬──────────────────────────────────────────────────────────────────────────────┤
│ SIDEBAR   width 260px     │ MAIN PANEL                                                    flex-1         │
│ bg --surface              │ bg --background                                                              │
│                           │                                                                              │
│ ┌───────────────────────┐ │ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ [+ New]           ▾   │ │ │ LIST HEADER                                                              │ │
│ └───────────────────────┘ │ │  Sprint 24   ⓘ         [ List │ Board ]   [Filter ▾][Sort ▾][Group ▾][⋯] │ │
│ ┌───────────────────────┐ │ ├──────────────────────────────────────────────────────────────────────────┤ │
│ │ 🏠 Home               │ │ │ FILTER BAR (S8) — only when active                                       │ │
│ │ 🔍 Search       /     │ │ │  [assignee: me ×] [priority: urgent ×] [+ Filter]        Clear all       │ │
│ │ 🔔 Notifications      │ │ ├──────────────────────────────────────────────────────────────────────────┤ │
│ └───────────────────────┘ │ │                                                                          │ │
│ ── SPACES ──────── [+]    │ │  CONTENT AREA                                                            │ │
│ ▾ 🟣 Product              │ │  S5 List view rows (36px) │ S6 Board columns (288px)                     │ │
│   ▾ 📁 Q3 Roadmap         │ │                                                                          │ │
│     ▪ Sprint 24     ●12   │ │                                                                          │ │
│     ▪ Sprint 25     ●3    │ │                                                                          │ │
│   ▸ 📁 Research           │ │                                                                          │ │
│     ▪ Backlog       ●47   │ │                                                                          │ │
│ ▸ 🔵 Design               │ │                                                                          │ │
│ ▸ 🟢 Engineering          │ │                                                                          │ │
│                           │ │                                                                          │ │
│                           │ └──────────────────────────────────────────────────────────────────────────┘ │
│ ┌───────────────────────┐ │                                          ┌─────────────────────────────────┐ │
│ │ ⚙ Settings            │ │                                          │ TASK PANEL (S7) 720px slide-over│ │
│ │ ● Live · 3 online     │ │                                          │ (overlays main panel from right)│ │
│ └───────────────────────┘ │                                          └─────────────────────────────────┘ │
└───────────────────────────┴──────────────────────────────────────────────────────────────────────────────┘
```

## 4.2 Shell component breakdown

| Component | shadcn/ui primitive | Props (TypeScript) | State owner |
| --- | --- | --- | --- |
| `AppShell` | — (layout div) | `{ workspaceId: string; children: ReactNode; panel: ReactNode }` | none (server) |
| `TopBar` | — | `{ workspaceId: string }` | — |
| `WorkspaceSwitcher` | `DropdownMenu` | `{ current: Workspace; }` | Query `['workspaces']` |
| `Breadcrumb` | `Breadcrumb` | `{ items: { id: string; label: string; href: string; kind: 'space'\|'folder'\|'list' }[] }` | Query `['workspace', workspaceId, 'tree']` |
| `SearchTrigger` | `Button` | `{ onOpen(): void }` | Zustand `usePaletteStore` |
| `PresenceStack` | `Avatar` + `Tooltip` | `{ users: PresenceUser[]; max?: number }` | Zustand `useRealtimeStore().presence` |
| `ConnectionIndicator` | `Badge` + `Tooltip` | `{ status: 'connecting'\|'open'\|'reconnecting'\|'offline' }` | Zustand `useRealtimeStore().status` |
| `ThemeToggle` | `DropdownMenu` | `{}` | Zustand `useUiStore().theme` |
| `UserMenu` | `DropdownMenu` + `Avatar` | `{ user: Me }` | Query `['me']` |
| `Sidebar` | — | `{ workspaceId: string }` | Zustand `useUiStore().sidebar` |
| `SidebarCreateButton` | `DropdownMenu` + `Button` | `{ workspaceId: string; canCreateSpace: boolean }` | local |
| `HierarchyTree` | `Accordion`-free custom + `role="tree"` | `{ tree: WorkspaceTree; activeListId?: string }` | Query `['workspace', id, 'tree']`, expansion in Zustand |
| `TreeNode` | `Collapsible` | `{ node: TreeNode; depth: number; isActive: boolean }` | Zustand `useTreeStore().expanded` |
| `SidebarFooter` | — | `{ workspaceId: string }` | — |
| `MainPanel` | — | `{ children: ReactNode }` | — |
| `TaskPanelSlot` | `Sheet` | `{ children: ReactNode }` | route (parallel slot) |
| `SidebarScrim` | `Sheet` overlay | `{ open: boolean; onClose(): void }` | Zustand |

## 4.3 Hierarchy tree rules

* Depth order is fixed: **Workspace > Space > Folder > List**. Lists may be direct children of a Space (no folder) — the API's `POST spaces/{id}/lists/` takes an optional `folder_id`.
* Indent: root spaces at `padding-left: 8px`; each level adds **12px**. Chevron occupies the first 16px of the row; leaf rows get a 16px spacer so labels align.
* Row height 32px, `text-13`, `rounded-md` on hover, active row = `--primary` at 12% alpha fill + `--primary` left bar 2px + `font-medium`.
* Space colour dot = `Space.color` (hex from API) as an 8px `rounded-full`.
* Task count badge on List rows shows the **non-closed** count; it is a `Badge variant="secondary"` in `text-xs` `--muted-foreground`, hidden at 0.
* Expansion state persists in `localStorage["clickish.tree.expanded"]` keyed by workspace id; the active list's ancestors are force-expanded on navigation.
* Reordering spaces/folders/lists in the tree is out of MVP scope for drag & drop **except lists**, which use `PATCH /api/v1/lists/{id}/move/` — see §6.7.

## 4.4 Responsive behaviour

| Breakpoint | Behaviour |
| --- | --- |
| **≥1280px** | Full shell. Sidebar 260px pinned. Task panel 720px overlays the main panel with a 40% `--foreground` scrim over the main panel only (sidebar stays visible and interactive). Board shows as many 288px columns as fit, horizontally scrollable. |
| **1024–1279px** | Same, but the task panel width becomes `min(720px, 100vw - 260px - 24px)` and the scrim covers the whole main panel. Breadcrumb truncates to `… / List`. |
| **<1024px** | Sidebar **collapses to an overlay**: rendered as a shadcn `Sheet side="left"` at 260px width, above a `z-overlay` scrim, opened by the `☰` button in the top bar, closed by `Esc`, scrim click, or navigating to a list. `useUiStore().sidebar.mode` becomes `'overlay'`. Main panel takes full width. Task panel becomes full-width (`100vw`) slide-over. Board columns become 264px and horizontally scroll with snap. |
| **<640px** | Top bar compresses: workspace switcher shows only the avatar-square, breadcrumb collapses to the list name only, presence stack shows max 2 + `+n`, theme toggle moves into the user menu. List view hides the `assignees`, `due date` and `tags` columns and renders a two-line row (title on line 1; status dot + priority flag + due chip on line 2) at 52px height — the 36px row height token applies to ≥640px only. Board view is the default at this width (`?view=board` is *not* forced; the user's last choice wins). Filter bar becomes a horizontally scrollable chip strip. Command palette becomes a full-screen dialog. |
| Touch | Drag activation uses `TouchSensor` with `delay: 200ms, tolerance: 8px` so scrolling still works. Hover-only affordances (row hover actions) get a persistent `⋯` button instead. |

---

# 5. Screen specifications

Conventions used in every screen spec below:

* **Query keys** are the binding cache keys. `filters` is the normalised, sorted filter object (see §5.8.4) — never the raw `searchParams` string.
* All endpoints are relative to `/api/v1/` and **always carry the trailing slash**.
* Error handling assumes the envelope `{"error":{"code","message","details","request_id"}}`. Field errors map to `error.details.<field>: string[]`.
* Every mutation sends `X-Client-Id: <tab uuid>` (see §7.5).

---

## S1 — Login

**Purpose.** Exchange email + password for a JWT pair and land the user in their last-used workspace.
**Who can see it.** Public. An already-authenticated user hitting `/login` is redirected to `/w/{lastWorkspaceId}`.

### Wireframe

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│                        ┌──────────┐                            │
│                        │    C     │  Clickish                  │
│                        └──────────┘                            │
│                                                                │
│      ┌──────────────────────────────────────────────────┐      │
│      │  Log in                                    24px  │      │
│      │  Welcome back.                       muted 14px  │      │
│      │                                                  │      │
│      │  Email                                           │      │
│      │  ┌────────────────────────────────────────────┐  │      │
│      │  │ you@company.com                            │  │      │
│      │  └────────────────────────────────────────────┘  │      │
│      │  ⚠ Enter a valid email address.        (danger)  │      │
│      │                                                  │      │
│      │  Password                    Forgot password?    │      │
│      │  ┌────────────────────────────────────────┬───┐  │      │
│      │  │ ••••••••••                             │ 👁 │  │      │
│      │  └────────────────────────────────────────┴───┘  │      │
│      │                                                  │      │
│      │  ┌────────────────────────────────────────────┐  │      │
│      │  │            Log in            (primary)     │  │      │
│      │  └────────────────────────────────────────────┘  │      │
│      │                                                  │      │
│      │  ⚠ No active account with those credentials.     │      │
│      │                                                  │      │
│      │  ──────────────────────────────────────────────  │      │
│      │  No account?  Sign up                            │      │
│      └──────────────────────────────────────────────────┘      │
│                                                                │
└────────────────────────────────────────────────────────────────┘
      card: max-w 400px, p-40, rounded-xl, bg --surface, shadow-lg
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `AuthCard` | `Card` | `{ title: string; subtitle?: string; children: ReactNode; footer?: ReactNode }` | none |
| `LoginForm` | `Form` + `Input` + `Button` | `{ nextUrl?: string }` | local (`react-hook-form`) |
| `PasswordInput` | `Input` | `{ value: string; onChange(v: string): void; error?: string; autoComplete: 'current-password' \| 'new-password' }` | local |
| `FormFieldError` | `FormMessage` | `{ messages?: string[] }` | local |
| `FormBanner` | `Alert` | `{ variant: 'danger' \| 'warning' \| 'info'; message: string; requestId?: string }` | local |
| `SubmitButton` | `Button` | `{ pending: boolean; children: ReactNode }` | local |

```ts
type LoginFormValues = { email: string; password: string };
type LoginResponse = { access: string; refresh: string; user: Me };
```

### Data requirements

| Action | Endpoint | Query/Mutation key |
| --- | --- | --- |
| Submit | `POST auth/login/` | mutation `['auth','login']` |
| Post-login bootstrap | `GET me/` | `['me']` |
| Post-login bootstrap | `GET workspaces/` | `['workspaces']` |

On success: store `access` in memory (Zustand `useAuthStore`) + `refresh` in `localStorage["clickish.refresh"]`, `queryClient.setQueryData(['me'], res.user)`, then `router.replace(nextUrl ?? '/w/' + firstWorkspaceId)`.

> Note: the Decision Sheet flags "refresh returned in JSON body (not cookie)" as a **REVIEW ITEM**. This spec implements the documented behaviour (JSON body) and isolates it behind `useAuthStore.persistRefresh()` so a cookie migration touches one function.

### Key interactions

1. Autofocus the **Email** field on mount.
2. `Enter` in either field submits.
3. `Tab` order: Email → Password → show/hide toggle → Forgot password → Log in → Sign up.
4. Show/hide password toggle is a `button type="button"` with `aria-label="Show password"` / `"Hide password"` and `aria-pressed`.
5. While pending, the submit button shows a spinner, keeps its label, and sets `aria-busy="true"`; both inputs become `readOnly` (not `disabled`, so focus is retained).
6. After a failed submit, focus moves to the `FormBanner` (`tabIndex={-1}`, `role="alert"`).
7. `?next=` is preserved through the whole flow and validated to be a same-origin path before redirecting.

### States

| State | What the user sees |
| --- | --- |
| Empty (default) | Clean form, submit enabled (validation is on submit, not on mount). |
| Loading | Submit button spinner; no skeletons (nothing is fetched before submit). |
| Error — credentials | `401 authentication_failed` → banner "No active account with those credentials." Password cleared, email kept, focus to banner. |
| Error — validation | `400 validation_error` → per-field messages from `error.details.email` / `error.details.password`. |
| Error — throttled | `429 throttled` → banner "Too many attempts. Try again in {n}s." Submit disabled with a live countdown. |
| Error — server | `5xx server_error` → banner "Something went wrong on our side." plus `request_id` in `text-xs` muted, copyable. |
| Permission denied | n/a (public route). |
| Offline | `navigator.onLine === false` → banner "You're offline. Check your connection." Submit disabled until `online` fires. |

### Validation & inline errors

| Field | Client rule | Server mapping |
| --- | --- | --- |
| `email` | required, RFC-ish email regex | `error.details.email[0]` |
| `password` | required, min length 1 (no client strength rule on login) | `error.details.password[0]` |
| form-level | — | `error.message` when `error.details` is absent |

Errors render below the field in `text-xs` `--danger`, the input gets `aria-invalid="true"` and `aria-describedby` pointing at the message id, and the input border becomes `--danger`.

---

## S2 — Register

**Purpose.** Create an account and (optionally) a first workspace, then sign in immediately.
**Who can see it.** Public. Redirects away if already authenticated.

### Wireframe

```
┌────────────────────────────────────────────────────────────────┐
│      ┌──────────────────────────────────────────────────┐      │
│      │  Create your account                       24px  │      │
│      │  Free while in beta.                 muted 14px  │      │
│      │                                                  │      │
│      │  Full name                                       │      │
│      │  ┌────────────────────────────────────────────┐  │      │
│      │  │ Ada Lovelace                               │  │      │
│      │  └────────────────────────────────────────────┘  │      │
│      │  Email                                           │      │
│      │  ┌────────────────────────────────────────────┐  │      │
│      │  │ you@company.com                            │  │      │
│      │  └────────────────────────────────────────────┘  │      │
│      │  ⚠ A user with this email already exists.        │      │
│      │  Password                                        │      │
│      │  ┌────────────────────────────────────────┬───┐  │      │
│      │  │ ••••••••••••                           │ 👁 │  │      │
│      │  └────────────────────────────────────────┴───┘  │      │
│      │  ▓▓▓▓▓▓▓▓░░░░░░  Strong                          │      │
│      │  · At least 8 characters      ✓                  │      │
│      │  · Not entirely numeric       ✓                  │      │
│      │  · Not a common password      ✓                  │      │
│      │                                                  │      │
│      │  Workspace name (optional)                       │      │
│      │  ┌────────────────────────────────────────────┐  │      │
│      │  │ Acme Inc.                                  │  │      │
│      │  └────────────────────────────────────────────┘  │      │
│      │  ┌────────────────────────────────────────────┐  │      │
│      │  │           Create account   (primary)       │  │      │
│      │  └────────────────────────────────────────────┘  │      │
│      │  By continuing you agree to the Terms.           │      │
│      │  ──────────────────────────────────────────────  │      │
│      │  Already have an account?  Log in                │      │
│      └──────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────┘
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `RegisterForm` | `Form` | `{ prefillEmail?: string; inviteToken?: string }` | local |
| `PasswordStrengthMeter` | `Progress` | `{ password: string; rules: PasswordRule[] }` | local (derived) |
| `PasswordRuleList` | — | `{ rules: { id: string; label: string; ok: boolean }[] }` | local (derived) |
| `PasswordInput` | `Input` | see S1 | local |
| `FormFieldError` | `FormMessage` | see S1 | local |

```ts
type RegisterFormValues = {
  full_name: string;
  email: string;
  password: string;
  workspace_name?: string;
};
```

### Data requirements

| Action | Endpoint | Key |
| --- | --- | --- |
| Submit | `POST auth/register/` | mutation `['auth','register']` |
| Auto sign-in | `POST auth/login/` (only if register does not return tokens) | mutation `['auth','login']` |
| Create first workspace when `workspace_name` given | `POST workspaces/` | mutation `['workspaces','create']` |
| Bootstrap | `GET me/`, `GET workspaces/` | `['me']`, `['workspaces']` |

### Key interactions

1. Autofocus **Full name**.
2. Password rules evaluate on every keystroke, debounced 120ms (`duration-fast`); the meter is `aria-hidden` and the rule list is the accessible source of truth (`role="status"`, polite).
3. `Enter` submits from any field.
4. Coming from an invite (S3) the email is prefilled and `readOnly`, and `workspace_name` is hidden entirely — the invite already determines the workspace.
5. On success with `workspace_name`: navigate to the new workspace and open the "Create your first Space" empty state (S4).
6. On success without `workspace_name`: navigate to `/w/{id}` of the only workspace, or the no-workspace empty state.

### States

| State | What the user sees |
| --- | --- |
| Empty | Form, meter at 0, all rules grey. |
| Loading | Submit spinner, inputs `readOnly`, `aria-busy`. |
| Error — validation | Per-field from `error.details.email`, `.password`, `.full_name`, `.workspace_name`. Focus jumps to the first invalid field. |
| Error — conflict | `409 conflict` → email field error "A user with this email already exists." + inline "Log in instead" link that carries the typed email. |
| Error — throttled | `429 throttled` banner with countdown. |
| Error — server | Banner + `request_id`. |
| Offline | Banner, submit disabled. |

### Validation & inline errors

| Field | Client rule | Server mapping |
| --- | --- | --- |
| `full_name` | required, 1–150 chars | `error.details.full_name` |
| `email` | required, email format, ≤254 chars, lowercased on submit | `error.details.email` |
| `password` | required, ≥8 chars, not entirely numeric, not in the common-password list (client heuristic only; server is authoritative) | `error.details.password` |
| `workspace_name` | optional, 1–120 chars when present | `error.details.workspace_name` |

---

## S3 — Invite accept

**Purpose.** Turn an invitation token into a `WorkspaceMember` with the role encoded in the invitation.
**Who can see it.** Anyone with the link. Three branches: signed-out + no account, signed-out + has account, signed-in.

### Wireframe

```
┌──────────────────────────────────────────────────────────────────┐
│      ┌────────────────────────────────────────────────────┐      │
│      │             ┌──────┐                               │      │
│      │             │  AC  │   (workspace avatar, 48px)    │      │
│      │             └──────┘                               │      │
│      │      You've been invited to join                   │      │
│      │      Acme Inc.                            20px/600 │      │
│      │      as a member                     muted 14px    │      │
│      │                                                    │      │
│      │      Invited by  (AB) Ada Lovelace                 │      │
│      │      Sent to     ada@acme.com                      │      │
│      │      Expires     in 6 days                         │      │
│      │      ───────────────────────────────────────────   │      │
│      │  ── branch A: signed in as the invited email ──    │      │
│      │      ┌──────────────────────────────────────────┐  │      │
│      │      │            Accept invitation             │  │      │
│      │      └──────────────────────────────────────────┘  │      │
│      │      Decline                                       │      │
│      │  ── branch B: signed in as SOMEONE ELSE ──         │      │
│      │      ⚠ You're signed in as bob@acme.com.           │      │
│      │        This invite is for ada@acme.com.            │      │
│      │      [ Log out and continue ]  [ Accept anyway ]   │      │
│      │  ── branch C: signed out ──                        │      │
│      │      [ Create account ]  [ I already have one ]    │      │
│      │  ── branch D: invalid / expired / revoked ──       │      │
│      │      ✖ This invitation is no longer valid.         │      │
│      │        Ask an admin of Acme Inc. to resend it.     │      │
│      │      [ Go to Clickish ]                            │      │
│      └────────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────────┘
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `InviteCard` | `Card` | `{ invitation: InvitationLookup }` | Query `['invitation','lookup', token]` |
| `WorkspaceAvatar` | `Avatar` | `{ name: string; color?: string; size?: 24 \| 32 \| 48 }` | none |
| `RoleBadge` | `Badge` | `{ role: 'owner' \| 'admin' \| 'member' \| 'guest' }` | none |
| `InviteActions` | `Button` group | `{ branch: 'self' \| 'other-user' \| 'anonymous' \| 'invalid'; onAccept(): void }` | local |
| `InviteMismatchAlert` | `Alert` | `{ signedInEmail: string; invitedEmail: string }` | none |

```ts
type InvitationLookup = {
  id: string;
  email: string;
  role: 'admin' | 'member' | 'guest';
  workspace: { id: string; name: string; color?: string };
  invited_by: { id: string; full_name: string; avatar_url: string | null };
  expires_at: string;   // ISO-8601 UTC with Z
  status: 'pending' | 'accepted' | 'revoked' | 'expired';
};
```

### Data requirements

| Action | Endpoint | Key |
| --- | --- | --- |
| Lookup (server component, no auth) | `GET invitations/lookup/?token=` | `['invitation','lookup', token]` |
| Accept | `POST invitations/accept/` body `{ token }` | mutation `['invitation','accept']` |
| Post-accept | `GET workspaces/`, `GET workspaces/{id}/tree/` | invalidate `['workspaces']`, `['workspace', id, 'tree']` |

### Key interactions

1. The lookup runs on the server so the workspace name is visible before any JS loads and is shareable/OG-previewable.
2. `Accept invitation` is the autofocused primary in branch A.
3. Branch C stores the token in `sessionStorage["clickish.invite.token"]`, sends the user to `/register?email=<invited>&invite=<token>`, and auto-accepts immediately after registration succeeds.
4. `Esc` does nothing (this is a page, not a dialog).
5. After accept: toast "You joined Acme Inc." and `router.replace('/w/{workspaceId}')`.
6. "Decline" is client-only in MVP — it clears the stored token and routes to `/` (there is no decline endpoint in the inventory).

### States

| State | What the user sees |
| --- | --- |
| Loading | Card skeleton: 48px circle + two text bars + one button bar, `animate-pulse`. |
| Error — not found / expired / revoked | Branch D copy; `404 not_found` or a `status` of `expired`/`revoked` from the lookup both render it. |
| Error — already a member | `409 conflict` → "You're already a member of Acme Inc." + `[ Open workspace ]`. |
| Permission denied | `403 permission_denied` on accept (email mismatch enforced server-side) → mismatch alert, accept disabled, only `Log out and continue` remains. |
| Offline | "You're offline." + retry button; the lookup is retried automatically on `online`. |

### Validation & inline errors

There are no editable fields. Server errors surface as the branch-D banner with `error.message` and a muted `request_id`.

---

## S4 — Workspace shell + sidebar hierarchy tree

**Purpose.** Persistent app chrome: identity, navigation across `Workspace > Space > Folder > List`, global search entry, presence and connection state.
**Who can see it.** Any authenticated `WorkspaceMember` (`owner`, `admin`, `member`, `guest`). Guests see the tree but never the `Settings > Members` entry; `member` sees Members read-only affordances hidden; only `admin`/`owner` see space create/delete.

### Wireframe

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ┌──────────────────────────┐                                                                   │
│ │ ☰  ▣ Acme Inc.        ▾ │  Product / Q3 Roadmap / Sprint 24                                  │
│ └──────────────────────────┘                            ┌──────────────────────────────────┐   │
│                                                         │ 🔍 Search tasks…            /    │   │
│                                                         └──────────────────────────────────┘   │
│                                                             (AB)(CD)(EF) +2   🔔³  ◐   (ME ▾)  │
├──────────────────────────────┬─────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────┐ │                                                                 │
│ │  ＋ New                ▾ │ │                                                                 │
│ └──────────────────────────┘ │                                                                 │
│   🏠  Home                   │                                                                 │
│   🔍  Search             /   │                    MAIN PANEL (S5 / S6 / settings)               │
│   🔔  Notifications      3   │                                                                 │
│                              │                                                                 │
│  SPACES                  ＋  │                                                                 │
│ ┌──────────────────────────┐ │                                                                 │
│ │▾ ● Product           ⋯ ＋│ │  role gating on ⋯ :                                             │
│ │  ▾ 📁 Q3 Roadmap     ⋯ ＋│ │    owner/admin → Rename, Colour, Statuses…, Delete              │
│ │    ▪ Sprint 24    12  ⋯ │◀│    member      → Rename (folders/lists only), New list          │
│ │    ▪ Sprint 25     3  ⋯ │ │    guest       → no ⋯ button at all                             │
│ │    ▪ Bugfixes      0  ⋯ │ │                                                                 │
│ │  ▸ 📁 Research       ⋯ ＋│ │                                                                 │
│ │    ▪ Backlog      47  ⋯ │ │                                                                 │
│ │▸ ● Design            ⋯ ＋│ │                                                                 │
│ │▸ ● Engineering       ⋯ ＋│ │                                                                 │
│ │                          │ │                                                                 │
│ │   (drop indicator ▔▔▔▔)  │ │  ← list drag reorder within space/folder                        │
│ └──────────────────────────┘ │                                                                 │
│                              │                                                                 │
│ ┌──────────────────────────┐ │                                                                 │
│ │ ⚙  Settings              │ │                                                                 │
│ │ ●  Live · 3 online       │ │  ← ConnectionIndicator + presence count                         │
│ └──────────────────────────┘ │                                                                 │
│  260px                       │                                                                 │
└──────────────────────────────┴─────────────────────────────────────────────────────────────────┘
  ▪ = list (leaf)   📁 = folder   ● = space colour dot   ◀ = active row marker (2px --primary bar)
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `AppShell` | — | `{ workspaceId: string; children: ReactNode; panel: ReactNode }` | server |
| `TopBar` | — | `{ workspaceId: string }` | — |
| `WorkspaceSwitcher` | `DropdownMenu` | `{ workspaces: Workspace[]; currentId: string }` | Query `['workspaces']` |
| `Breadcrumb` | `Breadcrumb` | `{ items: BreadcrumbItem[]; maxVisible?: number }` | Query `['workspace', wid, 'tree']` |
| `SearchTrigger` | `Button` | `{ shortcutHint: string }` | Zustand `usePaletteStore.open` |
| `PresenceStack` | `Avatar`+`Tooltip` | `{ users: PresenceUser[]; max?: number }` | Zustand `useRealtimeStore.presence` |
| `NotificationsBell` | `Popover` + `Badge` | `{ count: number }` | Zustand (local-only in MVP) |
| `ConnectionIndicator` | `Tooltip` + dot | `{ status: ConnStatus; lastSyncAt?: string }` | Zustand `useRealtimeStore.status` |
| `ThemeToggle` | `DropdownMenu` | `{ }` | Zustand `useUiStore.theme` |
| `UserMenu` | `DropdownMenu` | `{ user: Me }` | Query `['me']` |
| `Sidebar` | `Sheet` (<1024px) / `aside` | `{ workspaceId: string }` | Zustand `useUiStore.sidebar` |
| `SidebarCreateMenu` | `DropdownMenu` | `{ canCreateSpace: boolean; canCreateList: boolean }` | derived from role |
| `HierarchyTree` | custom, `role="tree"` | `{ tree: WorkspaceTree; activeListId?: string; canReorderLists: boolean }` | Query + Zustand |
| `TreeSpaceNode` | `Collapsible` | `{ space: SpaceNode; depth: 0 }` | Zustand `useTreeStore` |
| `TreeFolderNode` | `Collapsible` | `{ folder: FolderNode; depth: 1 }` | Zustand `useTreeStore` |
| `TreeListNode` | `Link` | `{ list: ListNode; depth: 1 \| 2; isActive: boolean; openCount: number }` | Query |
| `TreeNodeActions` | `DropdownMenu` | `{ kind: 'space'\|'folder'\|'list'; id: string; role: Role }` | local |
| `TreeSkeleton` | `Skeleton` | `{ rows?: number }` | — |
| `CreateSpaceDialog` | `Dialog` + `Form` | `{ workspaceId: string; open: boolean; onOpenChange(o: boolean): void }` | local |
| `CreateListDialog` | `Dialog` + `Form` | `{ spaceId: string; folderId?: string }` | local |
| `RenameDialog` | `Dialog` + `Form` | `{ kind: EntityKind; id: string; currentName: string }` | local |
| `DeleteConfirmDialog` | `AlertDialog` | `{ kind: EntityKind; id: string; name: string; consequence: string }` | local |
| `SidebarFooter` | — | `{ workspaceId: string; role: Role }` | — |

```ts
type Role = 'owner' | 'admin' | 'member' | 'guest';

type WorkspaceTree = {
  workspace: { id: string; name: string; color?: string };
  spaces: Array<{
    id: string; name: string; color: string; position: string;
    folders: Array<{
      id: string; name: string; position: string;
      lists: Array<ListNode>;
    }>;
    lists: Array<ListNode>;           // lists directly under the space (folder_id null)
  }>;
};

type ListNode = {
  id: string; name: string; position: string;
  folder_id: string | null; space_id: string;
  open_task_count: number;            // non-closed tasks
};
```

### Data requirements

| Purpose | Endpoint | Query key |
| --- | --- | --- |
| Workspace list (switcher) | `GET workspaces/` | `['workspaces']` |
| Current workspace | `GET workspaces/{id}/` | `['workspace', workspaceId]` |
| Whole tree (single call — preferred) | `GET workspaces/{id}/tree/` | `['workspace', workspaceId, 'tree']` |
| Current user | `GET me/` | `['me']` |
| Members (for role of current user + presence names) | `GET workspaces/{id}/members/` | `['workspace', workspaceId, 'members']` |
| Create space | `POST workspaces/{id}/spaces/` | invalidates `['workspace', workspaceId, 'tree']` |
| Create folder | `POST spaces/{id}/folders/` | invalidates tree |
| Create list | `POST spaces/{id}/lists/` (body may include `folder_id`) | invalidates tree |
| Rename space / folder / list | `PATCH spaces/{id}/` · `PATCH folders/{id}/` · `PATCH lists/{id}/` | optimistic on tree |
| Delete | `DELETE spaces/{id}/` · `DELETE folders/{id}/` · `DELETE lists/{id}/` | invalidates tree |
| Reorder list in tree | `PATCH lists/{id}/move/` | optimistic on tree |

`staleTime` for the tree is 30s; it is invalidated by `task.created`/`task.deleted` events only for the affected list's counter (patched in place, not refetched).

### Key interactions

1. `☰` toggles the sidebar. Below 1024px it opens the overlay `Sheet`; above, it collapses the sidebar to 0 and the main panel expands (state in `useUiStore`, persisted).
2. **Tree keyboard model** (`role="tree"`, roving `tabIndex`): `↓`/`↑` move between *visible* nodes; `→` expands a collapsed node then moves into it; `←` collapses, or moves to parent if already collapsed; `Home`/`End` jump to first/last visible; `Enter` navigates to the node's route; typing a letter jumps to the next node starting with it (typeahead, 1s buffer).
3. `/` from anywhere (outside inputs) focuses the top-bar search; `Cmd/Ctrl+K` opens the command palette (S12).
4. Hovering a tree row reveals `⋯` and `＋`; both are keyboard-reachable via `Tab` from within the focused row and are `aria-label`led ("More actions for Sprint 24").
5. `＋` on a Space creates a list at the space root; `＋` on a Folder creates a list in that folder; `＋` on the SPACES header creates a Space (admin/owner only).
6. Right-clicking a tree row opens the same menu as `⋯` (`ContextMenu`).
7. Navigating to a list force-expands all its ancestors and scrolls the row into view (`block: 'nearest'`).
8. Workspace switch resets `useTreeStore`, cancels the WebSocket, and navigates to `/w/{newId}`.
9. Focus after closing any dialog returns to the trigger element.
10. Lists are draggable within their `(space_id, folder_id)` scope and across folders in the same space — see §6.7.

### States

| State | What the user sees |
| --- | --- |
| Empty — no workspaces | Full-page centred empty state: "Create your first workspace" + primary button opening `CreateWorkspaceDialog`. Sidebar hidden. |
| Empty — workspace, no spaces | Tree area shows an inline empty state: illustration-free, `text-13` muted "No spaces yet", plus `[ Create a space ]` (admin/owner) or "Ask an admin to create a space" (member/guest). |
| Empty — space, no lists | Under the expanded space: "No lists here" + `[ New list ]` (member+). |
| Loading | `TreeSkeleton`: 3 groups of `1 × 32px` bar at 40% width + `2 × 32px` bars at 65% width, indented, `animate-pulse`, 900ms cycle. Top bar renders immediately with a skeleton pill for the workspace name and 3 grey circles for presence. |
| Error — tree fetch | Sidebar body replaced by an inline `Alert` "Couldn't load your spaces." + `[ Retry ]` calling `refetch()`. The rest of the shell stays usable. |
| Permission denied | `403` on `GET workspaces/{id}/` → replace whole shell with "You don't have access to this workspace." + `[ Switch workspace ]`. |
| Not found | `404` on the workspace → `not-found.tsx`. |
| Offline / reconnecting | `ConnectionIndicator` dot changes: `--accent-green` "Live", `--accent-yellow` pulsing "Reconnecting…", `--danger` "Offline". Tooltip shows "Last synced 14:32". A thin 2px `--accent-yellow` progress bar animates under the top bar while reconnecting. |

### Validation & inline errors

Applies to `CreateSpaceDialog`, `CreateListDialog`, `RenameDialog`.

| Field | Rule | Server mapping |
| --- | --- | --- |
| `name` (space/folder/list) | required, 1–120 chars, trimmed, must be unique among siblings (server-enforced) | `error.details.name[0]` — e.g. "A list with this name already exists in this folder." |
| `color` (space) | required hex `#RRGGBB`, chosen from an 8-swatch picker | `error.details.color[0]` |
| `folder_id` (list create) | optional uuid; must belong to the same space | `error.details.folder_id[0]` |
| delete confirmations | typing the entity name is required for **Space** deletion only | `error.message` in the dialog footer |

---

## S5 — List view

**Purpose.** The default working surface for a `TaskList`: a dense, sortable, groupable, inline-editable table of tasks at **36px** row height.
**Who can see it.** All roles. `guest` gets read-only rows (no drag handle, no inline edit) except on tasks where they appear in `assignee_ids`; the "+ New task" affordance is hidden for `guest`.

### Wireframe

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  Sprint 24                                              ┌──────────┬───────┐                       │
│  Product / Q3 Roadmap                                   │  List ▪  │ Board │  [Filter ▾] [⋯]       │
│                                                         └──────────┴───────┘                       │
├────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  [assignee: me ×] [priority: urgent, high ×] [due: this_week ×]   [＋ Filter]        Clear all      │
├────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Group by: Status ▾    Sort: position ▾    Showing 24 of 118            ⟳ stale, refetching…       │
├────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ▾ ● TO DO  (#87909E)                                                    8            ＋ New task    │
│ ┌──┬──┬────────────────────────────────────┬──────────┬────────┬─────────┬────────┬──────┬──────┐  │
│ │⠿ │☐ │ Name                               │ Status   │ Assign │ Due     │ Prio   │ Tags │  ⋯   │  │ 36px
│ ├──┼──┼────────────────────────────────────┼──────────┼────────┼─────────┼────────┼──────┼──────┤  │
│ │⠿ │☐ │ Fix login redirect loop        💬3 │ ● To do  │ (AB)   │ Aug 8   │ ⚑urgent│ #bug │  ⋯   │  │
│ │⠿ │☐ │ Add rate limiting to /auth/     👁 │ ● To do  │ (AB)(C)│ Aug 12  │ ⚑high  │ #api │  ⋯   │  │
│ │⠿ │☐ │ Write onboarding copy              │ ● To do  │   —    │  —      │ ⚑normal│  —   │  ⋯   │  │
│ │⠿ │☐ │ ▸ Long task title that truncates…  │ ● To do  │ (EF)   │ Aug 2 ⚠ │ ⚑low   │ #ux  │  ⋯   │  │  ⚠ overdue = --danger
│ │  │  │ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │  │
│ │  │  │ │ ＋ Task name…                              (inline composer, Enter=create, Esc=close)│ │  │
│ │  │  │ └──────────────────────────────────────────────────────────────────────────────────────┘ │  │
│ └──┴──┴────────────────────────────────────┴──────────┴────────┴─────────┴────────┴──────┴──────┘  │
│ ▾ ● IN PROGRESS  (#4194F6)                                              5            ＋ New task    │
│ │⠿ │☐ │ Refactor task move endpoint    💬1 │ ● In pro.│ (CD)   │ Aug 9   │ ⚑high  │ #api │  ⋯   │  │
│ │  │  │ ▔▔▔▔▔▔▔▔▔▔▔▔▔▔ drop indicator: 2px --primary, full row width ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔ │  │
│ │⠿ │☐ │ Board column virtualisation        │ ● In pro.│ (AB)   │  —      │ ⚑normal│  —   │  ⋯   │  │
│ ▸ ● DONE  (#6BC950)                                                    11            (collapsed)   │
│                                                                                                    │
│  ⌄ Load more (page 2 of 3)                            [ 50 per page ▾ ]        118 tasks total     │
└────────────────────────────────────────────────────────────────────────────────────────────────────┘
   row hover: bg --surface, rounded-md, ⠿ handle fades in (opacity 0→1, 120ms)
   row selected (checkbox): bg --primary/8, left 2px --primary
```

Bulk-action bar (appears when ≥1 checkbox is ticked, docked bottom-centre, `shadow-lg`, `z-sticky`):

```
┌───────────────────────────────────────────────────────────────────────────┐
│  3 selected   [ Status ▾ ] [ Assignee ▾ ] [ Priority ▾ ] [ Tags ▾ ]  🗑  ✕ │
└───────────────────────────────────────────────────────────────────────────┘
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `ListHeader` | — | `{ list: TaskList; canEdit: boolean }` | Query `['list', listId]` |
| `ViewSwitcher` | `Tabs` | `{ value: 'list' \| 'board'; onChange(v): void }` | URL `?view=` + Zustand fallback |
| `ListToolbar` | — | `{ listId: string }` | — |
| `GroupBySelect` | `Select` | `{ value: 'status' \| 'none'; onChange(v): void }` | Zustand `useViewStore` |
| `SortSelect` | `Select` | `{ value: Ordering; onChange(v: Ordering): void }` | Zustand `useViewStore` |
| `TaskTable` | `Table` + dnd-kit `DndContext` | `{ listId: string; groups: TaskGroup[]; canDrag: boolean }` | Query `['tasks', listId, filters]` |
| `TaskGroupHeader` | `Collapsible` | `{ status: Status; count: number; collapsed: boolean; onToggle(): void }` | Zustand `useViewStore.collapsedGroups` |
| `TaskRow` | `TableRow` + `useSortable` | `{ task: Task; selected: boolean; canEdit: boolean; density: 'default' }` | Query cache (item) |
| `DragHandle` | `Button` (ghost) | `{ listeners: SyntheticListenerMap; attributes: DraggableAttributes; disabled?: boolean }` | dnd-kit |
| `RowCheckbox` | `Checkbox` | `{ checked: boolean; onCheckedChange(c: boolean): void; 'aria-label': string }` | Zustand `useSelectionStore` |
| `TaskTitleCell` | `Input` (inline) | `{ taskId: string; title: string; editable: boolean; onCommit(v: string): void }` | local while editing |
| `StatusPicker` | `Popover` + `Command` | `{ value: string; statusSet: Status[]; onChange(statusId: string): void; disabled?: boolean }` | Query `['list', listId, 'status-set']` |
| `StatusDot` | — | `{ color: string; type: 'open' \| 'active' \| 'closed'; size?: 8 \| 10 }` | none |
| `AssigneePicker` | `Popover` + `Command` + `Avatar` | `{ value: string[]; members: Member[]; onChange(ids: string[]): void; max?: 3 }` | Query `['workspace', wid, 'members']` |
| `AvatarStack` | `Avatar` | `{ users: UserLite[]; max?: number; size?: 20 \| 24 \| 28 }` | none |
| `DueDatePicker` | `Popover` + `Calendar` | `{ value: string \| null; onChange(iso: string \| null): void; overdue: boolean }` | local |
| `PriorityPicker` | `DropdownMenu` | `{ value: Priority; onChange(p: Priority): void }` | none |
| `PriorityFlag` | — | `{ priority: Priority; size?: 14 \| 16 }` | none |
| `TagChips` | `Badge` + `Popover` | `{ value: string[]; tags: Tag[]; onChange(ids: string[]): void; max?: 2 }` | Query `['workspace', wid, 'tags']` |
| `RowActionsMenu` | `DropdownMenu` | `{ task: Task; role: Role }` | local |
| `InlineTaskComposer` | `Input` | `{ listId: string; statusId: string; afterTaskId?: string; onCreated(t: Task): void }` | local + optimistic mutation |
| `BulkActionBar` | `Card` | `{ selectedIds: string[]; onClear(): void }` | Zustand `useSelectionStore` |
| `TaskRowSkeleton` | `Skeleton` | `{ count?: number }` | — |
| `PaginationFooter` | `Button` + `Select` | `{ page: number; totalPages: number; count: number; pageSize: number }` | Query meta |
| `StaleIndicator` | `Badge` | `{ isFetching: boolean; isStale: boolean }` | TanStack `useIsFetching` |

```ts
type Priority = 'urgent' | 'high' | 'normal' | 'low' | 'none';

type Task = {
  id: string;
  list_id: string;
  title: string;
  description_html: string | null;
  description_json: unknown | null;
  status_id: string;
  priority: Priority;
  position: string;                 // fractional index, base-62
  due_date: string | null;          // ISO-8601 UTC Z
  start_date: string | null;
  time_estimate_minutes: number | null;
  assignee_ids: string[];
  watcher_ids: string[];
  tag_ids: string[];
  comment_count: number;
  created_by_id: string;
  updated_by_id: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  archived: boolean;
};

type TaskGroup = { status: Status; tasks: Task[]; count: number };
```

### Data requirements

| Purpose | Endpoint | Query key |
| --- | --- | --- |
| List metadata | `GET lists/{id}/` | `['list', listId]` |
| Effective status set | `GET lists/{id}/status-set/` | `['list', listId, 'status-set']` |
| Tasks (ungrouped) | `GET lists/{id}/tasks/?page&page_size&ordering&<filters>` | `['tasks', listId, filters]` |
| Tasks (grouped, `group_by=status`) | `GET lists/{id}/tasks/?group_by=status&<filters>` | `['tasks', listId, filters, { groupBy: 'status' }]` |
| Members (assignee picker) | `GET workspaces/{id}/members/` | `['workspace', workspaceId, 'members']` |
| Tags | `GET workspaces/{id}/tags/` | `['workspace', workspaceId, 'tags']` |
| Create task | `POST lists/{id}/tasks/` | mutation `['task','create', listId]` |
| Inline edit | `PATCH tasks/{id}/` | mutation `['task','update', taskId]` |
| Reorder / move | `PATCH tasks/{id}/move/` | mutation `['task','move', taskId]` |
| Delete (soft) | `DELETE tasks/{id}/` | mutation `['task','delete', taskId]` |
| Watch / unwatch | `POST tasks/{id}/watch/` · `DELETE tasks/{id}/watch/` | mutation `['task','watch', taskId]` |

Default query string: `?ordering=position&page=1&page_size=50&archived=false`.
Sort within a status group is `ORDER BY position ASC, created_at ASC`; ungrouped is `ORDER BY status__order ASC, position ASC` — the client never re-sorts, it renders the server order.

`filters` normalisation (also used by S6 and S8):

```ts
type TaskFilters = {
  status?: string[];                                   // status ids, repeatable
  status_type?: Array<'open' | 'active' | 'closed'>;
  assignee?: Array<string | 'me' | 'none'>;
  priority?: Priority[];
  tag?: string[];
  due?: 'overdue' | 'today' | 'this_week' | 'none';
  due_before?: string;
  due_after?: string;
  created_by?: string;
  watcher?: string;
  q?: string;
  archived?: boolean;                                  // default false
  include_deleted?: boolean;                           // admin only
  ordering?: Ordering;
  page?: number;
  page_size?: number;                                  // default 50, max 200
};

type Ordering =
  | 'position' | '-position'
  | 'due_date' | '-due_date'
  | 'priority_order' | '-priority_order'
  | 'created_at' | '-created_at'
  | 'updated_at' | '-updated_at'
  | 'title' | '-title';
```

Arrays are sorted and undefined keys dropped before the object enters the query key, so `['tasks', listId, filters]` is stable.

### Key interactions

1. `1` switches to List view, `2` to Board view (updates `?view=` with `router.replace`, no scroll).
2. `j` / `k` (or `↓` / `↑`) move the row cursor; the cursor row gets a 2px `--primary` left bar and is scrolled into view. `Home`/`End` jump to first/last row in the current group.
3. `Enter` or `o` on the cursor row opens the task panel (S7). `Space` toggles the row checkbox.
4. `e` starts inline title editing on the cursor row: the title cell becomes an `Input` with the text selected. `Enter` commits (`PATCH tasks/{id}/`), `Esc` cancels and restores, `Tab` commits and moves to the Status cell.
5. `t` opens the inline composer at the bottom of the current group with `status_id` preset to that group's status; `Enter` creates and immediately reopens a fresh composer below (rapid entry); `Esc` closes. Newly created tasks are optimistic with a client-generated UUID (allowed by the Decision Sheet).
6. `x` toggles selection; `Shift+click` selects a range; `Cmd/Ctrl+A` selects all loaded rows in the focused group. The bulk bar appears with `duration-base` slide-up.
7. `Backspace`/`Delete` on selection opens `AlertDialog` "Delete 3 tasks?"; confirming soft-deletes each (`deleted_at`) with a single undo toast (5s) that re-creates via `PATCH` restore semantics if available, otherwise re-fetches.
8. Clicking a status pill opens `StatusPicker` (a `Command` list filtered by typing). Choosing a status issues `PATCH tasks/{id}/` with `status_id`; if the status does not belong to the list's effective set the server returns `400 invalid_status_for_list` and the UI rolls back with a danger toast.
9. Group headers collapse/expand with `→`/`←` when focused, persisted per list in `useViewStore`.
10. `⋯` row menu: Open, Copy link, Watch/Unwatch, Duplicate (client-side create), Move to list…, Archive, Delete.
11. Drag: pointer press on `⠿` (handle only in list view) starts a drag after 4px movement — see §6.
12. `Shift+?` opens the shortcut cheat-sheet dialog.
13. Focus management: opening the task panel moves focus into it; closing returns focus to the originating row.

### States

| State | What the user sees |
| --- | --- |
| Empty — no tasks at all | Centred block, 48px vertical padding: "No tasks in Sprint 24 yet." + `[ ＋ New task ]` (hidden for `guest`) + secondary "Import" is out of scope. |
| Empty — filters exclude everything | "No tasks match your filters." + `[ Clear all filters ]`, and the filter bar stays visible with its chips. |
| Empty — a status group has 0 tasks | The group header still renders (so it remains a drop target) with a 36px dashed placeholder row reading "Drop a task here". |
| Loading — first load | Toolbar renders live; body renders **12 `TaskRowSkeleton` rows of exactly 36px**: 16px circle + 40%-width bar + 3 pill placeholders, `animate-pulse`. Group headers are skeletonised as a 20px × 120px bar. |
| Loading — page 2 | Existing rows stay; 6 skeleton rows append below; the "Load more" button shows a spinner. |
| Loading — background refetch | Rows stay fully interactive; `StaleIndicator` shows `⟳ stale, refetching…` in the toolbar (see §7.7). |
| Error — task fetch | Body replaced with `Alert variant="danger"`: `error.message` + `request_id` + `[ Retry ]`. Header/toolbar remain. |
| Error — mutation | Optimistic change reverts with a 180ms fade back, and a danger toast shows `error.message` with `[ Retry ]`. |
| Permission denied | `403 permission_denied` on a mutation → the affordance disables permanently for the session and a toast reads "You don't have permission to do that." `guest` never sees create/drag affordances in the first place. |
| Offline | Toolbar shows an `--danger` "Offline" chip; mutations are **not** queued in MVP — inputs that mutate become disabled with tooltip "Reconnect to make changes." Reads serve from cache. |
| Reconnecting | `--accent-yellow` chip "Reconnecting…"; on success the list refetches and any rows whose `updated_at` changed flash a 240ms `--accent-blue` background. |

### Validation & inline errors

| Field | Rule | Server mapping |
| --- | --- | --- |
| `title` (inline / composer) | required, trimmed, 1–500 chars | `error.details.title[0]` shown as a `Tooltip`-style popover anchored to the cell, `--danger` border, cell stays in edit mode |
| `status_id` | must belong to the list's effective status set | `error.details.status_id[0]` or top-level code `invalid_status_for_list` → toast "That status isn't available in this list." |
| `due_date` | ISO-8601 UTC with `Z`; must be ≥ `start_date` when both set | `error.details.due_date[0]` inline under the calendar popover |
| `assignee_ids` | every id must be a workspace member | `error.details.assignee_ids[0]` |
| `priority` | one of `urgent`/`high`/`normal`/`low`/`none` | `error.details.priority[0]` |
| move | — | code `position_conflict` → silent refetch of `['tasks', listId, filters]` and re-apply (see §6.5) |

---

## S6 — Board (Kanban) view

**Purpose.** Status-column view of the same `TaskList`, driven by `?group_by=status`, where dragging a card between columns changes `status_id`.
**Who can see it.** All roles; `guest` gets non-draggable cards and no `＋` in column headers.

### Wireframe

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│  Sprint 24                                          ┌──────┬─────────┐                           │
│  Product / Q3 Roadmap                               │ List │ Board ▪ │  [Filter ▾] [Sort ▾] [⋯]  │
│                                                     └──────┴─────────┘                           │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│  [assignee: me ×] [priority: urgent ×]  [＋ Filter]                       Clear all               │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐     │
│  │ ● TO DO       8  ⋯ │ │ ● IN PROGRESS 5 ⋯ │ │ ● IN REVIEW   2  ⋯ │ │ ● DONE       11  ⋯ │  →  │
│  │ #87909E        ＋  │ │ #4194F6        ＋ │ │ #4194F6        ＋  │ │ #6BC950        ＋  │     │
│  ├────────────────────┤ ├────────────────────┤ ├────────────────────┤ ├────────────────────┤     │
│  │┌──────────────────┐│ │┌──────────────────┐│ │┌──────────────────┐│ │┌──────────────────┐│     │
│  ││⚑ Fix login       ││ ││⚑ Refactor move   ││ ││⚑ Board virtual…  ││ ││  Ship v0.9       ││     │
│  ││  redirect loop   ││ ││  endpoint        ││ ││                  ││ ││  (strikethrough) ││     │
│  ││ #bug  #api       ││ ││ #api             ││ ││ #perf            ││ ││ #release         ││     │
│  ││ Aug 8  💬3  (AB) ││ ││ Aug 9  💬1  (CD) ││ ││ —      (AB)(CD)  ││ ││ Aug 1   ✓  (EF)  ││     │
│  │└──────────────────┘│ │└──────────────────┘│ │└──────────────────┘│ │└──────────────────┘│     │
│  │┌──────────────────┐│ │▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔│ │                    │ │┌──────────────────┐│     │
│  ││⚑ Add rate        ││ │  drop placeholder  │ │                    │ ││  Update README   ││     │
│  ││  limiting        ││ │  (68px dashed,     │ │                    │ ││ Jul 28  ✓        ││     │
│  ││ #api  👁         ││ │   --primary/40)    │ │                    │ │└──────────────────┘│     │
│  ││ Aug 12  (AB)(C)  ││ │                    │ │                    │ │                    │     │
│  │└──────────────────┘│ │┌──────────────────┐│ │                    │ │  ⌄ 9 more          │     │
│  │┌──────────────────┐│ ││⚑ Column DnD a11y ││ │  ┌──────────────┐  │ │                    │     │
│  ││  Write onboarding││ ││ —        (AB)    ││ │  │ Drop a task  │  │ │                    │     │
│  ││  copy            ││ │└──────────────────┘│ │  │ here (dashed)│  │ │                    │     │
│  ││ —                ││ │                    │ │  └──────────────┘  │ │                    │     │
│  │└──────────────────┘│ │                    │ │                    │ │                    │     │
│  │┌──────────────────┐│ │                    │ │                    │ │                    │     │
│  ││ ＋ New task      ││ │┌ ＋ New task ─────┐│ │┌ ＋ New task ─────┐│ │┌ ＋ New task ─────┐│     │
│  │└──────────────────┘│ │└──────────────────┘│ │└──────────────────┘│ │└──────────────────┘│     │
│  └────────────────────┘ └────────────────────┘ └────────────────────┘ └────────────────────┘     │
│   288px, gap 16px       columns scroll independently (overflow-y auto), row scrolls horizontally  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
   card: bg --surface, rounded-lg, shadow-sm, min-h 68px, p-12
   card while dragging (DragOverlay): rotate 2deg, scale 1.02, shadow-md (light) / --primary 2px ring (dark)
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `BoardView` | `DndContext` | `{ listId: string; statusSet: Status[]; canDrag: boolean }` | Query `['tasks', listId, filters, { groupBy: 'status' }]` |
| `BoardScroller` | `ScrollArea` | `{ children: ReactNode }` | local |
| `BoardColumn` | `SortableContext` (`verticalListSortingStrategy`) | `{ status: Status; tasks: Task[]; count: number; canDrag: boolean; canCreate: boolean }` | Query |
| `BoardColumnHeader` | — | `{ status: Status; count: number; onCreate(): void }` | — |
| `BoardColumnMenu` | `DropdownMenu` | `{ status: Status; canEditStatuses: boolean }` | — |
| `TaskCard` | `Card` + `useSortable` | `{ task: Task; isDragging?: boolean; canDrag: boolean }` | Query cache (item) |
| `TaskCardOverlay` | `DragOverlay` child | `{ task: Task }` | dnd-kit |
| `DropPlaceholder` | — | `{ height: number }` | dnd-kit derived |
| `ColumnComposer` | `Textarea` | `{ listId: string; statusId: string; onCreated(t: Task): void }` | local |
| `BoardColumnSkeleton` | `Skeleton` | `{ cards?: number }` | — |
| `LoadMoreInColumn` | `Button` | `{ statusId: string; remaining: number }` | Query |
| `EmptyColumnDropZone` | — | `{ statusId: string }` | — |

```ts
type BoardGroupedResponse = {
  groups: Array<{
    status: Status;
    count: number;               // total in this status (may exceed returned page)
    results: Task[];
    next: string | null;
  }>;
};

type Status = {
  id: string;
  name: string;
  color: string;                 // hex, wins over the type token
  type: 'open' | 'active' | 'closed';
  order: number;                 // integer, not fractional
  is_default: boolean;
  status_set_id: string;
};
```

### Data requirements

| Purpose | Endpoint | Query key |
| --- | --- | --- |
| Grouped tasks | `GET lists/{id}/tasks/?group_by=status&<filters>` | `['tasks', listId, filters, { groupBy: 'status' }]` |
| Effective status set (column order & colours) | `GET lists/{id}/status-set/` | `['list', listId, 'status-set']` |
| Column "load more" | `GET lists/{id}/tasks/?status={id}&page=n` | `['tasks', listId, { ...filters, status: [id] }]` |
| Create in column | `POST lists/{id}/tasks/` with `status_id` | mutation `['task','create', listId]` |
| Move (reorder or cross-column) | `PATCH tasks/{id}/move/` | mutation `['task','move', taskId]` |
| Inline field edits from the card menu | `PATCH tasks/{id}/` | mutation `['task','update', taskId]` |

Columns are ordered by `Status.order` ascending. Cards inside a column are ordered by `position ASC, created_at ASC`. The client renders server order and never sorts.

### Key interactions

1. `2` enters Board view; `1` returns to List. The `?view=` param is the source of truth and is preserved on refresh and in shared links.
2. **Whole card is draggable** in board view (no separate handle) — see §6.2 for the rationale and the a11y consequence.
3. Clicking a card (pointer up with < 4px movement) opens the task panel (S7).
4. `j`/`k` move the card cursor within a column; `h`/`l` move between columns keeping the vertical index (clamped).
5. `Enter` opens the cursor card; `Space` lifts it for keyboard drag (see §6.6).
6. `t` or the column `＋` opens `ColumnComposer` at the **top** of the column (board composes at top; list composes at bottom — deliberate, matches where new work lands). `Enter` creates, `Shift+Enter` newline, `Esc` closes.
7. Horizontal auto-scroll when a drag approaches within 80px of the viewport edge, at up to 12px/frame — see §6.4.
8. Columns lazy-load: each column requests `page_size=50`; a `⌄ n more` button appends the next page for that status only.
9. Column header `⋯` → "Edit statuses…" (routes to S11, admin/owner only), "Collapse column", "Create task".
10. Collapsed columns render as a 44px vertical rail with rotated label and count, and remain valid drop targets (dropping expands them).
11. `Shift+?` opens the shortcut cheat-sheet.

### States

| State | What the user sees |
| --- | --- |
| Empty — no tasks | All columns render (from the status set) each with a dashed 68px "Drop a task here" zone plus `＋ New task`. A single centred hint sits above the board: "This list is empty." |
| Empty — one column | Dashed 68px `EmptyColumnDropZone` reading "Drop a task here", `--primary` at 40% dashed border. |
| Empty — filters exclude everything | Columns still render; each shows "No matching tasks"; a toolbar banner offers `[ Clear all filters ]`. |
| Loading | 4 `BoardColumnSkeleton`s: header bar 20 × 120px + 3 card skeletons of exactly 68px (two text bars + a pill row), `animate-pulse`. |
| Loading — column page | Skeleton card appended at the column bottom; `⌄ n more` shows a spinner. |
| Error | Full-board `Alert` with `error.message`, `request_id`, `[ Retry ]`. If only one column's "load more" fails, the error is inline in that column. |
| Error — invalid status | Cross-column drop rejected with `400 invalid_status_for_list` → card animates back to origin over 240ms and a danger toast explains the list's status set does not contain that status (can happen if the status set changed in another tab). Board then refetches the status set. |
| Permission denied | `403` on move → card returns to origin; toast "You don't have permission to move tasks here." `guest` cards render with `cursor: default` and no drag listeners. |
| Offline | Drag is disabled entirely (`DndContext` gets `sensors={[]}`), cards get `aria-disabled`, and a persistent `--danger` toolbar chip explains why. |
| Reconnecting | Drag stays enabled but a move started while reconnecting is held in the mutation queue for up to 10s; if the socket does not recover the mutation still goes over HTTP (REST is independent of the WebSocket) — the WebSocket only affects *receiving* updates. |

### Validation & inline errors

| Field | Rule | Server mapping |
| --- | --- | --- |
| `title` (`ColumnComposer`) | required, 1–500 chars | `error.details.title[0]` under the textarea, `--danger` border, textarea keeps focus and content |
| `status_id` (implicit on cross-column drop) | must be in the list's effective status set | code `invalid_status_for_list` → rollback + toast |
| `before_id` / `after_id` | must be siblings in the same `(list_id, status_id)` scope | code `position_conflict` → silent refetch + re-apply |

---

## S7 — Task detail slide-over panel

**Purpose.** Full task record — title, description, all fields, comments — in a **720px** panel sliding in from the right, without unmounting the list/board behind it.
**Who can see it.** All roles. `guest` sees everything read-only **except** the comment composer (guests may comment) and, when the guest is in `assignee_ids`, the editable fields.

### Wireframe

```
                        ┌────────────────────────────────────────────────────────────────────┐
   (list/board dimmed)  │  ‹ ›  Sprint 24 / Fix login redirect loop        🔗  👁  ⋯    ✕     │ 56px
   scrim: --foreground  ├────────────────────────────────────────────────────────────────────┤
   at 40% over the      │                                                                    │
   main panel only      │  ┌──────────────────────────────────────────────────────────────┐  │
                        │  │ Fix login redirect loop                          20px/600    │  │
                        │  │ (click to edit inline, autosize textarea)                    │  │
                        │  └──────────────────────────────────────────────────────────────┘  │
                        │                                                                    │
                        │  ┌────────────┬─────────────────────────────────────────────────┐  │
                        │  │ Status     │ [ ● To do ▾ ]                                   │  │
                        │  │ Assignees  │ (AB)(CD) ＋                                     │  │
                        │  │ Priority   │ [ ⚑ Urgent ▾ ]                                  │  │
                        │  │ Due date   │ [ Aug 8, 2026 09:00 ▾ ]      ⚠ overdue          │  │
                        │  │ Start date │ [ Aug 4, 2026 ▾ ]                               │  │
                        │  │ Estimate   │ [ 3h 30m ]                                      │  │
                        │  │ Tags       │ [#bug ×][#api ×] ＋                             │  │
                        │  │ Watchers   │ (AB)(EF) ＋            You're watching 👁        │  │
                        │  │ List       │ Product / Q3 Roadmap / Sprint 24   [ Move… ]    │  │
                        │  └────────────┴─────────────────────────────────────────────────┘  │
                        │  ────────────────────────────────────────────────────────────────  │
                        │  Description                                       [ Edit ]        │
                        │  ┌──────────────────────────────────────────────────────────────┐  │
                        │  │ After SSO login the app bounces between /login and /w/…      │  │
                        │  │ • repro on Safari 18                                         │  │
                        │  │ • only when refresh token is rotated                         │  │
                        │  │ (rich text; description_html rendered, description_json      │  │
                        │  │  is the editor source of truth)                              │  │
                        │  └──────────────────────────────────────────────────────────────┘  │
                        │  ────────────────────────────────────────────────────────────────  │
                        │  Activity                        [ Comments ▪ ]  [ All activity ]  │
                        │  ┌──────────────────────────────────────────────────────────────┐  │
                        │  │ (AB) Ada Lovelace · 2h ago                            ⋯      │  │
                        │  │      I can repro. Looks like BLACKLIST_AFTER_ROTATION.        │  │
                        │  │ (CD) Carl Dyer · 41m ago                              ⋯      │  │
                        │  │      Patch on the way.                                       │  │
                        │  │ (EF) Eve is typing…                             (presence)   │  │
                        │  └──────────────────────────────────────────────────────────────┘  │
                        ├────────────────────────────────────────────────────────────────────┤
                        │  ┌──────────────────────────────────────────────────────┬───────┐  │
                        │  │ Write a comment…                                     │ Send  │  │
                        │  └──────────────────────────────────────────────────────┴───────┘  │
                        │  Created by Ada · Aug 1 · Updated 2m ago by Carl         (12px)    │
                        └────────────────────────────────────────────────────────────────────┘
                          720px, bg --background, shadow-lg, rounded-l-xl, z-panel
                          enter: translateX(100%)→0, 240ms cubic-bezier(0,0,.2,1)
                          exit:  0→translateX(100%), 240ms cubic-bezier(.4,0,1,1)
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `TaskPanel` | `Sheet side="right"` | `{ taskId: string; listId: string; onClose(): void }` | route + Query `['task', taskId]` |
| `TaskPanelHeader` | — | `{ task: Task; hasPrev: boolean; hasNext: boolean; onNavigate(dir: -1 \| 1): void }` | Zustand `useViewStore.cursor` |
| `TaskTitleEditor` | `Textarea` (autosize) | `{ value: string; editable: boolean; onCommit(v: string): void }` | local while editing |
| `TaskFieldGrid` | — | `{ task: Task; editable: boolean }` | — |
| `FieldRow` | — | `{ label: string; htmlFor?: string; children: ReactNode }` | — |
| `StatusPicker` | `Popover` + `Command` | see S5 | Query `['list', listId, 'status-set']` |
| `AssigneePicker` | `Popover` + `Command` | see S5 | Query `['workspace', wid, 'members']` |
| `PriorityPicker` | `DropdownMenu` | see S5 | — |
| `DueDatePicker` | `Popover` + `Calendar` | `{ value: string \| null; withTime?: boolean; onChange(iso: string \| null): void }` | local |
| `EstimateInput` | `Input` | `{ minutes: number \| null; onCommit(m: number \| null): void }` | local (parses "3h 30m", "90m", "1.5h") |
| `TagPicker` | `Popover` + `Command` + `Badge` | `{ value: string[]; tags: Tag[]; onChange(ids: string[]): void; canCreate: boolean }` | Query `['workspace', wid, 'tags']` |
| `WatcherControl` | `Button` + `AvatarStack` | `{ taskId: string; watching: boolean; watchers: UserLite[] }` | mutation `['task','watch', taskId]` |
| `MoveTaskDialog` | `Dialog` + `Command` | `{ taskId: string; currentListId: string }` | Query `['workspace', wid, 'tree']` |
| `DescriptionEditor` | `Textarea` / rich-text | `{ html: string \| null; json: unknown \| null; editable: boolean; onCommit(v: { description_html: string; description_json: unknown }): void }` | local while editing |
| `CommentList` | `ScrollArea` | `{ taskId: string }` | Query `['comments', taskId]` |
| `CommentItem` | — | `{ comment: Comment; canEdit: boolean; canDelete: boolean }` | Query cache |
| `CommentComposer` | `Textarea` + `Button` | `{ taskId: string; onSent(c: Comment): void }` | local + optimistic |
| `TypingIndicator` | — | `{ users: UserLite[] }` | Zustand `useRealtimeStore.typing` |
| `TaskPanelSkeleton` | `Skeleton` | `{ }` | — |
| `TaskAuditFooter` | — | `{ task: Task; users: Record<string, UserLite> }` | — |

```ts
type Comment = {
  id: string;
  task_id: string;
  author_id: string;
  body_html: string;
  body_json: unknown | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
};

type TaskPanelProps = {
  taskId: string;
  listId: string;
  /** true when rendered via the intercepting route over a live list/board */
  intercepted?: boolean;
};
```

### Data requirements

| Purpose | Endpoint | Query key |
| --- | --- | --- |
| Task | `GET tasks/{id}/` | `['task', taskId]` |
| Comments | `GET tasks/{id}/comments/?page&page_size` | `['comments', taskId]` |
| Status set (for the picker) | `GET lists/{id}/status-set/` | `['list', listId, 'status-set']` |
| Members | `GET workspaces/{id}/members/` | `['workspace', workspaceId, 'members']` |
| Tags | `GET workspaces/{id}/tags/` | `['workspace', workspaceId, 'tags']` |
| Tree (Move dialog) | `GET workspaces/{id}/tree/` | `['workspace', workspaceId, 'tree']` |
| Field edits | `PATCH tasks/{id}/` | mutation `['task','update', taskId]` |
| Watch / unwatch | `POST tasks/{id}/watch/` · `DELETE tasks/{id}/watch/` | mutation `['task','watch', taskId]` |
| Delete task | `DELETE tasks/{id}/` | mutation `['task','delete', taskId]` |
| Add comment | `POST tasks/{id}/comments/` | mutation `['comment','create', taskId]` |
| Edit comment | `PATCH comments/{id}/` | mutation `['comment','update', commentId]` |
| Delete comment | `DELETE comments/{id}/` | mutation `['comment','delete', commentId]` |
| Move to another list | `PATCH tasks/{id}/` with `list_id` (+ `status_id` mapping) | mutation `['task','update', taskId]` |

Every successful `PATCH tasks/{id}/` writes into both `['task', taskId]` **and** the matching item inside `['tasks', listId, filters]` / the grouped key, so list, board and panel never disagree.

### Key interactions

1. Opening: clicking a row/card pushes `/w/{w}/l/{l}/t/{taskId}`. Because of the intercepting route the list/board stays mounted and its scroll position is preserved. A hard refresh renders the same panel over a server-rendered list.
2. `Esc` closes the panel and returns focus to the originating row/card. Closing does `router.back()` when the panel was intercepted, otherwise `router.replace('/w/{w}/l/{l}')`.
3. Focus trap while open: `Tab` cycles inside the panel; the first focusable element on open is the close button (announced), and the panel has `role="dialog"` `aria-modal="true"` `aria-labelledby={titleId}`.
4. `‹` / `›` (or `Alt+↑` / `Alt+↓`) navigate to the previous/next task **in the current view's order**, keeping the panel open and the list cursor in sync.
5. `e` focuses the title editor with the text selected. `Enter` commits, `Esc` cancels, blur commits.
6. Description: click-to-edit. Autosave is **debounced 800ms** while typing plus an explicit commit on blur; `Cmd/Ctrl+Enter` commits and exits edit mode; `Esc` discards the current editing session with a confirm if dirty. Both `description_html` and `description_json` are sent together in one `PATCH`.
7. `c` focuses the comment composer. `Cmd/Ctrl+Enter` sends. `Esc` blurs (draft is preserved per task in `sessionStorage`).
8. Typing in the composer emits a throttled `presence.typing` client→server frame at most once per 3s; the indicator clears after 5s of silence.
9. `w` toggles watch. `Cmd/Ctrl+.` copies the task deep link and toasts "Link copied".
10. Field pickers all open on `Enter`/`Space`, close on `Esc` returning focus to the trigger, and filter by typing (`Command` primitive).
11. Comment `⋯` menu shows Edit/Delete for the author (any role), and Delete only for `admin`/`owner` on other people's comments — matching "Everyone may edit/delete their OWN comment. admin/owner may delete any comment."
12. Realtime: an incoming `task.updated` for this task patches the panel field-by-field; a field currently being edited by the user is **not** overwritten — instead a subtle `--accent-blue` chip appears next to it reading "Ada changed this" with `[ Use theirs ]`.
13. `comment.created` appends to `['comments', taskId]` and, if the scroll is within 80px of the bottom, auto-scrolls; otherwise a "1 new comment ↓" pill appears.
14. `task.deleted` for the open task swaps the body for "This task was deleted by Ada." + `[ Close ]`.

### States

| State | What the user sees |
| --- | --- |
| Empty — no description | Muted placeholder "Add a description…" that becomes an editor on click (or is inert text for read-only roles). |
| Empty — no comments | "No comments yet. Start the conversation." above the composer. |
| Loading | `TaskPanelSkeleton`: title bar 28 × 60%, 8 field rows (label 80px + value 200px), a 3-line description block, and 2 comment blocks; `animate-pulse`. The panel animates in immediately — the skeleton never delays the 240ms slide. |
| Loading — comments only | Field grid is live; the comment area shows 3 comment skeletons. |
| Error — task fetch | Panel shows a centred `Alert`: `error.message`, `request_id`, `[ Retry ]`, `[ Close ]`. |
| Error — 404 | "This task no longer exists." + `[ Close ]`; the row is also removed from the list cache. |
| Error — field save | The field reverts, gets a `--danger` border for 2s, and a danger toast shows the message. |
| Permission denied | Read-only rendering: pickers become plain text with a lock icon; the header shows a `Badge` "View only"; hovering a locked field tooltips "Only assignees and members can edit this task." |
| Offline | Header shows an `--danger` "Offline" chip; all editors become read-only; the comment composer keeps its draft and disables Send with tooltip "Reconnect to send". |
| Reconnecting | `--accent-yellow` chip "Reconnecting…"; on resume the task and comments both refetch and changed fields flash `--accent-blue` for 240ms. |

### Validation & inline errors

| Field | Rule | Server mapping |
| --- | --- | --- |
| `title` | required, 1–500 chars | `error.details.title[0]` under the title, editor stays open |
| `description_html` / `description_json` | ≤ 100k chars serialised; sanitised client-side before send | `error.details.description_html[0]` |
| `status_id` | must be in the list's effective status set | `error.details.status_id[0]` / code `invalid_status_for_list` |
| `due_date`, `start_date` | ISO-8601 UTC `Z`; `due_date >= start_date` | `error.details.due_date[0]` under the calendar |
| `time_estimate_minutes` | integer ≥ 0, ≤ 100000; parse failure shows "Try 3h 30m" without hitting the API | `error.details.time_estimate_minutes[0]` |
| `assignee_ids`, `watcher_ids`, `tag_ids` | uuid arrays, each id must exist in the workspace | `error.details.<field>[0]` on the picker trigger |
| `list_id` (Move) | destination list must be in the same workspace; a `status_mapping` may be required | `error.details.list_id[0]` / `error.details.status_id[0]` |
| comment `body_html` | required, 1–10000 chars | `error.details.body_html[0]` under the composer; the draft is never cleared on error |

---

## S8 — Search & filter bar

**Purpose.** Narrow the current list (filter bar) and find anything across the workspace (search). Two surfaces, one filter model.
**Who can see it.** All roles. `include_deleted` is offered to `admin`/`owner` only.

### Wireframe

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ FILTER BAR (docked under the list/board header)                                           │
│ ┌───────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ [ 🔍 Filter tasks…            ] [assignee: me ✕] [priority: urgent, high ✕]           │ │
│ │ [due: this_week ✕] [tag: #api ✕] [status_type: open ✕]   [＋ Filter ▾]    Clear all   │ │
│ └───────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                           │
│  [＋ Filter ▾] popover:                                                                   │
│  ┌────────────────────────────────┐   ┌──────────────────────────────────┐                │
│  │ 🔍 Find a filter…              │ → │ 🔍 Find a person…                │                │
│  │ ─────────────────────────────  │   │ ─────────────────────────────    │                │
│  │  Status                        │   │ ☑ Me                             │                │
│  │  Status type                   │   │ ☐ Unassigned                     │                │
│  │  Assignee                    ▸ │   │ ─────────────────────────────    │                │
│  │  Priority                      │   │ ☑ (AB) Ada Lovelace              │                │
│  │  Tag                           │   │ ☐ (CD) Carl Dyer                 │                │
│  │  Due date                      │   │ ☐ (EF) Eve Foster                │                │
│  │  Created by                    │   │                                  │                │
│  │  Watcher                       │   │        [ Apply ]  (or live)      │                │
│  │  Archived                      │   └──────────────────────────────────┘                │
│  │  Deleted (admin)               │                                                       │
│  └────────────────────────────────┘                                                       │
├───────────────────────────────────────────────────────────────────────────────────────────┤
│ SEARCH RESULTS PAGE  /w/{id}/search?q=redirect                                            │
│  🔍 redirect                                                     [ Tasks ▪ ][ Everything ]│
│  ─────────────────────────────────────────────────────────────────────────────────────────│
│  TASKS (7)                                                                                │
│   ▪ Fix login redirect loop        ● To do    ⚑urgent  (AB)  Sprint 24     Aug 8          │
│   ▪ Redirect after invite accept   ● Done     ⚑normal  (CD)  Backlog       —              │
│  LISTS (1)         ▪ Redirects & routing        Product / Q3 Roadmap                      │
│  FOLDERS (0)       —                                                                      │
│  SPACES (0)        —                                                                      │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `FilterBar` | — | `{ scope: 'list' \| 'workspace'; listId?: string }` | Zustand `useFilterStore` + URL |
| `FilterChip` | `Badge` + `Popover` | `{ kind: FilterKind; label: string; values: string[]; onEdit(): void; onRemove(): void }` | — |
| `AddFilterMenu` | `Popover` + `Command` | `{ available: FilterKind[]; onPick(k: FilterKind): void }` | local |
| `FilterValuePicker` | `Command` + `Checkbox` | `{ kind: FilterKind; value: string[]; options: FilterOption[]; onChange(v: string[]): void }` | Query (members/tags/statuses) |
| `DueFilterPicker` | `RadioGroup` + `Calendar` | `{ value?: 'overdue'\|'today'\|'this_week'\|'none'; before?: string; after?: string; onChange(v): void }` | local |
| `QuickSearchInput` | `Input` | `{ value: string; onChange(v: string): void; placeholder: string }` | local, debounced 250ms |
| `ClearFiltersButton` | `Button` (ghost) | `{ count: number; onClear(): void }` | — |
| `SavedFilterHint` | `Tooltip` | `{ shareUrl: string }` | — |
| `SearchResultsPage` | — | `{ workspaceId: string; q: string; tab: 'tasks' \| 'all' }` | Query |
| `SearchResultGroup` | — | `{ title: string; items: SearchItem[]; emptyLabel: string }` | — |
| `SearchResultRow` | — | `{ item: SearchItem; query: string }` | — |
| `HighlightedText` | — | `{ text: string; query: string }` | — |

```ts
type FilterKind =
  | 'status' | 'status_type' | 'assignee' | 'priority' | 'tag'
  | 'due' | 'due_before' | 'due_after'
  | 'created_by' | 'watcher' | 'archived' | 'include_deleted' | 'q';

type SearchItem =
  | { kind: 'task'; task: Task; list: { id: string; name: string } }
  | { kind: 'list'; id: string; name: string; path: string }
  | { kind: 'folder'; id: string; name: string; path: string }
  | { kind: 'space'; id: string; name: string; color: string };
```

### Data requirements

| Purpose | Endpoint | Query key |
| --- | --- | --- |
| Filtered tasks in a list | `GET lists/{id}/tasks/?<filters>` | `['tasks', listId, filters]` |
| Cross-list filtered tasks | `GET workspaces/{id}/tasks/?<filters>` | `['workspace', workspaceId, 'tasks', filters]` |
| Mixed search (tasks, lists, folders, spaces) | `GET workspaces/{id}/search/?q=` | `['workspace', workspaceId, 'search', q]` |
| Filter option sources | `GET workspaces/{id}/members/`, `GET workspaces/{id}/tags/`, `GET lists/{id}/status-set/` | `['workspace', wid, 'members']`, `['workspace', wid, 'tags']`, `['list', listId, 'status-set']` |

**URL is the source of truth for filters.** Every filter change calls `router.replace(pathname + '?' + qs, { scroll: false })`, so filtered views are shareable and survive refresh. `useFilterStore` holds only the *draft* state inside an open picker.

Serialisation rules: repeatable params repeat (`?priority=urgent&priority=high`), not CSV. `archived` defaults to `false` and is omitted when false. `include_deleted` is stripped from the URL entirely for non-admin roles.

### Key interactions

1. `/` focuses the quick-search input of the current scope; `Esc` clears it and blurs.
2. `f` opens the `＋ Filter` menu; typing filters the filter names; `Enter` drills into the value picker; `Esc` steps back one level, then closes.
3. Filter changes apply **live** (no Apply button) for multi-selects; the picker stays open so several values can be ticked. Each change is debounced 250ms before the network call.
4. Chips are removable with the `✕` or by focusing the chip and pressing `Backspace`/`Delete`.
5. `Cmd/Ctrl+Shift+Backspace` clears all filters; `Clear all` is also a visible button when ≥1 filter is active.
6. Search input debounces 250ms and requires ≥2 characters; below that, results show "Keep typing…".
7. On the results page, `↑`/`↓` move through results across groups, `Enter` opens, `Cmd/Ctrl+Enter` opens the task panel over the results page.
8. Query terms are highlighted with `<mark>` styled as `--accent-yellow` at 35% alpha with inherited colour (never a colour-only cue).
9. The filter bar is `role="group"` `aria-label="Active filters"`; adding/removing a chip announces the new result count via the polite live region.

### States

| State | What the user sees |
| --- | --- |
| Empty — no filters | The bar collapses to just `[ 🔍 Filter tasks… ]  [＋ Filter]`; no `Clear all`. |
| Empty — no search query | Results page shows recent searches (local, last 5) and "Search tasks, lists, folders and spaces". |
| Empty — no results | "No results for 'redirect'." + suggestions: check spelling, remove filters, `[ Search all workspaces ]` is **not** offered (single-workspace scope in MVP). |
| Loading | Filter bar keeps chips interactive; the underlying table/board shows a translucent overlay at 60% plus `StaleIndicator`. Search page shows 6 result-row skeletons (16px circle + 50% bar + 20% bar). |
| Error | Inline `Alert` above the results with `error.message` and `[ Retry ]`; chips remain so the user can back out of a bad filter. |
| Permission denied | `403` on a cross-list search (e.g. `include_deleted` as a non-admin) → the offending chip is removed automatically with a toast "That filter is admin-only." |
| Offline | Search input disabled with placeholder "Search unavailable offline"; existing filter chips still filter the cached page client-side where possible (client-side narrowing only, never widening). |
| Reconnecting | Results stay; `StaleIndicator` visible; a refetch fires when the socket reopens. |

### Validation & inline errors

| Field | Rule | Server mapping |
| --- | --- | --- |
| `q` | ≤ 200 chars; ≥2 chars to fire | `error.details.q[0]` under the input |
| `due_before` / `due_after` | valid ISO-8601; `due_after <= due_before` | `error.details.due_before[0]` in the date popover |
| `page_size` | 1–200 (server max 200) | `error.details.page_size[0]` → snap back to 50 with a toast |
| unknown `ordering` | must be one of the allowed values | `error.details.ordering[0]` → reset to `position` |

---

## S9 — Members & workspace settings

**Purpose.** Manage who is in the workspace, their roles, and pending invitations; plus workspace-level general settings.
**Who can see it.** `admin` and `owner`. `member` gets a read-only member roster (no role controls, no invite form). **`guest` cannot see the members page at all** — the settings nav item is hidden and the route returns `not-found`.

### Wireframe

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│  Workspace settings — Acme Inc.                                                                   │
├──────────────────────┬────────────────────────────────────────────────────────────────────────────┤
│  General             │  Members                                                                   │
│  Members         ▪   │  ┌──────────────────────────────────────────────────────────────────────┐  │
│  Invitations         │  │ 🔍 Search members…            [ Role: All ▾ ]      [ ＋ Invite ]     │  │
│  Tags                │  └──────────────────────────────────────────────────────────────────────┘  │
│  Danger zone         │  ┌────┬───────────────────────┬──────────────────┬──────────┬───────────┐  │
│                      │  │    │ Name                  │ Email            │ Role     │ Joined    │  │
│                      │  ├────┼───────────────────────┼──────────────────┼──────────┼───────────┤  │
│                      │  │(AB)│ Ada Lovelace   (you)   │ ada@acme.com     │ Owner    │ Jan 12  ⋯│  │
│                      │  │(CD)│ Carl Dyer      ● online│ carl@acme.com    │[Admin ▾] │ Feb 03  ⋯│  │
│                      │  │(EF)│ Eve Foster            │ eve@acme.com     │[Member▾] │ Mar 21  ⋯│  │
│                      │  │(GH)│ Gus Hall              │ gus@vendor.io    │[Guest ▾] │ Jul 02  ⋯│  │
│                      │  └────┴───────────────────────┴──────────────────┴──────────┴───────────┘  │
│                      │   ⋯ menu → Change role · Remove from workspace · Transfer ownership (owner)│
│                      │                                                                            │
│                      │  Pending invitations (2)                                                   │
│                      │  ┌───────────────────────┬──────────┬───────────┬────────────┬──────────┐  │
│                      │  │ Email                 │ Role     │ Invited by│ Expires    │          │  │
│                      │  ├───────────────────────┼──────────┼───────────┼────────────┼──────────┤  │
│                      │  │ new.dev@acme.com      │ Member   │ Ada       │ in 6 days  │ Resend ⋯ │  │
│                      │  │ auditor@vendor.io     │ Guest    │ Carl      │ EXPIRED    │ Resend ⋯ │  │
│                      │  └───────────────────────┴──────────┴───────────┴────────────┴──────────┘  │
│                      │                                                                            │
│                      │  ─────────────────────────────────────────────────────────────────────────│
│                      │  Danger zone                                                     (owner)   │
│                      │  ┌──────────────────────────────────────────────────────────────────────┐  │
│                      │  │ Leave workspace          You'll lose access immediately.  [ Leave ]  │  │
│                      │  │ Delete workspace         Permanently deletes everything. [ Delete ]  │  │
│                      │  └──────────────────────────────────────────────────────────────────────┘  │
└──────────────────────┴────────────────────────────────────────────────────────────────────────────┘

  Invite dialog:
  ┌─────────────────────────────────────────────────────────┐
  │  Invite people to Acme Inc.                        ✕    │
  │  Email addresses                                        │
  │  ┌───────────────────────────────────────────────────┐  │
  │  │ [new.dev@acme.com ×] [qa@acme.com ×] |            │  │
  │  └───────────────────────────────────────────────────┘  │
  │  ⚠ "not-an-email" isn't a valid address.                │
  │  Role   ( ) Admin  (•) Member  ( ) Guest                │
  │  Guests can read and comment, but can't create lists.   │
  │                          [ Cancel ]  [ Send invites ]   │
  └─────────────────────────────────────────────────────────┘
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `SettingsShell` | — | `{ workspaceId: string; children: ReactNode }` | server |
| `SettingsNav` | `Tabs` (vertical) | `{ items: { href: string; label: string; visible: boolean }[] }` | route |
| `MembersTable` | `Table` | `{ workspaceId: string; currentUserId: string; currentRole: Role }` | Query `['workspace', wid, 'members']` |
| `MemberRow` | `TableRow` | `{ member: Member; canManage: boolean; isSelf: boolean; isOnline: boolean }` | — |
| `RoleSelect` | `Select` | `{ value: Role; options: Role[]; disabled: boolean; onChange(r: Role): void }` | mutation |
| `MemberActionsMenu` | `DropdownMenu` | `{ member: Member; currentRole: Role; isSelf: boolean }` | local |
| `MemberSearchInput` | `Input` | `{ value: string; onChange(v: string): void }` | local (client-side filter) |
| `RoleFilterSelect` | `Select` | `{ value: Role \| 'all'; onChange(v): void }` | local |
| `InviteDialog` | `Dialog` + `Form` | `{ workspaceId: string; open: boolean; onOpenChange(o: boolean): void }` | local |
| `EmailTokenInput` | `Input` + `Badge` | `{ value: string[]; onChange(v: string[]): void; invalid: string[] }` | local |
| `RoleRadioGroup` | `RadioGroup` | `{ value: 'admin' \| 'member' \| 'guest'; onChange(v): void }` | local |
| `InvitationsTable` | `Table` | `{ workspaceId: string }` | Query `['workspace', wid, 'invitations']` |
| `InvitationRow` | `TableRow` | `{ invitation: Invitation; onResend(): void; onRevoke(): void }` | — |
| `TransferOwnershipDialog` | `AlertDialog` + `Command` | `{ workspaceId: string; members: Member[] }` | local |
| `RemoveMemberDialog` | `AlertDialog` | `{ member: Member }` | local |
| `LeaveWorkspaceDialog` | `AlertDialog` | `{ workspaceId: string; isLastOwner: boolean }` | local |
| `DeleteWorkspaceDialog` | `AlertDialog` + `Input` | `{ workspaceId: string; name: string }` | local |
| `DangerZoneCard` | `Card` | `{ children: ReactNode }` | — |
| `MembersTableSkeleton` | `Skeleton` | `{ rows?: number }` | — |
| `RoleBadge` | `Badge` | `{ role: Role }` | — |

```ts
type Member = {
  user_id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  role: Role;                 // 'owner' | 'admin' | 'member' | 'guest'
  joined_at: string;
};

type Invitation = {
  id: string;
  email: string;
  role: 'admin' | 'member' | 'guest';
  invited_by_id: string;
  expires_at: string;
  status: 'pending' | 'accepted' | 'revoked' | 'expired';
  created_at: string;
};
```

### Data requirements

| Purpose | Endpoint | Query key |
| --- | --- | --- |
| Members roster | `GET workspaces/{id}/members/` | `['workspace', wid, 'members']` |
| Change role | `PATCH workspaces/{id}/members/{user_id}/` | mutation `['member','update', userId]` |
| Remove member | `DELETE workspaces/{id}/members/{user_id}/` | mutation `['member','remove', userId]` |
| Leave workspace | `POST workspaces/{id}/members/leave/` | mutation `['member','leave']` |
| Invitations | `GET workspaces/{id}/invitations/` | `['workspace', wid, 'invitations']` |
| Create invitations | `POST workspaces/{id}/invitations/` | mutation `['invitation','create']` |
| Revoke invitation | `DELETE invitations/{id}/` | mutation `['invitation','revoke', id]` |
| Resend invitation | `POST invitations/{id}/resend/` | mutation `['invitation','resend', id]` |
| Workspace general | `GET workspaces/{id}/` · `PATCH workspaces/{id}/` | `['workspace', wid]` |
| Delete workspace | `DELETE workspaces/{id}/` | mutation `['workspace','delete', wid]` |
| Transfer ownership | `PATCH workspaces/{id}/members/{user_id}/` with `role: "owner"` | mutation `['member','update', userId]` |

### Role gating matrix (UI affordances)

| Affordance | owner | admin | member | guest |
| --- | --- | --- | --- | --- |
| See Members page | ✔ | ✔ | ✔ (read-only) | ✖ (route 404) |
| Invite people | ✔ | ✔ | ✖ | ✖ |
| Change a member's role | ✔ (any) | ✔ (except owners) | ✖ | ✖ |
| Promote someone to `owner` | ✔ | ✖ | ✖ | ✖ |
| Remove a member | ✔ (any) | ✔ (except owners) | ✖ | ✖ |
| Revoke / resend invitation | ✔ | ✔ | ✖ | ✖ |
| Rename workspace | ✔ | ✔ | ✖ | ✖ |
| Delete workspace | ✔ | ✖ | ✖ | ✖ |
| Leave workspace | ✔ (unless last owner) | ✔ | ✔ | ✔ |
| Manage tags | ✔ | ✔ | ✔ | ✖ |
| Manage statuses (S11) | ✔ | ✔ | ✖ | ✖ |

### Key interactions

1. Own row's `RoleSelect` is always disabled with tooltip "You can't change your own role."
2. An `admin` sees `owner` rows with a static `RoleBadge` instead of a `Select`, and no `⋯` menu on them.
3. Changing a role is optimistic: the select updates immediately, then reconciles; on error it reverts and a danger toast shows `error.message`.
4. Demoting the **last** owner is blocked client-side ("A workspace needs at least one owner.") and again server-side.
5. Transfer ownership opens an `AlertDialog` with a searchable member `Command` list, then requires typing the workspace name to confirm; the acting user is demoted to `admin` on success and the page refetches.
6. Removing a member requires confirmation naming them; the dialog warns "Their tasks stay, but they'll be unassigned."
7. `EmailTokenInput` tokenises on `Enter`, `,`, `Space`, `Tab`, and on paste (splits on `[,\s;]+`). Invalid addresses become `--danger` chips and block submit. Max 20 per submit.
8. `Resend` is rate-limited client-side to once per 60s per invitation; the button becomes "Sent ✓" for 3s then a disabled countdown.
9. Delete workspace requires typing the exact workspace name; the confirm button stays disabled until it matches exactly (case-sensitive).
10. Member search filters client-side (the roster is small); the role filter is also client-side.
11. Presence dots on member rows come from `useRealtimeStore().presence` and update live.
12. All dialogs return focus to their trigger on close.

### States

| State | What the user sees |
| --- | --- |
| Empty — only you | Table shows one row plus an inline callout "It's just you here." + `[ ＋ Invite ]`. |
| Empty — no invitations | "No pending invitations." in a 48px-padded muted block. |
| Loading | `MembersTableSkeleton`: 6 rows of `28px avatar circle + 140px bar + 180px bar + 80px pill + 70px bar`, `animate-pulse`. Header controls render live. |
| Error | Table body replaced by an `Alert` with `error.message`, `request_id`, `[ Retry ]`. |
| Permission denied — page | `member` hitting `/settings/members`: renders read-only. `guest`: `not-found.tsx`. Direct `403` from the API renders "You don't have permission to view members." + `[ Back to workspace ]`. |
| Permission denied — action | `403` on a role change → revert, toast "Only owners can do that." and the control disables for the session. |
| Conflict | `409 conflict` on invite (already a member / already invited) → the offending email chip turns `--danger` with an inline reason; other invites in the same batch still send. |
| Offline | All mutating controls disabled with a banner "You're offline — member changes are unavailable." Roster renders from cache. |
| Reconnecting | Yellow banner "Reconnecting…"; the roster refetches on resume. |

### Validation & inline errors

| Field | Rule | Server mapping |
| --- | --- | --- |
| invite `email` (each) | valid email, ≤254 chars, not already a member, not already invited, max 20 per submit | `error.details.email[0]` → mapped onto the specific chip; batch-level errors go to `error.details.emails[i]` |
| invite `role` | one of `admin` / `member` / `guest` (never `owner`) | `error.details.role[0]` under the radio group |
| `role` change | target role valid for the actor's role | `error.details.role[0]` → inline under the select as a `--danger` `text-xs` line |
| workspace `name` | required, 1–120 chars | `error.details.name[0]` |
| delete confirmation | must equal the workspace name exactly | client-only; server returns `403` if the actor is not owner |
| leave | blocked if last owner | `error.message` in the dialog: "Transfer ownership before leaving." |

---

## S10 — User profile settings

**Purpose.** Edit the signed-in user's own name, avatar, password and appearance preferences.
**Who can see it.** Any authenticated user, regardless of workspace role. Only ever shows the caller's own record.

### Wireframe

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Your settings                                                               │
├────────────────┬─────────────────────────────────────────────────────────────┤
│  Profile   ▪   │  Profile                                                    │
│  Account       │  ┌───────────────────────────────────────────────────────┐  │
│  Appearance    │  │   ┌────────┐                                          │  │
│  Sessions      │  │   │  (AB)  │  [ Upload photo ]  [ Remove ]            │  │
│                │  │   │  80px  │  PNG or JPG, max 2 MB, square works best │  │
│                │  │   └────────┘  ⚠ File is larger than 2 MB.             │  │
│                │  │                                                       │  │
│                │  │   Full name                                           │  │
│                │  │   ┌─────────────────────────────────────────────────┐ │  │
│                │  │   │ Ada Lovelace                                    │ │  │
│                │  │   └─────────────────────────────────────────────────┘ │  │
│                │  │   Email                                               │  │
│                │  │   ┌─────────────────────────────────────────────────┐ │  │
│                │  │   │ ada@acme.com                       (read-only)  │ │  │
│                │  │   └─────────────────────────────────────────────────┘ │  │
│                │  │   Email changes aren't supported in the MVP.          │  │
│                │  │                              [ Discard ] [ Save ]     │  │
│                │  └───────────────────────────────────────────────────────┘  │
│                │  Account                                                    │
│                │  ┌───────────────────────────────────────────────────────┐  │
│                │  │   Current password   [ ••••••••        ] 👁            │  │
│                │  │   New password       [ ••••••••••••    ] 👁            │  │
│                │  │   ▓▓▓▓▓▓▓▓░░░  Strong                                 │  │
│                │  │   Confirm new        [ ••••••••••••    ] 👁            │  │
│                │  │   ⚠ Passwords don't match.                            │  │
│                │  │   You'll stay signed in on this device only.          │  │
│                │  │                              [ Change password ]      │  │
│                │  └───────────────────────────────────────────────────────┘  │
│                │  Appearance                                                 │
│                │  ┌───────────────────────────────────────────────────────┐  │
│                │  │   Theme    ( ) Light   ( ) Dark   (•) System           │  │
│                │  │   ┌───────┐ ┌───────┐ ┌───────┐  (live preview tiles) │  │
│                │  │   └───────┘ └───────┘ └───────┘                       │  │
│                │  │   Reduce motion  [ Follow system ▾ ]                   │  │
│                │  └───────────────────────────────────────────────────────┘  │
└────────────────┴─────────────────────────────────────────────────────────────┘
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `ProfileForm` | `Form` + `Input` | `{ me: Me }` | local (`react-hook-form`), seeded from Query |
| `AvatarUploader` | `Avatar` + hidden `input[type=file]` | `{ src: string \| null; name: string; onUpload(f: File): void; onRemove(): void; maxBytes: number }` | local + mutation |
| `PasswordChangeForm` | `Form` | `{ }` | local |
| `PasswordStrengthMeter` | `Progress` | see S2 | local |
| `ThemeRadioCards` | `RadioGroup` + `Card` | `{ value: 'light' \| 'dark' \| 'system'; onChange(v): void }` | Zustand `useUiStore.theme` |
| `ReducedMotionSelect` | `Select` | `{ value: 'system' \| 'always' \| 'never'; onChange(v): void }` | Zustand `useUiStore.motion` |
| `SessionsList` | `Table` | `{ }` | out of MVP scope — renders "Coming soon" |
| `UnsavedChangesBar` | `Card` (sticky) | `{ dirty: boolean; pending: boolean; onSave(): void; onDiscard(): void }` | local |

```ts
type Me = {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  created_at: string;
  updated_at: string;
};
```

### Data requirements

| Purpose | Endpoint | Query key |
| --- | --- | --- |
| Load profile | `GET me/` | `['me']` |
| Save profile | `PATCH me/` | mutation `['me','update']` |
| Upload avatar | `POST me/avatar/` (multipart `file`) | mutation `['me','avatar']` |
| Remove avatar | `PATCH me/` with `avatar_url: null` | mutation `['me','update']` |
| Change password | `POST auth/password/change/` | mutation `['auth','password-change']` |
| Sign out | `POST auth/logout/` | mutation `['auth','logout']` |

A successful `PATCH me/` writes `['me']` and also patches the cached `full_name`/`avatar_url` inside `['workspace', wid, 'members']` so the roster and every avatar update without a refetch.

### Key interactions

1. The form is dirty-tracked; the sticky `UnsavedChangesBar` slides up (`duration-base`) when dirty and `Cmd/Ctrl+S` saves. Navigating away while dirty triggers a `beforeunload` guard and a Next.js route-change confirm.
2. Avatar upload validates type (`image/png`, `image/jpeg`, `image/webp`) and size (≤2 MB) **before** the request; the preview swaps immediately and shows a determinate `Progress` during upload.
3. Removing the avatar falls back to initials on a deterministic accent colour derived from `user.id` (`accent-pink` / `accent-blue` / `accent-yellow` / `accent-green` / `primary`), always with `--primary-fg` text.
4. Password change requires all three fields; on success it toasts "Password changed" and clears the form. Because `ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION` are on, the client immediately stores the new token pair if one is returned; otherwise it silently re-authenticates via `POST auth/refresh/`.
5. Theme change applies instantly (no save) and writes `localStorage["clickish.theme"]`; the three preview tiles render live miniatures of the shell.
6. Reduce motion: `always` adds a `reduce-motion` class that forces the same rules as `prefers-reduced-motion`; `never` opts out; `system` follows the media query.
7. `Esc` in any input reverts that field to its last saved value.

### States

| State | What the user sees |
| --- | --- |
| Empty | Never empty — `GET me/` always resolves for an authenticated user. Missing avatar shows initials. |
| Loading | Skeleton: 80px circle + two 320px input bars + one button bar; the left settings nav renders live. |
| Loading — upload | Avatar shows a 60% dark scrim + determinate progress ring; Save is disabled meanwhile. |
| Error — save | Field-level messages from `error.details`; the `UnsavedChangesBar` stays visible so the user can retry. |
| Error — upload | Danger text under the avatar with `error.details.file[0]`; the previous avatar is restored. |
| Error — password | `400 validation_error` maps to `error.details.old_password` / `.new_password`; a wrong current password focuses that field. |
| Permission denied | Not applicable — the endpoint is always self-scoped. A `401 authentication_failed` triggers a refresh attempt, then a redirect to `/login?next=/settings/profile`. |
| Offline | Banner "You're offline — changes can't be saved."; Save and Upload disabled; theme changes still work (local only). |
| Reconnecting | Non-blocking; `['me']` refetches when connectivity returns and a background diff toast appears only if the server value differs from the local draft. |

### Validation & inline errors

| Field | Rule | Server mapping |
| --- | --- | --- |
| `full_name` | required, 1–150 chars | `error.details.full_name[0]` |
| `email` | read-only in MVP | — |
| avatar `file` | `image/png\|jpeg\|webp`, ≤2 MB, ≥64×64 | `error.details.file[0]` |
| `old_password` | required | `error.details.old_password[0]` — "Your current password is incorrect." |
| `new_password` | required, ≥8 chars, not entirely numeric, ≠ `old_password` | `error.details.new_password[0]` |
| `confirm_password` | client-only, must equal `new_password` | client message "Passwords don't match." |

---

## S11 — Status-set editor (per space / per list)

**Purpose.** Create and order the `Status` rows of a `StatusSet`, which belongs to **either** a Space **or** a TaskList (never both), and remap tasks when a list's status set changes.
**Who can see it.** `owner` and `admin` only. `member` and `guest` see statuses as read-only chips elsewhere and get a `not-found` on this route.

### Wireframe

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│  Statuses — Sprint 24                                                          ✕           │
│  ┌──────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  Scope   (•) Inherit from space "Product"      ( ) Custom for this list               │  │
│  │          Editing the inherited set changes every list in Product that inherits it.    │  │
│  └──────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                            │
│  ┌────┬──────────────────────────────┬──────────┬───────────────┬─────────┬─────────────┐  │
│  │ ⠿  │ Name                         │ Colour   │ Type          │ Default │             │  │
│  ├────┼──────────────────────────────┼──────────┼───────────────┼─────────┼─────────────┤  │
│  │ ⠿  │ [ To do                    ] │ [#87909E]│ [ Open     ▾ ]│   (•)   │  🗑 (8 tasks)│  │
│  │ ⠿  │ [ In progress              ] │ [#4194F6]│ [ Active   ▾ ]│   ( )   │  🗑 (5 tasks)│  │
│  │ ⠿  │ [ In review                ] │ [#4194F6]│ [ Active   ▾ ]│   ( )   │  🗑 (2 tasks)│  │
│  │ ⠿  │ [ Done                     ] │ [#6BC950]│ [ Closed   ▾ ]│   ( )   │  🗑 (11 …)  │  │
│  │    │ ▔▔▔▔▔▔ drop indicator ▔▔▔▔▔▔ │          │               │         │             │  │
│  │ ⠿  │ [ Won't do                 ] │ [#87909E]│ [ Closed   ▾ ]│   ( )   │  🗑 (0)     │  │
│  └────┴──────────────────────────────┴──────────┴───────────────┴─────────┴─────────────┘  │
│  [ ＋ Add status ]                                                                          │
│                                                                                            │
│  Rules                                                                                     │
│   ✓ Exactly one status must be the default for new tasks.                                  │
│   ✓ At least one status of type "closed" is required.                                      │
│   ✗ "In review" has no tasks — safe to delete.                                             │
│                                                                                            │
│  ─── Remap required ────────────────────────────────────────────────────────────────────── │
│  You're switching this list to a custom status set. Choose where existing tasks go:        │
│  ┌──────────────────────────────┬──────────────────────────────────────────────────────┐   │
│  │ From (inherited)             │ To (custom)                                          │   │
│  ├──────────────────────────────┼──────────────────────────────────────────────────────┤   │
│  │ ● To do          8 tasks     │ [ ● Backlog                                     ▾ ]  │   │
│  │ ● In progress    5 tasks     │ [ ● Doing                                       ▾ ]  │   │
│  │ ● Done          11 tasks     │ [ ● Shipped                                     ▾ ]  │   │
│  └──────────────────────────────┴──────────────────────────────────────────────────────┘   │
│  ⚠ Every source status must be mapped before you can save.                                 │
│                                                                                            │
│                                                    [ Reset to default ] [ Cancel ] [ Save ]│
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `StatusSetEditor` | `Dialog` (from a list) / page (from settings) | `{ scope: 'space' \| 'list'; scopeId: string }` | Query + local draft |
| `ScopeRadioGroup` | `RadioGroup` | `{ value: 'inherit' \| 'custom'; inheritedFrom: string; onChange(v): void; disabled: boolean }` | local |
| `StatusRowList` | `DndContext` + `SortableContext` | `{ statuses: StatusDraft[]; onReorder(ids: string[]): void }` | local draft |
| `StatusRow` | `TableRow` + `useSortable` | `{ status: StatusDraft; taskCount: number; canDelete: boolean }` | local draft |
| `StatusNameInput` | `Input` | `{ value: string; onChange(v: string): void; error?: string }` | local |
| `ColorSwatchPicker` | `Popover` + swatch grid | `{ value: string; onChange(hex: string): void; presets: string[] }` | local |
| `StatusTypeSelect` | `Select` | `{ value: 'open' \| 'active' \| 'closed'; onChange(v): void }` | local |
| `DefaultStatusRadio` | `RadioGroup` (single across rows) | `{ value: string; onChange(statusId: string): void }` | local |
| `StatusRulesPanel` | `Alert` | `{ rules: { id: string; label: string; ok: boolean }[] }` | derived |
| `StatusMappingTable` | `Table` + `Select` | `{ from: Status[]; to: StatusDraft[]; value: Record<string,string>; onChange(m): void; counts: Record<string,number> }` | local |
| `ResetToDefaultButton` | `AlertDialog` | `{ scopeId: string }` | local |
| `StatusSetEditorSkeleton` | `Skeleton` | `{ rows?: number }` | — |

```ts
type StatusDraft = {
  id: string;                 // client uuid for new rows
  name: string;
  color: string;              // #RRGGBB
  type: 'open' | 'active' | 'closed';
  order: number;              // integer — NOT the fractional position field
  is_default: boolean;
  _new?: boolean;
  _deleted?: boolean;
};

type StatusSetPayload = {
  statuses: Array<Omit<StatusDraft, '_new' | '_deleted'>>;
  status_mapping?: Record<string, string>;   // { old_status_id: new_status_id }
};
```

### Data requirements

| Purpose | Endpoint | Query key |
| --- | --- | --- |
| Space status set | `GET spaces/{id}/status-set/` | `['space', spaceId, 'status-set']` |
| Replace space status set | `PUT spaces/{id}/status-set/` | mutation `['status-set','put','space', spaceId]` |
| List effective status set | `GET lists/{id}/status-set/` | `['list', listId, 'status-set']` |
| Give a list its own status set (or replace it) | `PUT lists/{id}/status-set/` with `status_mapping` | mutation `['status-set','put','list', listId]` |
| Revert a list to the space's set | `DELETE lists/{id}/status-set/` | mutation `['status-set','delete','list', listId]` |
| Task counts per status (for the remap table) | `GET lists/{id}/tasks/?group_by=status` | `['tasks', listId, {}, { groupBy: 'status' }]` |

Invalidations after a successful save: `['list', listId, 'status-set']`, `['space', spaceId, 'status-set']`, every `['tasks', listId, ...]`, `['workspace', wid, 'tree']`.

### Key interactions

1. Reordering rows sets `Status.order` (an **integer**, unlike the fractional `position` used for tasks/lists). The client renumbers the whole draft `0..n-1` on every drop; nothing is sent until Save.
2. Drag uses the `⠿` handle only, `KeyboardSensor` enabled, same lift/move/drop grammar as §6.6.
3. `＋ Add status` appends a row with a client uuid, focus in the name field, colour prefilled from the type token (`open` → `#87909E`, `active` → `#4194F6`, `closed` → `#6BC950`).
4. Changing a row's `type` re-prefills its colour **only if** the colour still equals the previous type's token (never overwrites a deliberate colour).
5. The `Default` column is a single radio across all rows — picking one clears the previous; the constraint "exactly one `is_default`" is therefore structurally enforced.
6. Deleting a status with tasks is blocked: the 🗑 disables with tooltip "Move its 8 tasks first." Deleting an empty status is instant in the draft and reversible until Save.
7. Switching Scope from `inherit` to `custom` seeds the draft from the inherited set and reveals `StatusMappingTable`; switching back to `inherit` shows an `AlertDialog` warning that the custom set (and mapping) will be dropped via `DELETE lists/{id}/status-set/`.
8. Save is disabled while any rule fails; hovering it explains which rule.
9. `Esc` closes with an unsaved-changes confirm when dirty. `Cmd/Ctrl+S` saves.
10. On save the whole set is `PUT` at once (not per-row) — the endpoint is a replace, so the draft is the payload.

### States

| State | What the user sees |
| --- | --- |
| Empty — impossible for a space | A Space always has a status set (auto-created), so the editor is never empty in space scope. |
| Empty — list inherits | Scope radio on "Inherit"; rows render read-only and greyed with a note "Editing here would change the whole space. Choose Custom to make a list-only set." |
| Loading | `StatusSetEditorSkeleton`: 5 rows of `16px handle + 200px bar + 24px swatch + 100px pill + 20px circle`. Save/Cancel disabled. |
| Error — load | `Alert` with `error.message` + `[ Retry ]`; the dialog stays open. |
| Error — save | Footer `Alert` `--danger`; per-row errors from `error.details.statuses[i].name` are rendered on the offending row. |
| Error — mapping required | `400` with `error.details.status_mapping` → the remap table scrolls into view and unmapped source rows get a `--danger` border. |
| Permission denied | `member`/`guest` route → `not-found`. A `403` on save → "Only admins can change statuses." and the editor becomes read-only. |
| Offline | Save disabled with tooltip; the draft is preserved in memory (not persisted) and the dialog warns before closing. |
| Reconnecting | If a `task.updated` arrives while the editor is open, the per-status task counts update live; the draft is untouched. |

### Validation & inline errors

| Field | Rule | Server mapping |
| --- | --- | --- |
| `name` | required, 1–60 chars, unique within the set (case-insensitive) | `error.details.statuses[i].name[0]` |
| `color` | `#RRGGBB` hex | `error.details.statuses[i].color[0]` |
| `type` | one of `open` / `active` / `closed` | `error.details.statuses[i].type[0]` |
| `order` | integers, contiguous from 0 | `error.details.statuses[i].order[0]` |
| `is_default` | **exactly one** `true` across the set | `error.details.statuses[0].is_default[0]` or `error.message` "Exactly one status must be the default." |
| closed requirement | **at least one** status of type `closed` | `error.message` "At least one closed status is required." |
| `status_mapping` | required when a list changes status set and tasks exist; must cover every source status; targets must be in the new set | `error.details.status_mapping[0]` and `error.details.status_mapping.<old_status_id>[0]` |
| cross-check | a task's status must belong to its list's effective set | code `invalid_status_for_list` |

---

## S12 — Command palette (Cmd+K)

**Purpose.** One keystroke to reach anything: navigate to a list, jump to a task, run an action, switch workspace or theme.
**Who can see it.** Any authenticated user. Commands are filtered by role — a `guest` never sees "New list" or "Invite people".

### Wireframe

```
              ┌─────────────────────────────────────────────────────────────────┐
              │  🔍  redirect|                                          Esc     │
              ├─────────────────────────────────────────────────────────────────┤
              │  TASKS                                                          │
              │   ▪ Fix login redirect loop        ● To do   Sprint 24      ↵   │
              │   ▪ Redirect after invite accept   ● Done    Backlog            │
              │  LISTS                                                          │
              │   ▪ Redirects & routing            Product / Q3 Roadmap         │
              │  SPACES & FOLDERS                                               │
              │   ● Product                                                     │
              │  ACTIONS                                                        │
              │   ＋ New task in Sprint 24                                 t    │
              │   ＋ New list in Q3 Roadmap                                     │
              │   ⇄ Switch to Board view                                   2    │
              │   👤 Invite people…                              (admin only)   │
              │   ◐ Toggle theme                                                │
              │   ⌘ Show keyboard shortcuts                              ⇧?     │
              │  RECENT                                                         │
              │   ▪ Sprint 25                                                   │
              ├─────────────────────────────────────────────────────────────────┤
              │  ↑↓ navigate   ↵ open   ⌘↵ open in panel   esc close            │
              └─────────────────────────────────────────────────────────────────┘
                 640px wide, max-h 60vh, rounded-xl, shadow-lg, z-palette
                 scrim: --foreground at 40%; enter 180ms scale .98→1 + fade
```

### Component breakdown

| Component | Primitive | Props | State owner |
| --- | --- | --- | --- |
| `CommandPalette` | `CommandDialog` (`Dialog` + `Command`) | `{ workspaceId: string }` | Zustand `usePaletteStore` |
| `PaletteInput` | `CommandInput` | `{ value: string; onValueChange(v: string): void }` | Zustand |
| `PaletteGroup` | `CommandGroup` | `{ heading: string; children: ReactNode }` | — |
| `PaletteItem` | `CommandItem` | `{ id: string; icon: ReactNode; label: string; hint?: string; shortcut?: string; onSelect(): void }` | — |
| `PaletteEmpty` | `CommandEmpty` | `{ query: string }` | — |
| `PaletteFooterHints` | — | `{ }` | — |
| `PaletteSkeleton` | `Skeleton` | `{ rows?: number }` | — |
| `ShortcutsDialog` | `Dialog` | `{ open: boolean; onOpenChange(o: boolean): void }` | Zustand |

```ts
type PaletteCommand = {
  id: string;
  group: 'tasks' | 'lists' | 'spaces' | 'actions' | 'recent';
  label: string;
  hint?: string;
  shortcut?: string;
  icon: LucideIcon;
  /** null means always visible */
  requiresRole?: Array<'owner' | 'admin' | 'member' | 'guest'> | null;
  run: (ctx: PaletteContext) => void | Promise<void>;
};
```

### Data requirements

| Purpose | Endpoint | Query key |
| --- | --- | --- |
| Navigation targets (lists, folders, spaces) | already cached: `GET workspaces/{id}/tree/` | `['workspace', wid, 'tree']` |
| Task + mixed search (only when `q.length >= 2`) | `GET workspaces/{id}/search/?q=` | `['workspace', wid, 'search', q]` |
| Workspace list | `GET workspaces/` | `['workspaces']` |
| Role for command gating | `GET workspaces/{id}/members/` | `['workspace', wid, 'members']` |

The palette **never** fires a request on open. Tree/space/list matching is purely client-side over the cached tree; only task search hits the network, debounced 200ms, with `keepPreviousData: true` so the list does not flicker.

### Key interactions

1. `Cmd+K` (macOS) / `Ctrl+K` (Windows/Linux) opens from anywhere except when a text input has focus *and* the user is mid-IME-composition. `Cmd/Ctrl+K` again closes it.
2. `Esc` closes and returns focus to the previously focused element (stored on open).
3. `↑` / `↓` move through items across groups; `Home`/`End` jump; the active item is scrolled into view; selection is announced via `aria-activedescendant`.
4. `Enter` runs the item. `Cmd/Ctrl+Enter` on a task opens it in the slide-over over the current view instead of navigating.
5. Typing `>` at the start restricts to Actions; `#` restricts to Tasks; `@` restricts to People (assign-to-me style actions). The prefix renders as a `Badge` inside the input.
6. Recent items are the last 8 visited lists/tasks per workspace from `localStorage["clickish.recent"]`, shown when the query is empty.
7. Actions are context-aware: "New task in {current list}" only appears while a list is open; "Switch to Board view" only appears in List view.
8. Role gating removes commands entirely rather than disabling them, so the palette never advertises what the user cannot do.
9. `Shift+?` from the palette (or globally) opens `ShortcutsDialog`.
10. The palette is a modal dialog: focus trapped, background `aria-hidden`, body scroll locked.

### States

| State | What the user sees |
| --- | --- |
| Empty — no query | Recent items + Actions, no network call. |
| Empty — 1 character | "Keep typing to search tasks…" while local list/space matching still works. |
| Empty — no matches | `CommandEmpty`: "No results for 'xyz'." + `[ Create task "xyz" ]` action when a list is open. |
| Loading | Local groups render instantly; the TASKS group shows 3 shimmer rows (16px circle + 60% bar) while the search request is in flight; previous results stay visible underneath thanks to `keepPreviousData`. |
| Error | The TASKS group is replaced by an inline `--danger` row "Search failed. Press ↵ to retry." Local navigation still works. |
| Permission denied | Gated commands are simply absent. A `403` at run time toasts "You don't have permission to do that." and keeps the palette open. |
| Offline | A muted footer chip "Offline — searching cached items only"; the TASKS group falls back to matching whatever is already in the query cache. |
| Reconnecting | Same as offline, plus the chip reads "Reconnecting…"; the current query re-runs automatically once the connection returns. |

### Validation & inline errors

The palette has one input and no submit; there is no field validation. Errors from a command's `run()` surface as toasts, never inside the palette body, except the search-failure row above.

---

# 6. Drag & drop specification

**Library decision: dnd-kit.** `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/modifiers` + `@dnd-kit/accessibility`. Chosen over `react-beautiful-dnd` (unmaintained, no React 19 support) and native HTML5 DnD (no touch, no keyboard, unstylable drag image). No other DnD library may be introduced.

## 6.1 Sensors

```ts
const sensors = useSensors(
  useSensor(PointerSensor, {
    activationConstraint: { distance: 4 },       // 4px so clicks still open the task
  }),
  useSensor(TouchSensor, {
    activationConstraint: { delay: 200, tolerance: 8 }, // long-press; scrolling still works
  }),
  useSensor(KeyboardSensor, {
    coordinateGetter: sortableKeyboardCoordinates,
    scrollBehavior: 'smooth',
  }),
);
```

| Surface | `DndContext` | Strategy | Collision detection | Modifiers |
| --- | --- | --- | --- | --- |
| S5 List view | one per list, wrapping all groups | `verticalListSortingStrategy` per group | `closestCenter` | `restrictToVerticalAxis`, `restrictToParentElement` |
| S6 Board view | one per board, wrapping all columns | `verticalListSortingStrategy` per column | `pointerWithin` → fallback `rectIntersection` | none (free 2D movement) |
| S4 Sidebar list reorder | one per tree | `verticalListSortingStrategy` per `(space, folder)` scope | `closestCenter` | `restrictToVerticalAxis` |
| S11 Status rows | one per editor | `verticalListSortingStrategy` | `closestCenter` | `restrictToVerticalAxis`, `restrictToParentElement` |

Board uses `pointerWithin` because column bodies are large containers; `closestCenter` would snap to a far column's card when the pointer is in empty space.

## 6.2 Drag handle vs whole card

| Surface | Draggable area | Rationale |
| --- | --- | --- |
| **S5 List view** | **Handle only** (`⠿`, 16px, appears on row hover/focus at `opacity 0→1` over `duration-fast`) | Rows contain inline-editable cells, checkboxes and pickers; a whole-row drag would fight text selection and click-to-edit. |
| **S6 Board view** | **Whole card** | Cards have no inline editing; the whole card is the affordance, matching every Kanban tool. A 4px activation distance keeps click-to-open working. |
| **S4 Sidebar** | **Whole row**, but only when `canReorderLists` and only for List nodes | Tree rows are single-purpose links. |
| **S11 Status rows** | **Handle only** | Rows are full of inputs. |

Accessibility consequence: because the board card has no visible handle, `TaskCard` itself carries `{...attributes}` `{...listeners}` and is `tabIndex={0}` with `role="button"` semantics for the drag, while a nested `<a>` provides navigation. In list view, the handle is the only element carrying `listeners` and it has `aria-label="Reorder {task.title}"`.
`guest` and offline states pass `disabled: true` to `useSortable`, which strips listeners and sets `aria-disabled`.

## 6.3 Optimistic move algorithm

```ts
// 1. On drag end, resolve the destination container + index.
type MoveIntent = {
  taskId: string;
  fromListId: string;
  fromStatusId: string;
  toStatusId: string;      // same as from for an in-column reorder
  toIndex: number;         // index within the DESTINATION column, after removal of the dragged item
};

// 2. Compute neighbours from the CLIENT-VISIBLE, server-ordered array of the destination column.
function computeNeighbours(dest: Task[], toIndex: number, draggedId: string) {
  const list = dest.filter((t) => t.id !== draggedId);          // exclude self
  const before = list[toIndex - 1] ?? null;                     // item that will sit ABOVE
  const after  = list[toIndex] ?? null;                         // item that will sit BELOW
  return { before_id: before?.id ?? null, after_id: after?.id ?? null };
}

// 3. Optimistically write the cache. Never invent a `position` string —
//    use a temporary sentinel and rely on array order until the server replies.
async function onDragEnd(intent: MoveIntent) {
  const key = ['tasks', intent.fromListId, filters, { groupBy: 'status' }] as const;
  await queryClient.cancelQueries({ queryKey: key });
  const snapshot = queryClient.getQueryData<BoardGroupedResponse>(key);

  const { before_id, after_id } = computeNeighbours(destColumn, intent.toIndex, intent.taskId);

  queryClient.setQueryData(key, (old) =>
    applyLocalMove(old, {
      ...intent,
      // cross-column drop also changes the task's status
      statusPatch: intent.toStatusId !== intent.fromStatusId
        ? { status_id: intent.toStatusId }
        : undefined,
      pendingMove: true,               // marks the card for the "syncing" affordance
    }),
  );

  try {
    // 4. Send neighbours, NOT a position. The server computes the fractional index.
    const updated: Task & { rebalanced?: boolean } = await api.patch(
      `/api/v1/tasks/${intent.taskId}/move/`,
      { before_id, after_id, status_id: intent.toStatusId },
      { headers: { 'X-Client-Id': clientId } },
    );

    // 5. Reconcile with the authoritative `position` the server returned.
    queryClient.setQueryData(key, (old) => reconcilePosition(old, updated));

    // 6. Rebalance: the server re-numbered the whole scope. Refetch it.
    if (updated.rebalanced) {
      await queryClient.invalidateQueries({ queryKey: ['tasks', intent.fromListId] });
    }
  } catch (err) {
    // 7. Roll back to the exact pre-drag snapshot.
    queryClient.setQueryData(key, snapshot);
    handleMoveError(err);              // see 6.5
  } finally {
    queryClient.setQueryData(key, (old) => clearPendingMove(old, intent.taskId));
  }
}
```

Step notes:

1. **Compute neighbours, never positions.** The Decision Sheet is explicit: the client sends `before_id`/`after_id` to `PATCH /api/v1/tasks/{id}/move/` and the **server** computes the fractional `position` via `midstring(prev, next)` over the base-62 alphabet `0-9A-Za-z`. Dropping at the very top sends `{ before_id: null, after_id: <first> }`; at the very bottom `{ before_id: <last>, after_id: null }`; into an empty column both are `null` (the server assigns `"n"`).
2. **Ordering scope is `(list_id, status_id)`.** Neighbours must always be taken from the destination status column of the same list — never across statuses, never across lists.
3. **Reconcile.** On success the server returns the full task including the new `position`. Write it into the item and re-sort the column by `position ASC, created_at ASC`. If the re-sort moves the card away from where the user dropped it, animate the correction over `duration-base` with `ease-spring` rather than snapping.
4. **Rebalance.** Per the Decision Sheet's final resolution: when the generated key would exceed 48 chars, the server re-numbers the scope with evenly spaced 2-char keys inside a transaction, emits **`task.moved` for the moved task with `rebalanced: true`**, and clients then **refetch the list**. There is no `list.rebalanced` or `list.reordered` event. The client therefore checks `rebalanced` on both the HTTP response and the WebSocket frame and invalidates `['tasks', listId]` (all filter variants) when it is true.
5. **Rollback** restores the exact pre-drag snapshot object — not a recomputed one — so unrelated concurrent cache writes made during the request are also correctly superseded by the subsequent refetch.
6. While `pendingMove` is set, the card renders at `opacity 0.7` with a 12px spinner in its top-right corner. It stays draggable; a second drag before the first resolves cancels the first request via `AbortController` and starts a fresh one.

## 6.4 Cross-column moves and auto-scroll

* **Cross-column** drop = reorder **plus** `status_id` change, sent in the **same** `PATCH /api/v1/tasks/{id}/move/` request. One request, one optimistic update, one rollback unit. Never issue a separate `PATCH tasks/{id}/` for the status.
* If the destination status is not in the list's effective status set (possible only if the set changed in another session), the server returns `400 invalid_status_for_list`; the client rolls back, refetches `['list', listId, 'status-set']`, and toasts.
* Column headers show a live count that increments/decrements optimistically.
* Dropping into a **collapsed** column expands it after the drop settles.
* **Auto-scroll**: dnd-kit's built-in `autoScroll` with `{ threshold: { x: 0.15, y: 0.2 }, acceleration: 12, interval: 5 }`.
  * Board: horizontal auto-scroll on the board scroller when the pointer is within 80px of the viewport's left/right edge, max 12px/frame; vertical auto-scroll within the hovered column when within 60px of its top/bottom.
  * List: vertical only, on the table scroll container.
  * Auto-scroll is disabled entirely under `prefers-reduced-motion: reduce` — instead the nearest edge shows a static "▲/▼ more" affordance and keyboard drag is recommended.
* The `DragOverlay` renders at `z-drag` (40) so it floats over sticky column headers but under dialogs.

## 6.5 Error handling per code

| Server response | Client behaviour |
| --- | --- |
| `200` normal | Reconcile `position`; clear `pendingMove`. |
| `200` with `rebalanced: true` | Reconcile, then `invalidateQueries(['tasks', listId])`; show a 1.2s inline "Reordering…" chip in the toolbar, no toast. |
| `400 position_conflict` | The neighbours no longer exist or are no longer adjacent. **Silent recovery**: refetch `['tasks', listId, filters, …]`, then re-apply the same intent once against the fresh data. If it fails a second time, roll back and toast "Couldn't move that task — the list changed. Try again." |
| `400 invalid_status_for_list` | Roll back, refetch the status set, danger toast. |
| `403 permission_denied` | Roll back, danger toast, disable dragging for the session on that surface. |
| `404 not_found` | Roll back, remove the task from the cache, info toast "That task was deleted." |
| `409 conflict` | Treated as `position_conflict`. |
| `429 throttled` | Roll back, toast with the retry-after seconds; drag is suppressed for that period. |
| `5xx server_error` | Roll back, danger toast with `request_id` and a `[ Retry ]` action that replays the intent. |
| Network failure | Roll back, toast "You're offline — that move wasn't saved." |

## 6.6 Keyboard-accessible drag

Fully supported on every drag surface via `KeyboardSensor`.

| Key | Behaviour |
| --- | --- |
| `Tab` | Move focus to the drag handle (list/status) or the card (board). |
| `Space` / `Enter` | **Lift.** The item enters drag mode: `DragOverlay` renders, the source slot becomes a dashed placeholder, and the live region announces "Picked up Fix login redirect loop. It is in position 2 of 8 in To do. Use arrow keys to move, space to drop, escape to cancel." |
| `↑` / `↓` | Move one slot within the current column. Announce "Moved to position 3 of 8 in To do." |
| `←` / `→` | **Board only.** Move to the adjacent column at the same index (clamped). Announce "Moved to In progress, position 1 of 5." |
| `Space` / `Enter` | **Drop.** Commits via the same `onDragEnd` path. Announce "Dropped Fix login redirect loop in In progress, position 1 of 5." |
| `Escape` | **Cancel.** Item returns to origin, nothing is sent. Announce "Movement cancelled. Fix login redirect loop returned to position 2 of 8 in To do." |
| `Page Up` / `Page Down` | Move 5 slots at a time. |
| `Home` / `End` | Move to the first/last slot in the current column. |

Announcements go through dnd-kit's `announcements` prop into an `aria-live="assertive"` region owned by `DndContext` (`screenReaderInstructions` set to the sentence above). While a keyboard drag is active, global single-letter shortcuts (`j`, `k`, `t`, `e`) are suppressed.

## 6.7 List reordering in the sidebar (S4)

Same algorithm, different endpoint and scope:

* Endpoint: `PATCH /api/v1/lists/{id}/move/`, body `{ before_id, after_id, folder_id }`.
* Ordering scope is `(space_id, folder_id)` — a list may be dragged into another folder of the **same space**, which changes `folder_id`.
* Optimistic target: `['workspace', workspaceId, 'tree']`.
* Cross-space drags are **not** permitted in MVP; such a drop is rejected client-side with a shake animation (skipped under reduced motion) and a toast "Move lists within a space only."
* Folders and Spaces are not draggable in MVP even though they carry `position` — the endpoints exist but the UI does not expose them.

## 6.8 Concurrent `task.moved` arriving mid-drag

The hard case: another user moves a task while this user is dragging.

```ts
// useRealtimeStore keeps a dragging flag and a buffer.
type DragGate = {
  isDragging: boolean;
  draggedTaskId: string | null;
  buffered: RealtimeEvent[];   // capped at 200; overflow sets needsFullRefetch
  needsFullRefetch: boolean;
};
```

Rules, in priority order:

1. **Echo of my own move** (`actor.client_id === X-Client-Id`): dropped immediately, at any time, dragging or not. The optimistic path already owns this change.
2. **Event about the task I am currently dragging** (`data.id === draggedTaskId`): **discard** the incoming position for the duration of the drag. My drop is about to be sent and will be the last writer. After my `PATCH` resolves, the server's returned `position` is authoritative and reconciles everything. If my `PATCH` fails, the rollback is followed by a forced `invalidateQueries(['tasks', listId])`, which pulls in the other user's move.
3. **Event about a different task in a column I am dragging over**: **buffer**, do not apply. Applying it would re-order the array under the pointer, causing dnd-kit's measured rects to go stale and the drop indicator to jump. Buffered events are applied in arrival order in `onDragEnd`'s `finally`, *after* the optimistic write and *before* reconciliation.
4. **Event about a task in a column I am not interacting with**: apply immediately — it cannot affect collision detection for the active drag. (Board columns are independent scroll containers; a change in a far column does not move the hovered column's rects.) If the change alters column heights in a way that shifts layout (only possible for the same column), fall back to rule 3.
5. **`task.deleted` for the task I am dragging**: cancel the drag immediately (`dndContextRef.current?.cancelDrop()`), roll back the placeholder, and toast "Ada deleted this task while you were moving it."
6. **`task.moved` with `rebalanced: true` arriving mid-drag**: set `needsFullRefetch = true`, keep dragging, let the drop go through normally, then discard the local reconciliation and `invalidateQueries(['tasks', listId])`. The user's drop still wins because it is sent after the rebalance.
7. **Buffer overflow (>200 events) or a drag lasting >30s**: set `needsFullRefetch = true` and drop the buffer.
8. After applying the buffer, if any buffered event touched the destination column, `queryClient.invalidateQueries` is called for that list with `refetchType: 'active'` so the final order is server-truth, not a merge guess.
9. `DragOverlay` content is snapshotted at lift time and is never re-rendered from the query cache, so a concurrent `task.updated` cannot change the appearance of the card under the pointer.

<!-- SECTION-BREAK-4 -->
