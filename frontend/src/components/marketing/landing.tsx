import type * as React from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  FolderTree,
  MousePointer2,
  Paperclip,
  ShieldCheck,
  UserPlus,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { AppPreview, TerminalBlock } from "@/components/marketing/app-preview";
import {
  ActivityFeedVisual,
  OrderingVisual,
  PermissionMatrixVisual,
} from "@/components/marketing/feature-visuals";

const REPO = "https://github.com/shohruhbektemirov21s-pixel/clickup-clon";
const DOCS = `${REPO}/blob/main/docs`;

/** Qahramon fonidagi nozik grid naqshi. */
const GRID_STYLE: React.CSSProperties = {
  backgroundImage:
    "linear-gradient(to right, var(--border) 1px, transparent 1px), linear-gradient(to bottom, var(--border) 1px, transparent 1px)",
  backgroundSize: "56px 56px",
  maskImage: "radial-gradient(90% 65% at 50% 0%, #000 15%, transparent 78%)",
  WebkitMaskImage: "radial-gradient(90% 65% at 50% 0%, #000 15%, transparent 78%)",
};

/** Binafsha nur — `--primary` (#7B68EE) bilan bir xil ohangda. */
const GLOW_STYLE: React.CSSProperties = {
  background:
    "radial-gradient(closest-side, rgba(123,104,238,0.38), rgba(123,104,238,0.10) 55%, rgba(123,104,238,0) 78%)",
};

/** Dark rejimda qahramon fonini chuqurlashtiruvchi qatlam. */
const DEEP_STYLE: React.CSSProperties = {
  background: "linear-gradient(180deg, #0a0a0f 0%, rgba(10,10,15,0.55) 45%, rgba(10,10,15,0) 100%)",
};

/** Public marketing landing shown at `/` to signed-out visitors. */
export function Landing() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteHeader />

      <main className="flex-1">
        <Hero />
        <Stats />
        <Features />
        <WhySection />
        <QuickStart />
        <FinalCta />
      </main>

      <SiteFooter />
    </div>
  );
}

/* ------------------------------------------------------------------ header */

function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`flex items-center gap-2 ${className}`}>
      <span
        aria-hidden
        className="flex size-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground"
      >
        C
      </span>
      <span className="text-base font-semibold tracking-tight">Clickish</span>
    </span>
  );
}

function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between gap-4 px-5 sm:px-6">
        <Logo />
        <nav aria-label="Asosiy" className="hidden items-center gap-1 md:flex">
          <HeaderLink href="#imkoniyatlar">Imkoniyatlar</HeaderLink>
          <HeaderLink href="#nima-uchun">Nima uchun</HeaderLink>
          <HeaderLink href="#ishga-tushirish">Ishga tushirish</HeaderLink>
          <HeaderLink href={`${DOCS}/API_CONTRACT.md`} external>
            Hujjatlar
          </HeaderLink>
        </nav>
        <div className="flex items-center gap-2">
          <Button variant="ghost" render={<Link href="/login" />}>
            Kirish
          </Button>
          <Button render={<Link href="/register" />}>Ro&apos;yxatdan o&apos;tish</Button>
        </div>
      </div>
    </header>
  );
}

function HeaderLink({
  href,
  children,
  external = false,
}: {
  href: string;
  children: React.ReactNode;
  external?: boolean;
}) {
  const className =
    "rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground";
  if (external) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={className}>
        {children}
      </a>
    );
  }
  return (
    <a href={href} className={className}>
      {children}
    </a>
  );
}

/* -------------------------------------------------------------------- hero */

