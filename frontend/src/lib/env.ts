export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

export const WS_BASE_URL = (
  process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000"
).replace(/\/+$/, "");

export const API_MODE = process.env.NEXT_PUBLIC_API_MODE ?? "real";

/**
 * "Demo rejimda kirish" tugmasini ko'rsatish bayrog'i. Backend'dagi
 * `DEMO_MODE` bilan mos bo'lishi kerak — bu yerda faqat UI ko'rinishi
 * boshqariladi, haqiqiy tekshiruv `POST auth/demo/` da (o'chiq bo'lsa 404).
 * Demo parol hech qachon klientga tushmaydi.
 */
export const DEMO_MODE =
  (process.env.NEXT_PUBLIC_DEMO_MODE ?? "false").toLowerCase() === "true";
