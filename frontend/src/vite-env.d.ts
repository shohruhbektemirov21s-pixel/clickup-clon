/// <reference types="vite/client" />

/**
 * Bundle'ga tushadigan env o'zgaruvchilari.
 *
 * Vite faqat `VITE_` prefiksli qiymatlarni klientga uzatadi (Next'dagi
 * `NEXT_PUBLIC_` ning ekvivalenti). `vite/client` ularni `any` deb beradi,
 * shuning uchun bu yerda aniq tiplar e'lon qilinadi — `.env.example` bilan
 * bir xil ro'yxat.
 */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_WS_BASE_URL?: string;
  readonly VITE_API_MODE?: string;
  readonly VITE_DEMO_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
