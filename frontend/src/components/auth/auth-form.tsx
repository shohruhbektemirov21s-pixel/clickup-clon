"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DemoLoginButton } from "@/components/auth/demo-login-button";
import { PasswordInput } from "@/components/auth/password-input";
import { PasswordStrength, scorePassword } from "@/components/auth/password-strength";
import { isApiError } from "@/lib/api";
import { login, register } from "@/lib/auth";
import { keys } from "@/lib/keys";
import { PROFESSION_OPTIONS } from "@/lib/roles";
import { cn } from "@/lib/utils";
import type { InvitableRole, Paginated, Profession, Workspace } from "@/types/api";
import { api } from "@/lib/api";

interface FieldErrors {
  [field: string]: string | undefined;
}

/** `/invite/[token]` sahifasi ro'yxatdan o'tish formasiga uzatadigan kontekst. */
export interface InviteContext {
  token: string;
  /** Taklif qilingan email — forma uni o'zgartira olmaydi. */
  email: string;
  workspaceName: string;
  /** FAQAT KO'RSATISH UCHUN. Rol serverda `Invitation.role` dan olinadi. */
  role: InvitableRole;
  /**
   * "Hisobingiz bormi? Kirish" havolasi. §F-6 MUST-5 sababli bu yerga
   * TOKEN QO'YILMAYDI — `InviteView` uni sessionStorage'da qoldirib, manzilga
   * faqat ma'nosiz nonce yozadi.
   */
  loginHref: string;
}

function extractErrors(err: unknown, fields: string[]): { banner?: string; fields: FieldErrors } {
  if (!isApiError(err)) {
    return {
      banner: "Nimadir xato ketdi. Internet aloqasini tekshirib, qayta urinib ko'ring.",
      fields: {},
    };
  }
  const fieldErrors: FieldErrors = {};
  for (const f of fields) {
    const msg = err.fieldError(f);
    if (msg) fieldErrors[f] = msg;
  }
  if (Object.keys(fieldErrors).length > 0) return { fields: fieldErrors };
  if (err.code === "authentication_failed") {
    return { banner: "Bunday email va parolga ega faol hisob topilmadi.", fields: {} };
  }
  if (err.code === "throttled") {
    return { banner: "Urinishlar juda ko'p. Biroz kutib, qayta urinib ko'ring.", fields: {} };
  }
  if (err.status === 404) {
    return { banner: "Taklif muddati tugagan yoki bekor qilingan.", fields: {} };
  }
  if (err.status === 409) {
    return { banner: "Bu taklif allaqachon ishlatilgan.", fields: {} };
  }
  return { banner: err.message, fields: {} };
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="text-xs text-danger">{message}</p>;
}

/**
 * Read `?next=` at submit time (not via useSearchParams) so the form fully
 * server-renders instead of bailing out to a Suspense fallback.
 */
function getSafeNext(): string | null {
  if (typeof window === "undefined") return null;
  const next = new URLSearchParams(window.location.search).get("next");
  // Only same-origin paths.
  if (next && next.startsWith("/") && !next.startsWith("//")) return next;
  return null;
}

async function firstWorkspaceRoute(): Promise<string> {
  try {
    const ws = await api.get<Paginated<Workspace>>("workspaces/");
    if (ws.results.length > 0) return `/w/${ws.results[0].id}`;
  } catch {
    // fall through
  }
  return "/";
}

