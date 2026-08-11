import { api } from "@/lib/api";
import { getRefreshToken, useAuthStore } from "@/stores/auth-store";
import type { AuthResponse, LoginRequest, RegisterRequest } from "@/types/api";

/**
 * "Foydalanuvchi o'zi chiqdi" bayrog'i.
 *
 * `AuthGate` sessiya yo'qolganini ko'rganda `/login?next=<joriy yo'l>` ga
 * yo'naltiradi — bu token eskirganda to'g'ri, chunki odam o'sha sahifaga
 * qaytishni kutadi. Lekin ataylab chiqishda `?next=` **oldingi** odamning
 * ish maydoni URL'ini olib qoladi va shu brauzerda keyin kirgan odam o'zi
 * a'zo bo'lmagan sahifaga tushib, 403/404 ekranini ko'radi.
 *
 * Shu sababli `useLogout` chiqishdan oldin bu bayroqni qo'yadi; gate uni
 * o'qib `?next=` ni tushirib qoldirishi kerak. Bayroq keyingi muvaffaqiyatli
 * kirishda o'zi tushadi.
 */
let intentionalLogout = false;

/** `useLogout` chaqiradi — bundan keyingi redirect `?next=` siz bo'lsin. */
export function markIntentionalLogout(): void {
  intentionalLogout = true;
}

/** `AuthGate` o'qiydi: `true` bo'lsa `/login` ga `?next=` qo'shilmaydi. */
export function isIntentionalLogout(): boolean {
  return intentionalLogout;
}

export async function login(body: LoginRequest): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>("auth/login/", body, { auth: false });
  intentionalLogout = false;
  useAuthStore.getState().setSession(res);
  return res;
}

export async function register(body: RegisterRequest): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>("auth/register/", body, { auth: false });
  intentionalLogout = false;
  useAuthStore.getState().setSession(res);
  return res;
}

/** Blacklists this device's refresh token, then clears local session state. */
export async function logout(): Promise<void> {
  const refresh = getRefreshToken();
  try {
    if (refresh) await api.post("auth/logout/", { refresh });
  } catch {
    // Best effort — clear locally regardless.
  } finally {
    useAuthStore.getState().clearSession();
  }
}