function Hero() {
  return (
    <section className="relative isolate overflow-hidden border-b">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 hidden dark:block" style={DEEP_STYLE} />
        <div className="absolute inset-0 opacity-70 dark:opacity-40" style={GRID_STYLE} />
        <div
          className="absolute top-[-22rem] left-1/2 size-[46rem] -translate-x-1/2 rounded-full opacity-70 blur-[2px] dark:opacity-100"
          style={GLOW_STYLE}
        />
      </div>

      <div className="mx-auto w-full max-w-6xl px-5 pt-16 pb-12 sm:px-6 sm:pt-24 sm:pb-16">
        <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
          <span className="inline-flex items-center gap-2 rounded-full border bg-background/70 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
            <span aria-hidden className="size-1.5 rounded-full bg-primary" />
            Ochiq kod · Django + Next.js · to&apos;liq o&apos;zbek tilida
          </span>

          <h1 className="mt-6 text-4xl leading-[1.05] font-bold tracking-tight text-balance sm:text-6xl">
            Jamoangizning butun ishi —{" "}
            <span className="text-primary">bitta real vaqtli</span> ish maydonida.
          </h1>

          <p className="mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            Clickish — bo&apos;lim, jild, ro&apos;yxat va vazifalar iyerarxiyasi, sudrab
            tartiblash, 48 ta ruxsat kodi bilan granular rollar va WebSocket orqali bir zumda
            yangilanadigan hamkorlik.
          </p>

          <div className="mt-8 flex w-full flex-col items-stretch gap-3 sm:w-auto sm:flex-row sm:items-center">
            <Button size="lg" className="h-11 px-6 text-[0.95rem]" render={<Link href="/register" />}>
              Ro&apos;yxatdan o&apos;tish
              <ArrowRight data-icon="inline-end" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="h-11 px-6 text-[0.95rem]"
              render={<Link href="/login" />}
            >
              Demo rejimda ko&apos;rish
            </Button>
          </div>

          <p className="mt-3 text-xs text-muted-foreground">
            Demo hisobga kirish uchun parol shart emas — kirish sahifasidagi «Demo rejimda kirish»
            tugmasi.
          </p>
        </div>

        <div className="mx-auto mt-12 max-w-5xl sm:mt-16">
          <AppPreview />
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------- stats */

const STATS = [
  { value: "48", label: "ruxsat kodi" },
  { value: "4", label: "rol darajasi" },
  { value: "12", label: "specced ekran" },
  { value: "0", label: "sahifa yangilash" },
];

function Stats() {
  return (
    <section aria-label="Raqamlarda" className="border-b bg-muted/30">
      <dl className="mx-auto grid w-full max-w-6xl grid-cols-2 gap-px px-5 py-10 sm:px-6 md:grid-cols-4">
        {STATS.map((stat) => (
          <div key={stat.label} className="flex flex-col items-center gap-1 px-2 text-center">
            <dt className="sr-only">{stat.label}</dt>
            <dd className="text-3xl font-bold tracking-tight text-primary sm:text-4xl">
              {stat.value}
            </dd>
            <p className="text-xs text-muted-foreground sm:text-sm">{stat.label}</p>
          </div>
        ))}
      </dl>
    </section>
  );
}

/* ---------------------------------------------------------------- features */

const FEATURES = [
  {
    icon: FolderTree,
    title: "Ish maydonlari iyerarxiyasi",
    text: "Bo'lim → Jild → Ro'yxat → Vazifa. Yopiq bo'limlar faqat qo'shilgan a'zolarga ko'rinadi.",
  },
  {
    icon: MousePointer2,
    title: "Sudrab tartiblash",
    text: "Kasr pozitsiyalar bilan — vazifani ko'chirganda butun jadval qayta raqamlanmaydi.",
  },
  {
    icon: Zap,
    title: "Real vaqtli hamkorlik",
    text: "Vazifa, izoh va presence hodisalari WebSocket orqali keladi; sahifani yangilash shart emas.",
  },
  {
    icon: ShieldCheck,
    title: "48 ta ruxsat kodi",
    text: "Har bir ish maydonida rol × huquq matritsasi sozlanadi; tekshiruv har doim serverda.",
  },
  {
    icon: UserPlus,
    title: "Takliflar bilan jamoa",
    text: "Token bilan taklif yuboring — ro'yxatdan o'tgan zahoti a'zolik avtomatik beriladi.",
  },
  {
    icon: Paperclip,
    title: "Fayllar va faoliyat",
    text: "Vazifalarga hujjat va rasm biriktiring, a'zo profillari va faoliyat tasmasini kuzating.",
  },
];

function Features() {
  return (
    <section id="imkoniyatlar" className="scroll-mt-16 border-b">
      <div className="mx-auto w-full max-w-6xl px-5 py-16 sm:px-6 sm:py-20">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-bold tracking-tight sm:text-4xl">
            Ishni boshqarish uchun kerak bo&apos;lgan hamma narsa
          </h2>
          <p className="mt-3 text-base text-muted-foreground">
            Har bir imkoniyat ilovada allaqachon ishlaydi — ro&apos;yxat va doska
            ko&apos;rinishidan tortib huquqlar matritsasigacha.
          </p>
        </div>

        <ul className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <li
              key={title}
              className="group rounded-xl border bg-card p-5 transition-colors hover:border-primary/40 hover:bg-primary/[0.03]"
            >
              <span
                aria-hidden
                className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary"
              >
                <Icon className="size-4.5" />
              </span>
              <h3 className="mt-4 text-sm font-semibold tracking-tight">{title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{text}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------- nima uchun */

const WHY = [
  {
    eyebrow: "Real vaqt",
    title: "Har bir o'zgarish — bir zumda, hammada",
    text: "Vazifa ko'chdimi, izoh qo'shildimi, kimdir ro'yxatga kirdimi — hodisa servis qatlamidan chiqadi va WebSocket orqali barcha ochiq oynalarga yetadi. O'z aks-sadolaringiz bostiriladi, shuning uchun kursor sakramaydi.",
    bullets: ["Presence — kim onlayn", "Avtomatik qayta ulanish", "Izoh va fayl hodisalari"],
    visual: <ActivityFeedVisual />,
  },
  {
    eyebrow: "Huquqlar",
    title: "Rollar tugmani yashirish bilan cheklanmaydi",
    text: "48 ta ruxsat kodi rol × huquq matritsasida sozlanadi. Frontend faqat tugmani ko'rsatadi yoki yashiradi; ruxsatni har bir endpoint mustaqil tekshiradi. Ish maydonidan tashqaridagi resurs har doim 404 qaytaradi — mavjudligi oshkor bo'lmaydi.",
    bullets: ["Egasi / Admin / A'zo / Mehmon", "Egasi qatori qulflangan", "404 va 403 qoidasi"],
    visual: <PermissionMatrixVisual />,
  },
  {
    eyebrow: "Tartiblash",
    title: "Sudrash tez — chunki bitta qator yangilanadi",
    text: "Ko'chirishda mijoz qo'shni elementlarni hisoblab, serverga faqat before/after yuboradi. Server kasr pozitsiya qaytaradi va ro'yxat optimistik yangilanadi; xato bo'lsa avvalgi holatga qaytadi.",
    bullets: ["Optimistik yangilanish", "Ustunlar orasida status almashadi", "dnd-kit klaviatura bilan"],
    visual: <OrderingVisual />,
  },
];

function WhySection() {
  return (
    <section id="nima-uchun" className="scroll-mt-16 border-b bg-muted/20">
      <div className="mx-auto w-full max-w-6xl space-y-16 px-5 py-16 sm:space-y-24 sm:px-6 sm:py-20">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-bold tracking-tight sm:text-4xl">Nima uchun Clickish</h2>
          <p className="mt-3 text-base text-muted-foreground">
            Uchta qaror butun mahsulotni belgilaydi: real vaqt, jiddiy huquqlar va arzon
            tartiblash.
          </p>
        </div>

        {WHY.map((item, index) => (
          <div
            key={item.title}
            className="grid items-center gap-8 lg:grid-cols-2 lg:gap-14"
          >
            <div className={`min-w-0 ${index % 2 === 1 ? "lg:order-2" : ""}`}>
              <p className="text-xs font-semibold tracking-widest text-primary uppercase">
                {item.eyebrow}
              </p>
              <h3 className="mt-3 text-xl font-bold tracking-tight sm:text-2xl">{item.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
                {item.text}
              </p>
              <ul className="mt-5 space-y-2">
                {item.bullets.map((bullet) => (
                  <li key={bullet} className="flex items-center gap-2 text-sm">
                    <Activity aria-hidden className="size-3.5 shrink-0 text-primary" />
                    <span className="text-muted-foreground">{bullet}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className={`min-w-0 ${index % 2 === 1 ? "lg:order-1" : ""}`}>{item.visual}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* --------------------------------------------------------- ishga tushirish */

function QuickStart() {
  return (
    <section id="ishga-tushirish" className="scroll-mt-16 border-b">
      <div className="mx-auto grid w-full max-w-6xl items-center gap-8 px-5 py-16 sm:px-6 sm:py-20 lg:grid-cols-2 lg:gap-14">
        <div className="min-w-0">
          <p className="text-xs font-semibold tracking-widest text-primary uppercase">
            Ishga tushirish
          </p>
          <h2 className="mt-3 text-2xl font-bold tracking-tight sm:text-4xl">
            Bir buyruq — to&apos;liq stek
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
            Docker Compose PostgreSQL 16, Redis 7, Django backend va Next.js frontendni birga
            ko&apos;taradi. Backend migratsiyani o&apos;zi bajaradi,{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">seed_demo</code>{" "}
            esa demo ish maydoni va besh xil roldagi foydalanuvchini yaratadi.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button variant="outline" render={<a href={`${DOCS}/DOCKER.md`} target="_blank" rel="noreferrer" />}>
              Docker qo&apos;llanmasi
            </Button>
            <Button variant="ghost" render={<Link href="/login" />}>
              Demo rejimda ko&apos;rish
              <ArrowRight data-icon="inline-end" />
            </Button>
          </div>
        </div>
        <div className="min-w-0">
          <TerminalBlock />
        </div>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- final cta */

function FinalCta() {
  return (
    <section className="relative isolate overflow-hidden border-b">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 opacity-60 dark:opacity-30" style={GRID_STYLE} />
        <div
          className="absolute bottom-[-26rem] left-1/2 size-[40rem] -translate-x-1/2 rounded-full opacity-70 dark:opacity-100"
          style={GLOW_STYLE}
        />
      </div>
      <div className="mx-auto flex w-full max-w-3xl flex-col items-center px-5 py-20 text-center sm:px-6 sm:py-28">
        <h2 className="text-3xl font-bold tracking-tight text-balance sm:text-5xl">
          Jamoangizni bugun ko&apos;chiring
        </h2>
        <p className="mt-4 max-w-xl text-base text-muted-foreground">
          Ish maydoni yarating, bo&apos;limlarni qo&apos;shing va jamoani taklif qiling — yoki
          avval demo ma&apos;lumot bilan sinab ko&apos;ring.
        </p>
        <div className="mt-8 flex w-full flex-col items-stretch gap-3 sm:w-auto sm:flex-row">
          <Button size="lg" className="h-11 px-6 text-[0.95rem]" render={<Link href="/register" />}>
            Bepul boshlash
            <ArrowRight data-icon="inline-end" />
          </Button>
          <Button
            size="lg"
            variant="outline"
            className="h-11 px-6 text-[0.95rem]"
            render={<Link href="/login" />}
          >
            Demo rejimda ko&apos;rish
          </Button>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ footer */

const FOOTER: { title: string; links: { label: string; href: string; external?: boolean }[] }[] = [
  {
    title: "Mahsulot",
    links: [
      { label: "Imkoniyatlar", href: "#imkoniyatlar" },
      { label: "Nima uchun", href: "#nima-uchun" },
      { label: "Ishga tushirish", href: "#ishga-tushirish" },
      { label: "Demo rejimda ko'rish", href: "/login" },
    ],
  },
  {
    title: "Hujjatlar",
    links: [
      { label: "API shartnomasi", href: `${DOCS}/API_CONTRACT.md`, external: true },
      { label: "Ma'lumotlar modeli", href: `${DOCS}/DATA_MODEL.md`, external: true },
      { label: "UI spetsifikatsiyasi", href: `${DOCS}/UI_SPEC.md`, external: true },
      { label: "Huquqlar dizayni", href: `${DOCS}/DESIGN_PERMISSIONS.md`, external: true },
    ],
  },
  {
    title: "Loyiha",
    links: [
      { label: "Manba kodi", href: REPO, external: true },
      { label: "Mahsulot talablari", href: `${DOCS}/PRD.md`, external: true },
      { label: "Sprint rejasi", href: `${DOCS}/SPRINT_PLAN.md`, external: true },
      { label: "Docker qo'llanmasi", href: `${DOCS}/DOCKER.md`, external: true },
    ],
  },
];

function SiteFooter() {
  return (
    <footer className="bg-muted/20">
      <div className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-6 sm:py-16">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-1">
            <Logo />
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-muted-foreground">
              Jamoaviy vazifa boshqaruvi: ish maydonlari, real vaqtli hamkorlik va granular
              huquqlar. Interfeys to&apos;liq o&apos;zbek tilida.
            </p>
          </div>

          {FOOTER.map((column) => (
            <nav key={column.title} aria-label={column.title}>
              <h2 className="text-xs font-semibold tracking-wide uppercase">{column.title}</h2>
              <ul className="mt-3 space-y-2">
                {column.links.map((link) => (
                  <li key={link.label}>
                    {link.external ? (
                      <a
                        href={link.href}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                      >
                        {link.label}
                      </a>
                    ) : (
                      <Link
                        href={link.href}
                        className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                      >
                        {link.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-10 flex flex-col items-start justify-between gap-3 border-t pt-6 text-xs text-muted-foreground sm:flex-row sm:items-center">
          <p>© 2026 Clickish — ClickUp uslubidagi demo loyiha.</p>
          <p>Next.js va Django asosida qurilgan.</p>
        </div>
      </div>
    </footer>
  );
}