export function LoginForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [pending, setPending] = React.useState(false);
  const [banner, setBanner] = React.useState<string | undefined>();
  const [errors, setErrors] = React.useState<FieldErrors>({});

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPending(true);
    setBanner(undefined);
    setErrors({});
    try {
      const res = await login({ email: email.trim().toLowerCase(), password });
      queryClient.setQueryData(keys.me, res.user);
      router.replace(getSafeNext() ?? (await firstWorkspaceRoute()));
    } catch (err) {
      const parsed = extractErrors(err, ["email", "password"]);
      setBanner(parsed.banner);
      setErrors(parsed.fields);
      setPassword("");
      setPending(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="flex w-full flex-col gap-4" noValidate>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoFocus
          autoComplete="email"
          placeholder="siz@kompaniya.uz"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          readOnly={pending}
          aria-invalid={!!errors.email}
        />
        <FieldError message={errors.email} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="password">Parol</Label>
        <PasswordInput
          id="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          readOnly={pending}
          aria-invalid={!!errors.password}
        />
        <FieldError message={errors.password} />
      </div>
      {banner ? (
        <p role="alert" className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
          {banner}
        </p>
      ) : null}
      <Button type="submit" disabled={pending} aria-busy={pending}>
        {pending ? "Kirilmoqda…" : "Kirish"}
      </Button>
      <DemoLoginButton onWorkspaceRoute={firstWorkspaceRoute} />
      <p className="text-center text-sm text-muted-foreground">
        Hisobingiz yo&apos;qmi?{" "}
        <Link href="/register" className="font-medium text-primary hover:underline">
          Ro&apos;yxatdan o&apos;ting
        </Link>
      </p>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Ro'yxatdan o'tish
// ---------------------------------------------------------------------------

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

type RegisterField =
  | "full_name"
  | "email"
  | "password"
  | "password_confirm"
  | "terms"
  | "workspace_name";

interface RegisterValues {
  fullName: string;
  email: string;
  password: string;
  passwordConfirm: string;
  terms: boolean;
}

/** Klient tomonidagi tekshiruvlar — server baribir mustaqil tekshiradi. */
function validateRegister(v: RegisterValues, inviteMode: boolean): FieldErrors {
  const errors: FieldErrors = {};
  const name = v.fullName.trim();
  if (inviteMode ? name.length < 2 : name.length > 0 && name.length < 2) {
    errors.full_name = "To'liq ismni kiriting (kamida 2 ta belgi).";
  }
  if (!EMAIL_RE.test(v.email.trim())) {
    errors.email = "To'g'ri email manzilini kiriting.";
  }
  if (v.password.length < 8) {
    errors.password = "Parol kamida 8 ta belgidan iborat bo'lsin.";
  } else if (/^\d+$/.test(v.password)) {
    errors.password = "Parol faqat raqamlardan iborat bo'lmasin.";
  }
  if (!v.passwordConfirm) {
    errors.password_confirm = "Parolni tasdiqlang.";
  } else if (v.password !== v.passwordConfirm) {
    errors.password_confirm = "Parollar mos kelmadi.";
  }
  if (!v.terms) {
    errors.terms = "Davom etish uchun shartlarga rozilik bildiring.";
  }
  return errors;
}

export function RegisterForm({ invite }: { invite?: InviteContext } = {}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const inviteMode = !!invite;

  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState(invite?.email ?? "");
  const [password, setPassword] = React.useState("");
  const [passwordConfirm, setPasswordConfirm] = React.useState("");
  const [profession, setProfession] = React.useState<Profession>("");
  const [workspaceName, setWorkspaceName] = React.useState("");
  const [terms, setTerms] = React.useState(false);

  const [pending, setPending] = React.useState(false);
  const [banner, setBanner] = React.useState<string | undefined>();
  const [serverErrors, setServerErrors] = React.useState<FieldErrors>({});
  const [touched, setTouched] = React.useState<Partial<Record<RegisterField, boolean>>>({});

  const values: RegisterValues = { fullName, email, password, passwordConfirm, terms };
  const clientErrors = validateRegister(values, inviteMode);

  /** Maydon xatosi: server xatosi ustun, keyin "touched" bo'lgan klient xatosi. */
  const errorFor = (field: RegisterField): string | undefined =>
    serverErrors[field] ?? (touched[field] ? clientErrors[field] : undefined);

  const markTouched = (field: RegisterField) =>
    setTouched((t) => (t[field] ? t : { ...t, [field]: true }));

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerErrors({});
    setBanner(undefined);
    // Parollar mos kelmasa (yoki boshqa klient xatosi) — so'rov YUBORILMAYDI.
    if (Object.keys(clientErrors).length > 0) {
      setTouched({
        full_name: true,
        email: true,
        password: true,
        password_confirm: true,
        terms: true,
        workspace_name: true,
      });
      return;
    }
    setPending(true);
    try {
      const res = await register({
        email: email.trim().toLowerCase(),
        password,
        full_name: fullName.trim() || undefined,
        profession: profession || undefined,
        ...(inviteMode
          ? { invite_token: invite.token }
          : { workspace_name: workspaceName.trim() || undefined }),
      });
      queryClient.setQueryData(keys.me, res.user);
      router.replace(res.workspace_id ? `/w/${res.workspace_id}` : await firstWorkspaceRoute());
    } catch (err) {
      const parsed = extractErrors(err, [
        "email",
        "password",
        "full_name",
        "workspace_name",
        "profession",
        "invite_token",
      ]);
      setBanner(parsed.banner);
      setServerErrors(parsed.fields);
      setPending(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="flex w-full flex-col gap-4" noValidate>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="full_name">
          To&apos;liq ism
          {inviteMode ? null : <span className="text-muted-foreground"> (ixtiyoriy)</span>}
        </Label>
        <Input
          id="full_name"
          autoFocus
          autoComplete="name"
          placeholder="Alisher Navoiy"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          onBlur={() => markTouched("full_name")}
          readOnly={pending}
          required={inviteMode}
          aria-invalid={!!errorFor("full_name")}
        />
        <FieldError message={errorFor("full_name")} />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="reg_email">Email</Label>
        <Input
          id="reg_email"
          type="email"
          autoComplete="email"
          placeholder="siz@kompaniya.uz"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={() => markTouched("email")}
          required
          // Taklif emaili qat'iy: server ham CI tenglikni tekshiradi.
          readOnly={pending || inviteMode}
          aria-invalid={!!errorFor("email")}
          className={inviteMode ? "bg-muted/60" : undefined}
        />
        {inviteMode ? (
          <p className="text-xs text-muted-foreground">
            Taklif shu manzilga yuborilgan, uni o&apos;zgartirib bo&apos;lmaydi.
          </p>
        ) : null}
        <FieldError message={errorFor("email")} />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="reg_password">Parol</Label>
        <PasswordInput
          id="reg_password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onBlur={() => markTouched("password")}
          required
          minLength={8}
          readOnly={pending}
          aria-invalid={!!errorFor("password")}
        />
        <PasswordStrength password={password} />
        {!password || scorePassword(password) >= 2 ? (
          <p className="text-xs text-muted-foreground">
            Kamida 8 ta belgi, faqat raqamlardan iborat bo&apos;lmasin.
          </p>
        ) : null}
        <FieldError message={errorFor("password")} />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="reg_password_confirm">Parolni tasdiqlash</Label>
        <PasswordInput
          id="reg_password_confirm"
          autoComplete="new-password"
          value={passwordConfirm}
          onChange={(e) => setPasswordConfirm(e.target.value)}
          onBlur={() => markTouched("password_confirm")}
          required
          readOnly={pending}
          aria-invalid={!!errorFor("password_confirm")}
        />
        <FieldError message={errorFor("password_confirm")} />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="reg_profession">
          Kasb roli <span className="text-muted-foreground">(ixtiyoriy)</span>
        </Label>
        <select
          id="reg_profession"
          value={profession}
          onChange={(e) => setProfession(e.target.value as Profession)}
          disabled={pending}
          aria-invalid={!!serverErrors.profession}
          className={cn(
            "h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm",
            "outline-none transition-colors focus-visible:border-ring focus-visible:ring-3",
            "focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50",
            "dark:bg-input/30",
          )}
        >
          <option value="">Tanlanmagan</option>
          {PROFESSION_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <p className="text-xs text-muted-foreground">
          Bu ish maydonidagi ruxsatlarga ta&apos;sir qilmaydi — jamoadagi
          o&apos;rningizni ko&apos;rsatadi.
        </p>
        <FieldError message={serverErrors.profession} />
      </div>

      {inviteMode ? null : (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="workspace_name">
            Ish maydoni nomi <span className="text-muted-foreground">(ixtiyoriy)</span>
          </Label>
          <Input
            id="workspace_name"
            placeholder="Acme MChJ"
            value={workspaceName}
            onChange={(e) => setWorkspaceName(e.target.value)}
            readOnly={pending}
            aria-invalid={!!serverErrors.workspace_name}
          />
          <FieldError message={serverErrors.workspace_name} />
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <label className="flex items-start gap-2 text-sm">
          <Checkbox
            id="reg_terms"
            checked={terms}
            onCheckedChange={(next) => {
              setTerms(next === true);
              markTouched("terms");
            }}
            disabled={pending}
            aria-invalid={!!errorFor("terms")}
            className="mt-0.5"
          />
          <span className="text-muted-foreground">
            <span className="text-foreground">Foydalanish shartlari</span> va{" "}
            <span className="text-foreground">Maxfiylik siyosati</span>ga roziman
          </span>
        </label>
        <FieldError message={errorFor("terms")} />
      </div>

      {banner ? (
        <p role="alert" className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
          {banner}
        </p>
      ) : null}

      <Button type="submit" disabled={pending} aria-busy={pending}>
        {pending
          ? "Hisob yaratilmoqda…"
          : inviteMode
            ? "Qo'shilish"
            : "Hisob yaratish"}
      </Button>

      {inviteMode ? null : <DemoLoginButton onWorkspaceRoute={firstWorkspaceRoute} />}

      <p className="text-center text-sm text-muted-foreground">
        Hisobingiz bormi?{" "}
        <Link
          href={inviteMode ? invite.loginHref : "/login"}
          className="font-medium text-primary hover:underline"
        >
          Kirish
        </Link>
      </p>
    </form>
  );
}
