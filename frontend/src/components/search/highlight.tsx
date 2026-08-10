/**
 * Qidirilgan so'zni matn ichida ajratib ko'rsatish (docs/UI_SPEC.md §S8.8):
 * `<mark>` sariq fonda, rang esa meros qilib olinadi — belgi hech qachon
 * faqat rangga tayanmasin.
 */

import * as React from "react";
import { cn } from "@/lib/utils";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Ko'p so'zli so'rov: har bir so'z alohida ajratiladi ("q3 road" → 2 ta). */
function buildPattern(query: string): RegExp | null {
  const terms = query
    .trim()
    .split(/\s+/)
    .filter((term) => term.length > 0)
    // Juda uzun so'rovda regex'ni cheklaymiz — 8 ta so'z yetarli.
    .slice(0, 8)
    .map(escapeRegExp);
  if (terms.length === 0) return null;
  return new RegExp(`(${terms.join("|")})`, "gi");
}

export function Highlight({
  text,
  query,
  className,
}: {
  text: string;
  query: string;
  className?: string;
}) {
  const pattern = React.useMemo(() => buildPattern(query), [query]);
  if (!pattern || !text) return <>{text}</>;

  // Bitta capture guruh bilan `split` natijasi: [matn, moslik, matn, moslik…]
  // — toq indekslar doim moslik bo'ladi.
  const parts = text.split(pattern);
  if (parts.length === 1) return <>{text}</>;

  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <mark
            key={i}
            className={cn(
              "rounded-[2px] bg-brand-yellow/35 text-inherit dark:bg-brand-yellow/30",
              className,
            )}
          >
            {part}
          </mark>
        ) : (
          <React.Fragment key={i}>{part}</React.Fragment>
        ),
      )}
    </>
  );
}
