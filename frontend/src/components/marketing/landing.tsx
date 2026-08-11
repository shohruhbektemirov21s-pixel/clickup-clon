import type * as React from "react";
import { Link } from "@/components/ui/link";
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
import { useQuery } from "@tanstack/react-query";
import { COMMON, LANDING } from "@/i18n/uz";
import { keys } from "@/lib/keys";
import { fetchShowcase, SHOWCASE_STALE_MS } from "@/lib/showcase";
import type { ShowcaseResponse } from "@/types/api";

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

/**
 * Public marketing landing shown at `/` to signed-out visitors.
 *
 * Ma'lumot bazadan keladi (`GET public/showcase/`) — sahifada qo'lda yozilgan
 * namunaviy qator yo'q. Backend javob bermasa `data` `null` bo'ladi va sahifa
 * bo'sh holatlar bilan baribir to'liq render bo'ladi.
 *
 * NEGA `useQuery`: Next davrida bu server komponenti edi va `await` bilan
 * o'qirdi. SPA'da server render bosqichi yo'q, so'rov brauzerdan ketadi;
 * javob kelmaguncha ekranda aynan "backend o'chiq" holatidagi ko'rinish
 * turadi, ya'ni markup va bo'sh holatlar o'zgarmadi.
 */
export function Landing() {
  const { data = null } = useQuery({
    queryKey: keys.showcase,
    queryFn: fetchShowcase,
    staleTime: SHOWCASE_STALE_MS,
  });

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteHeader />

      <main className="flex-1">
        <Hero data={data} />
        <Stats data={data} />
        <Features data={data} />
        <WhySection data={data} />
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
      <span className="text-base font-semibold tracking-tight">{LANDING.brand}</span>
    </span>
  );
}

function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between gap-4 px-5 sm:px-6">
        <Logo />
        <nav aria-label={LANDING.navMain} className="hidden items-center gap-1 md:flex">
          <HeaderLink href="#imkoniyatlar">{LANDING.navFeatures}</HeaderLink>
          <HeaderLink href="#nima-uchun">{LANDING.navWhy}</HeaderLink>
          <HeaderLink href="#ishga-tushirish">{LANDING.navQuickStart}</HeaderLink>
          <HeaderLink href={`${DOCS}/API_CONTRACT.md`} external>
            {LANDING.navDocs}
          </HeaderLink>
        </nav>
        <div className="flex items-center gap-2">
          <Button variant="ghost" render={<Link href="/login" />}>
            {COMMON.login}
          </Button>
          <Button render={<Link href="/register" />}>{COMMON.register}</Button>
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

