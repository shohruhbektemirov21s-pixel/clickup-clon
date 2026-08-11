import path from "node:path";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { buildSecurityHeaders, headersToRecord } from "./security-headers.ts";

const rootDir = import.meta.dirname;

export default defineConfig(({ mode }) => {
  // `loadEnv` .env fayllarini o'qiydi; `import.meta.env` ga faqat `VITE_`
  // prefiksli qiymatlar tushadi va CSP shu ikkitasidan hisoblanadi.
  const env = loadEnv(mode, rootDir, "VITE_");
  const isDev = mode !== "production";

  const headers = headersToRecord(
    buildSecurityHeaders({
      isDev,
      apiBaseUrl: env.VITE_API_BASE_URL,
      wsBaseUrl: env.VITE_WS_BASE_URL,
    }),
  );

  return {
    // Tailwind v4 CSS-first: konfiguratsiya fayli yo'q, tokenlar
    // `src/app/globals.css` dagi `@theme` ichida (CLAUDE.md).
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { "@": path.resolve(rootDir, "src") },
    },
    server: {
      // 3000 — compose, E2E va `e2e/README.md` shu portga bog'langan.
      port: 3000,
      strictPort: true,
      headers,
    },
    preview: {
      port: 3000,
      strictPort: true,
      headers,
    },
    build: {
      outDir: "dist",
      // Vite modulepreload polifilini INLINE <script> sifatida index.html ga
      // qo'yadi. Prod CSP'da `script-src 'self'` (inline yo'q), ya'ni u
      // bloklanardi. Nishon brauzerlar modulepreload'ni o'zi qo'llab-quvvatlaydi.
      modulePreload: { polyfill: false },
    },
    test: {
      environment: "jsdom",
      // `globals: false` — `describe`/`it`/`expect` har bir testda ochiq
      // import qilinadi. Shu tufayli `tsconfig.json` dagi `types` ro'yxatiga
      // qo'shimcha global tiplar kerak emas.
      globals: false,
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      // Playwright spec'lari vitest bilan ishga tushmasin.
      exclude: ["node_modules/**", "dist/**", "e2e/**"],
      css: false,
      restoreMocks: true,
    },
  };
});
