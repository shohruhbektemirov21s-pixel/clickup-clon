import { Button } from "@/components/ui/button";
import { Link } from "@/components/ui/link";
import { APP, NOT_FOUND } from "@/i18n/uz";
import { usePageTitle } from "@/hooks/use-page-title";

/**
 * 404 — hech bir marshrutga tushmagan manzil.
 *
 * Next'da bu `notFound()` va `not-found.tsx` edi (bu loyihada u yozilmagan,
 * ya'ni framework standarti ishlar edi). SPA'da mos keluvchi marshrut
 * bo'lmasa router shu komponentni chizadi.
 */
export function NotFound() {
  usePageTitle(APP.pageTitle(NOT_FOUND.title));
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-muted/40 p-6 text-center">
      <p className="text-5xl font-semibold text-muted-foreground">404</p>
      <h1 className="text-xl font-semibold">{NOT_FOUND.title}</h1>
      <p className="max-w-sm text-sm text-muted-foreground">{NOT_FOUND.description}</p>
      <Button render={<Link href="/" />}>{NOT_FOUND.goHome}</Button>
    </main>
  );
}
