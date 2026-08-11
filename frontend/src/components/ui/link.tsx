import * as React from "react";
import { Link as RouterLink } from "react-router";

/**
 * Ilova ichidagi havola.
 *
 * NEGA O'RAM: React Router'ning `Link` i manzilni `to` deb oladi, `next/link`
 * esa `href` deb olardi. Yigirmadan ortiq chaqiruv joyi bor va ularning
 * ko'pchiligi Base UI'ning `render={<Link href="…" />}` shakli — `href` ni
 * saqlab qolish migratsiya diffini shu joylarda nolga tushiradi va kelajakda
 * router almashsa yana bitta fayl o'zgaradi.
 *
 * Tashqi manzil (`https://`, `mailto:`) yoki sof langar (`#bo'lim`) berilsa
 * oddiy `<a>` qaytariladi: router bunday manzillarni ichki marshrut deb
 * o'ylab, sahifani almashtirmoqchi bo'lardi.
 */

type RouterLinkProps = React.ComponentPropsWithoutRef<typeof RouterLink>;

export interface LinkProps extends Omit<RouterLinkProps, "to"> {
  href: string;
}

function isExternal(href: string): boolean {
  return /^[a-z][a-z0-9+.-]*:/i.test(href) || href.startsWith("//") || href.startsWith("#");
}

export const Link = React.forwardRef<HTMLAnchorElement, LinkProps>(function Link(
  { href, ...props },
  ref,
) {
  if (isExternal(href)) {
    return <a ref={ref} href={href} {...props} />;
  }
  return <RouterLink ref={ref} to={href} {...props} />;
});
