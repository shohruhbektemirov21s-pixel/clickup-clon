import { API_BASE_URL } from "@/lib/env";
import type { ShowcaseResponse } from "@/types/api";

/**
 * Landing sahifasi uchun ma'lumot (`GET public/showcase/`) — sahifada qo'lda
 * yozilgan namunaviy qator yo'q.
 *
 * NEGA ENDI BRAUZERDAN O'QIYDI: ilgari bu Next server komponenti ichida
 * chaqirilardi va `API_BASE_URL_INTERNAL` orqali konteyner ichidagi manzilga
 * (`backend:8000`) borardi. SPA'da server bosqichi yo'q — so'rov brauzerdan
 * ketadi, ya'ni bitta manzil (`VITE_API_BASE_URL`) yetarli va CSP'dagi
 * `connect-src` ham aynan shu origin'ga ochilgan.
 *
 * Keshni endi TanStack Query ushlaydi (`landing.tsx` dagi `staleTime`),
 * ilgarigi `next: { revalidate: 60 }` o'rniga.
 */

/** Landing ma'lumoti shu qadar millisekund yangi hisoblanadi. */
export const SHOWCASE_STALE_MS = 60_000;

/**
 * Backend o'chiq bo'lsa `null` qaytaradi — landing baribir to'liq
 * render bo'ladi, faqat bazadan keladigan bloklar tushib qoladi. Marketing
 * sahifasi API tushgani uchun buzilmasligi kerak.
 */
export async function fetchShowcase(): Promise<ShowcaseResponse | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/public/showcase/`);
    if (!res.ok) return null;
    return (await res.json()) as ShowcaseResponse;
  } catch {
    return null;
  }
}
