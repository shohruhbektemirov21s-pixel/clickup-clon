/**
 * Xavfsizlik sarlavhalarining PARITETI (ADR 0011 → "Ochiq ish" 5-band).
 *
 * Sarlavhalar ilgari `next.config.ts` da bitta joyda edi. Endi ular ikkita
 * joyda ishlab chiqariladi: dev/preview uchun `security-headers.ts` →
 * `vite.config.ts`, prod uchun esa `nginx/default.conf.template`. Ikkinchisi
 * qo'lda yozilgan matn, ya'ni birinchisi o'zgarganda jimgina eskirib qolishi
 * mumkin — aynan shu testning vazifasi buni ushlash.
 *
 * Shablondagi `${API_ORIGIN}` / `${WS_ORIGIN}` o'rniniga test soxta
 * origin'lardan foydalanadi va kutilgan CSP'ni o'sha placeholder'larga
 * qaytarib qo'yadi.
 */

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { buildSecurityHeaders } from "../../security-headers";

const ROOT = path.resolve(import.meta.dirname, "../..");
const TEMPLATE = fs.readFileSync(
  path.join(ROOT, "nginx", "default.conf.template"),
  "utf8",
);

const API_ORIGIN = "https://api.example.test";
const WS_ORIGIN = "wss://ws.example.test";

const prodHeaders = buildSecurityHeaders({
  isDev: false,
  apiBaseUrl: `${API_ORIGIN}/api/v1`,
  wsBaseUrl: WS_ORIGIN,
});

/** Shablon origin'lari o'rniga nginx placeholder'lari. */
function toTemplateForm(value: string): string {
  return value
    .replaceAll(API_ORIGIN, "${API_ORIGIN}")
    .replaceAll(WS_ORIGIN, "${WS_ORIGIN}");
}

/** `add_header Name "value" always;` → Map<Name, value>. */
function parseNginxHeaders(conf: string): Map<string, string> {
  const map = new Map<string, string>();
  const re = /add_header\s+(\S+)\s+"([^"]*)"\s+always;/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(conf)) !== null) {
    map.set(match[1], match[2]);
  }
  return map;
}

describe("nginx shabloni va security-headers.ts", () => {
  const nginxHeaders = parseNginxHeaders(TEMPLATE);

  it("prod ro'yxatidagi HAR BIR sarlavha nginx'da bor va qiymati bir xil", () => {
    for (const { key, value } of prodHeaders) {
      expect(nginxHeaders.has(key), `${key} nginx shablonida yo'q`).toBe(true);
      expect(nginxHeaders.get(key), key).toBe(toTemplateForm(value));
    }
  });

  it("nginx'da ortiqcha (ro'yxatda yo'q) sarlavha qo'shilmagan", () => {
    expect([...nginxHeaders.keys()].sort()).toEqual(
      prodHeaders.map((h) => h.key).sort(),
    );
  });

  it("SPA fallback va 3000-port saqlangan", () => {
    expect(TEMPLATE).toMatch(/listen\s+3000;/);
    expect(TEMPLATE).toMatch(/try_files\s+\$uri\s+\/index\.html;/);
  });
});

describe("CSP qattiqligi", () => {
  const csp = (isDev: boolean) =>
    buildSecurityHeaders({ isDev }).find((h) => h.key === "Content-Security-Policy")!
      .value;

  it("prodda inline/eval skript RUXSAT ETILMAYDI", () => {
    const value = csp(false);
    expect(value).toContain("script-src 'self';");
    expect(value).not.toContain("'unsafe-eval'");
    expect(value.split("script-src")[1].split(";")[0]).not.toContain("'unsafe-inline'");
    expect(value).toContain("upgrade-insecure-requests");
  });

  it("devda React Refresh uchun yon beriladi", () => {
    const value = csp(true);
    expect(value).toContain("script-src 'self' 'unsafe-inline' 'unsafe-eval'");
    // HMR soketi dev serverning o'z origin'iga ulanadi.
    expect(value).toContain("ws:");
    expect(value).not.toContain("upgrade-insecure-requests");
  });

  it("frame-ancestors va object-src yopiq qoladi", () => {
    const value = csp(false);
    expect(value).toContain("frame-ancestors 'none'");
    expect(value).toContain("object-src 'none'");
    expect(value).toContain("base-uri 'self'");
    expect(value).toContain("form-action 'self'");
  });
});

describe("vite.config.ts ulanishi", () => {
  const config = fs.readFileSync(path.join(ROOT, "vite.config.ts"), "utf8");

  it("dev va preview serverlariga sarlavhalar berilgan", () => {
    expect(config).toContain("buildSecurityHeaders");
    // Ikkalasi ham `headers` oladi — biri tushib qolsa E2E prod CSP'siz
    // ishlagan bo'lardi va regressiya sezilmasdi.
    expect(config).toMatch(/server:\s*\{[^}]*headers/s);
    expect(config).toMatch(/preview:\s*\{[^}]*headers/s);
  });

  it("modulepreload polifili o'chirilgan (inline skript emitilmasin)", () => {
    expect(config).toMatch(/modulePreload:\s*\{\s*polyfill:\s*false\s*\}/);
  });
});
