import Link from "next/link";
import { Columns3, MousePointer2, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Public marketing landing shown at `/` to signed-out visitors. */
export function Landing() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="flex h-14 items-center justify-between border-b px-6">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
            C
          </div>
          <span className="text-base font-semibold">Clickish</span>
        </div>
        <nav className="flex items-center gap-2">
          <Button variant="ghost" render={<Link href="/login" />}>
            Log in
          </Button>
          <Button render={<Link href="/register" />}>Sign up</Button>
        </nav>
      </header>

      <main className="flex flex-1 flex-col">
        <section className="mx-auto flex w-full max-w-3xl flex-col items-center gap-5 px-6 py-24 text-center">
          <h1 className="text-4xl leading-tight font-bold tracking-tight sm:text-5xl">
            One app for tasks, lists
            <br />
            and <span className="text-primary">boards</span>.
          </h1>
          <p className="max-w-xl text-base text-muted-foreground">
            Clickish keeps your team&apos;s work in one place — plan in List view,
            move work forward on the Board, and see every change the moment it
            happens.
          </p>
          <Button size="lg" className="mt-2 px-6" render={<Link href="/register" />}>
            Get started — it&apos;s free
          </Button>
        </section>

        <section className="border-t bg-muted/40">
          <div className="mx-auto grid w-full max-w-4xl gap-8 px-6 py-14 sm:grid-cols-3">
            <Feature
              icon={<Columns3 className="size-5 text-primary" />}
              title="List & Board views"
              text="Every list doubles as a Kanban board — switch with one click."
            />
            <Feature
              icon={<Zap className="size-5 text-primary" />}
              title="Real-time collaboration"
              text="Edits, comments and moves appear instantly for everyone."
            />
            <Feature
              icon={<MousePointer2 className="size-5 text-primary" />}
              title="Drag & drop"
              text="Reorder tasks and change status by dragging cards between columns."
            />
          </div>
        </section>
      </main>

      <footer className="border-t px-6 py-4 text-center text-xs text-muted-foreground">
        Clickish — a ClickUp-style demo. Built with Next.js &amp; Django.
      </footer>
    </div>
  );
}

function Feature({
  icon,
  title,
  text,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
        {icon}
      </div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="text-sm text-muted-foreground">{text}</p>
    </div>
  );
}
