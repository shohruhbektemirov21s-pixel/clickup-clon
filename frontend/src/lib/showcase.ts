import type { ShowcaseResponse } from "@/types/api";

/**
 * Landing sahifasi uchun ma'lumotni **serverda** o'qiydi.
 *
 * Nega client emas: `/` marketing daraxti ataylab server komponenti bo'lib
 * qoladi (`app/page.tsx` dagi izohga qarang) — birinchi bo'yoq, JS'siz
 * ko'rinish va SEO shunga bog'liq. Ma'lumotni TanStack Query bilan olish
 * butun daraxtni client tomonga sudrab o'tardi.
 *
 * Server ichidan API'ga murojaat brauzerdagi manzil bilan bir xil bo'lmasligi
 * mumkin (Docker'da `backend:8000`, brauzerda `localhost:8000`), shuning uchun
 * `API_BASE_URL_INTERNAL` alohida o'qiladi va `NEXT_PUBLIC_API_BASE_URL` ga
 * qaytadi.
 */
const SERVER_API_BASE_URL = (
  process.env.API_BASE_URL_INTERNAL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

/** Landing statik bo'lib qolishi uchun javob shu qadar soniya keshlanadi. */
const REVALIDATE_SECONDS = 60;

/**
 * Backend o'chiq bo'lsa `null` qaytaradi — landing baribir to'liq
 * render bo'ladi, faqat bazadan keladigan bloklar tushib qoladi. Marketing
 * sahifasi API tushgani uchun 500 bermasligi kerak.
 */
export async function fetchShowcase(): Promise<ShowcaseResponse | null> {
  try {
    const res = await fetch(`${SERVER_API_BASE_URL}/public/showcase/`, {
      next: { revalidate: REVALIDATE_SECONDS },
    });
    if (!res.ok) return null;
    return (await res.json()) as ShowcaseResponse;
  } catch {
    return null;
  }
}
