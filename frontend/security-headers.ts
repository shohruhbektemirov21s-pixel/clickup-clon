/**
 * Xavfsizlik sarlavhalarining YAGONA manbai.
 *
 * Ilgari bu ro'yxat `next.config.ts` ichida yashardi va Next server har bir
 * javobga o'zi qo'shib berardi. SPA'da server yo'q, shuning uchun sarlavhalar
 * ikki joyda qayta ishlab chiqariladi:
 *
 *   • dev / preview — `vite.config.ts` dagi `server.headers` va
 *     `preview.headers` shu funksiyadan oziqlanadi;
 *   • prod — `nginx/default.conf.template` (Docker image ichida nginx).
 *
 * Ikkalasi bir xilligini `src/test/security-headers.test.ts` tekshiradi:
 * nginx shabloni faylda yozilgani uchun u bilan bu ro'yxat vaqt o'tib
 * ajralib ketishi mumkin edi, test aynan shuni ushlaydi.
 */

export interface SecurityHeader {
  key: string;
  value: string;
}

export interface SecurityHeaderOptions {
  /** Dev serverda HMR va React Refresh uchun CSP yumshatiladi. */
  isDev: boolean;
  /** `VITE_API_BASE_URL` — REST manzili. */
  apiBaseUrl?: string;
  /** `VITE_WS_BASE_URL` — WebSocket manzili. */
  wsBaseUrl?: string;
}

export const DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1";
export const DEFAULT_WS_BASE_URL = "ws://localhost:8000";

/** Reduce a URL to its scheme://host[:port] form for use as a CSP source. */
export function originOf(value: string): string | null {
  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
}

const unique = (values: (string | null)[]) =>
  Array.from(new Set(values.filter((v): v is string => Boolean(v))));

export function buildSecurityHeaders({
  isDev,
  apiBaseUrl = DEFAULT_API_BASE_URL,
  wsBaseUrl = DEFAULT_WS_BASE_URL,
}: SecurityHeaderOptions): SecurityHeader[] {
  const apiOrigin = originOf(apiBaseUrl);
  const wsOrigin = originOf(wsBaseUrl);

  // The backend serves avatars and other uploads from MEDIA_URL on the API origin.
  const imgSrc = unique(["'self'", "data:", "blob:", apiOrigin]);
  const connectSrc = unique([
    "'self'",
    apiOrigin,
    wsOrigin,
    // The Vite dev server keeps an HMR websocket open against its own origin.
    ...(isDev ? ["ws:", "http://localhost:*"] : []),
  ]);

  const csp = [
    "default-src 'self'",
    // Vite prod build'i inline <script> emitmaydi (`build.modulePreload.polyfill`
    // ham o'chirilgan), shuning uchun prodda `'unsafe-inline'` KERAK EMAS —
    // Next davridagi qattiqlashtirish shu yerda amalga oshdi. Devda esa
    // React Refresh preamble'i inline modul sifatida kiritiladi va `eval`
    // ishlatadi, shuning uchun ikkala yon berish faqat dev uchun qoladi.
    `script-src 'self'${isDev ? " 'unsafe-inline' 'unsafe-eval'" : ""}`,
    // Tailwind ships as a stylesheet, but component kutubxonalari (Base UI,
    // sonner) hamon inline `style` atributlarini qo'yadi.
    "style-src 'self' 'unsafe-inline'",
    `img-src ${imgSrc.join(" ")}`,
    "font-src 'self' data:",
    `connect-src ${connectSrc.join(" ")}`,
    "media-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    // Modern equivalent of X-Frame-Options: DENY.
    "frame-ancestors 'none'",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    ...(isDev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");

  return [
    { key: "Content-Security-Policy", value: csp },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    // Kept next to frame-ancestors for browsers that ignore CSP Level 2.
    { key: "X-Frame-Options", value: "DENY" },
    {
      key: "Permissions-Policy",
      value:
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
    },
    {
      key: "Strict-Transport-Security",
      value: "max-age=31536000; includeSubDomains; preload",
    },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  ];
}

/** Vite `server.headers` / `preview.headers` uchun ko'rinish. */
export function headersToRecord(headers: SecurityHeader[]): Record<string, string> {
  return Object.fromEntries(headers.map((h) => [h.key, h.value]));
}
