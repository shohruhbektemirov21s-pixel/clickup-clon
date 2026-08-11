/**
 * Env qiymatlari build vaqtida bundle'ga inline bo'ladi (`import.meta.env`),
 * shuning uchun ular Docker image'iga BUILD ARG sifatida beriladi — ishga
 * tushirishda `-e` bilan almashtirib bo'lmaydi (`frontend/Dockerfile`).
 */

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

export const WS_BASE_URL = (
  import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000"
).replace(/\/+$/, "");

export const API_MODE = import.meta.env.VITE_API_MODE ?? "real";
