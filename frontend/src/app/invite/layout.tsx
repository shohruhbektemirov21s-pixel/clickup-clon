/**
 * Public taklif sahifasi uchun markazlashtirilgan karta — `(auth)` guruhidagi
 * layout bilan bir xil ko'rinish, lekin bu marshrut autentifikatsiya
 * talab qilmaydi.
 */
export default function InviteLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-muted/40 p-6">
      <div className="mb-8 flex items-center gap-2.5">
        <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-lg font-bold text-primary-foreground">
          C
        </div>
        <span className="text-xl font-semibold">Clickish</span>
      </div>
      <div className="w-full max-w-[420px] rounded-xl border bg-background p-8 shadow-lg">
        {children}
      </div>
    </main>
  );
}
