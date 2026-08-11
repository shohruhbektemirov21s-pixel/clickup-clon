/**
 * SPA kirish nuqtasi — Next'ning `src/app/layout.tsx` i o'rniga (ADR 0011).
 *
 * Shriftlar `next/font/google` bilan emas, `@fontsource-variable/*` orqali
 * o'zimizda: CSP'da `font-src 'self' data:` turibdi, ya'ni Google'ga
 * so'rov baribir bloklanardi. Oila nomlari `globals.css` dagi
 * `--font-sans` / `--font-geist-mono` o'zgaruvchilariga ulanadi.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import "@fontsource-variable/inter";
import "@fontsource-variable/geist-mono";
import "./app/globals.css";
import { Providers } from "./app/providers";
import { appRouter } from "./routes/app-routes";

const container = document.getElementById("root");
if (!container) throw new Error("#root topilmadi — index.html buzilgan.");

createRoot(container).render(
  <StrictMode>
    {/* `Providers` router'dan tashqarida: QueryClient va mavzu butun
        ilovaga tegishli va navigatsiya hooklariga bog'liq emas. */}
    <Providers>
      <RouterProvider router={appRouter} />
    </Providers>
  </StrictMode>,
);
