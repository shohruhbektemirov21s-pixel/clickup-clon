import * as React from "react";

/**
 * Sahifa sarlavhasi (va kerak bo'lsa `robots` meta tegi).
 *
 * Next'da bu `export const metadata: Metadata` edi va serverda `<head>` ga
 * yozilardi. SPA'da `<head>` bitta — `index.html` — shuning uchun sarlavhani
 * marshrut komponenti mount bo'lganda qo'yamiz va unmount'da standart
 * qiymatga qaytaramiz. Sarlavha matnlari Next davridagidek qoldi.
 */
export const DEFAULT_TITLE = "UzWork";

const ROBOTS_CONTENT = "noindex, nofollow";

export function usePageTitle(title: string, options?: { noIndex?: boolean }) {
  const noIndex = options?.noIndex ?? false;

  React.useEffect(() => {
    document.title = title;
    return () => {
      document.title = DEFAULT_TITLE;
    };
  }, [title]);

  React.useEffect(() => {
    // Taklif havolasi hech qachon indekslanmasin (§F-6). Meta teg faqat shu
    // marshrut ekranda turganda mavjud bo'ladi — landing indekslanadigan
    // bo'lib qolishi kerak.
    if (!noIndex) return;
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = ROBOTS_CONTENT;
    document.head.appendChild(meta);
    return () => {
      meta.remove();
    };
  }, [noIndex]);
}
