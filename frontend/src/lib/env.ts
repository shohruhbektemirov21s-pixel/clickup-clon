export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

export const WS_BASE_URL = (
  process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000"
).replace(/\/+$/, "");

export const API_MODE = process.env.NEXT_PUBLIC_API_MODE ?? "real";