function Hero({ data }: { data: ShowcaseResponse | null }) {
  const codes = data?.stats.permission_codes;
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
            {LANDING.heroBadge}
          </span>

          <h1 className="mt-6 text-4xl leading-[1.05] font-bold tracking-tight text-balance sm:text-6xl">
            {LANDING.heroTitleLead}{" "}
            <span className="text-primary">{LANDING.heroTitleAccent}</span>{" "}
            {LANDING.heroTitleTail}
          </h1>

          <p className="mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            {LANDING.heroSubtitle(codes)}
          </p>

          <div className="mt-8 flex w-full flex-col items-stretch gap-3 sm:w-auto sm:flex-row sm:items-center">
            <Button size="lg" className="h-11 px-6 text-[0.95rem]" render={<Link href="/register" />}>
              {COMMON.register}
              <ArrowRight data-icon="inline-end" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="h-11 px-6 text-[0.95rem]"
              render={<Link href="/login" />}
            >
              {COMMON.login}
            </Button>
          </div>

          <p className="mt-3 text-xs text-muted-foreground">{LANDING.heroFootnote}</p>
        </div>

        <div className="mx-auto mt-12 max-w-5xl sm:mt-16">
          <AppPreview data={data?.workspace ?? null} />
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------- stats */

/**
 * Raqamlar bazadan keladi — `GET public/showcase/` jamlangan COUNT'lar. Backend
 * javob bermasa butun blok tushib qoladi: noto'g'ri raqam ko'rsatgandan
 * ko'ra hech narsa ko'rsatmagan yaxshi.
 */
function Stats({ data }: { data: ShowcaseResponse | null }) {
  if (!data) return null;
  const { stats } = data;
  const items = [
    { value: stats.permission_codes, label: LANDING.statPermissionCodes },
    { value: stats.roles, label: LANDING.statRoles },
    { value: stats.tasks, label: LANDING.statTasks },
    { value: stats.members, label: LANDING.statMembers },
  ];

  return (
    <section aria-label={LANDING.statsAria} className="border-b bg-muted/30">
      <dl className="mx-auto grid w-full max-w-6xl grid-cols-2 gap-px px-5 py-10 sm:px-6 md:grid-cols-4">
        {items.map((stat) => (
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

/** `codes` — katalogdagi haqiqiy ruxsat kodlari soni (bazadan). */
const featureList = (codes: number | undefined) => [
  {
    icon: FolderTree,
    title: LANDING.featureHierarchyTitle,
    text: LANDING.featureHierarchyText,
  },
  {
    icon: MousePointer2,
    title: LANDING.featureOrderingTitle,
    text: LANDING.featureOrderingText,
  },
  {
    icon: Zap,
    title: LANDING.featureRealtimeTitle,
    text: LANDING.featureRealtimeText,
  },
  {
    icon: ShieldCheck,
    title: LANDING.featurePermissionsTitle(codes),
    text: LANDING.featurePermissionsText,
  },
  {
    icon: UserPlus,
    title: LANDING.featureInvitesTitle,
    text: LANDING.featureInvitesText,
  },
  {
    icon: Paperclip,
    title: LANDING.featureFilesTitle,
    text: LANDING.featureFilesText,
  },
];

function Features({ data }: { data: ShowcaseResponse | null }) {
  const features = featureList(data?.stats.permission_codes);
  return (
    <section id="imkoniyatlar" className="scroll-mt-16 border-b">
      <div className="mx-auto w-full max-w-6xl px-5 py-16 sm:px-6 sm:py-20">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-bold tracking-tight sm:text-4xl">
            {LANDING.featuresTitle}
          </h2>
          <p className="mt-3 text-base text-muted-foreground">{LANDING.featuresSubtitle}</p>
        </div>

        <ul className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map(({ icon: Icon, title, text }) => (
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

const whySections = (data: ShowcaseResponse | null) => [
  {
    eyebrow: LANDING.whyRealtimeEyebrow,
    title: LANDING.whyRealtimeTitle,
    text: LANDING.whyRealtimeText,
    bullets: LANDING.whyRealtimeBullets,
    visual: <ActivityFeedVisual items={data?.workspace?.activity ?? []} />,
  },
  {
    eyebrow: LANDING.whyPermissionsEyebrow,
    title: LANDING.whyPermissionsTitle,
    text: LANDING.whyPermissionsText(data?.stats.permission_codes),
    bullets: LANDING.whyPermissionsBullets,
    visual: (
      <PermissionMatrixVisual
        matrix={data?.matrix ?? null}
        totalCodes={data?.stats.permission_codes ?? null}
      />
    ),
  },
  {
    eyebrow: LANDING.whyOrderingEyebrow,
    title: LANDING.whyOrderingTitle,
    text: LANDING.whyOrderingText,
    bullets: LANDING.whyOrderingBullets,
    visual: <OrderingVisual rows={data?.workspace?.ordering ?? []} />,
  },
];

function WhySection({ data }: { data: ShowcaseResponse | null }) {
  const sections = whySections(data);
  return (
    <section id="nima-uchun" className="scroll-mt-16 border-b bg-muted/20">
      <div className="mx-auto w-full max-w-6xl space-y-16 px-5 py-16 sm:space-y-24 sm:px-6 sm:py-20">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-bold tracking-tight sm:text-4xl">{LANDING.whyTitle}</h2>
          <p className="mt-3 text-base text-muted-foreground">{LANDING.whySubtitle}</p>
        </div>

        {sections.map((item, index) => (
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
            {LANDING.quickStartEyebrow}
          </p>
          <h2 className="mt-3 text-2xl font-bold tracking-tight sm:text-4xl">
            {LANDING.quickStartTitle}
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
            {LANDING.quickStartTextLead}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">migrate</code>
            {LANDING.quickStartTextTail}
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button variant="outline" render={<a href={`${DOCS}/DOCKER.md`} target="_blank" rel="noreferrer" />}>
              {LANDING.quickStartDocs}
            </Button>
            <Button variant="ghost" render={<Link href="/register" />}>
              {COMMON.register}
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
          {LANDING.ctaTitle}
        </h2>
        <p className="mt-4 max-w-xl text-base text-muted-foreground">{LANDING.ctaSubtitle}</p>
        <div className="mt-8 flex w-full flex-col items-stretch gap-3 sm:w-auto sm:flex-row">
          <Button size="lg" className="h-11 px-6 text-[0.95rem]" render={<Link href="/register" />}>
            {LANDING.ctaPrimary}
            <ArrowRight data-icon="inline-end" />
          </Button>
          <Button
            size="lg"
            variant="outline"
            className="h-11 px-6 text-[0.95rem]"
            render={<Link href="/login" />}
          >
            {COMMON.login}
          </Button>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ footer */

const FOOTER: { title: string; links: { label: string; href: string; external?: boolean }[] }[] = [
  {
    title: LANDING.footerProduct,
    links: [
      { label: LANDING.navFeatures, href: "#imkoniyatlar" },
      { label: LANDING.navWhy, href: "#nima-uchun" },
      { label: LANDING.navQuickStart, href: "#ishga-tushirish" },
      { label: COMMON.login, href: "/login" },
    ],
  },
  {
    title: LANDING.footerDocs,
    links: [
      { label: LANDING.footerApiContract, href: `${DOCS}/API_CONTRACT.md`, external: true },
      { label: LANDING.footerDataModel, href: `${DOCS}/DATA_MODEL.md`, external: true },
      { label: LANDING.footerUiSpec, href: `${DOCS}/UI_SPEC.md`, external: true },
      { label: LANDING.footerPermissions, href: `${DOCS}/DESIGN_PERMISSIONS.md`, external: true },
    ],
  },
  {
    title: LANDING.footerProject,
    links: [
      { label: LANDING.footerSource, href: REPO, external: true },
      { label: LANDING.footerPrd, href: `${DOCS}/PRD.md`, external: true },
      { label: LANDING.footerSprintPlan, href: `${DOCS}/SPRINT_PLAN.md`, external: true },
      { label: LANDING.footerDocker, href: `${DOCS}/DOCKER.md`, external: true },
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
              {LANDING.footerTagline}
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
          <p>{LANDING.footerCopyright}</p>
          <p>{LANDING.footerBuiltWith}</p>
        </div>
      </div>
    </footer>
  );
}
