import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000";

/** Reduce a URL to its scheme://host[:port] form for use as a CSP source. */
function originOf(value: string): string | null {
  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
}

const unique = (values: (string | null)[]) =>
  Array.from(new Set(values.filter((v): v is string => Boolean(v))));

const apiOrigin = originOf(API_BASE_URL);
const wsOrigin = originOf(WS_BASE_URL);

// The backend serves avatars and other uploads from MEDIA_URL on the API origin.
const imgSrc = unique(["'self'", "data:", "blob:", apiOrigin]);
const connectSrc = unique([
  "'self'",
  apiOrigin,
  wsOrigin,
  // The Next dev server keeps an HMR websocket open against its own origin.
  ...(isDev ? ["ws:", "http://localhost:*"] : []),
]);

const csp = [
  "default-src 'self'",
  // Next injects its bootstrap and flight payloads as inline <script>. Without
  // a nonce-emitting middleware those need 'unsafe-inline'; 'unsafe-eval' is
  // dev-only (React Refresh). Drop both once a nonce middleware exists.
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  // Tailwind ships as a stylesheet, but Next still emits inline style tags.
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

const securityHeaders = [
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

const nextConfig: NextConfig = {
  // Emits .next/standalone with a self-contained server.js — required by
  // frontend/Dockerfile (see docs/DOCKER.md). Harmless for `next dev`.
  output: "standalone",
  // Do not advertise the framework to scanners.
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
