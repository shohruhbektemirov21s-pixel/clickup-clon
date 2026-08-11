/**
 * Vitest sozlamasi (`vite.config.ts` → `test.setupFiles`).
 *
 * `globals: false` bo'lgani uchun Testing Library'ning avtomatik tozalashi
 * ishlamaydi (u global `afterEach` ni qidiradi) — shuning uchun uni shu
 * yerda ochiq ulaymiz.
 */

import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
// `/vitest` kirish nuqtasi matcher'larni ham qo'shadi, tiplarni ham
// augment qiladi — `toBeInTheDocument()` shusiz `tsc` da xato berardi.
import "@testing-library/jest-dom/vitest";

afterEach(() => {
  cleanup();
});

// jsdom'da yo'q, lekin komponentlar (Base UI, dnd-kit, cmdk) kutadigan
// brauzer API'lari.
if (!("matchMedia" in window)) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

if (!("ResizeObserver" in globalThis)) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
