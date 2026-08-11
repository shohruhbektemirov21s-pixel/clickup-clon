import * as React from "react";
import { Link } from "@/components/ui/link";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/auth/password-input";
import { PasswordStrength, scorePassword } from "@/components/auth/password-strength";
import { AUTH, COMMON, PROFESSION_OPTIONS } from "@/i18n/uz";
import { isApiError } from "@/lib/api";
import { login, register } from "@/lib/auth";
import { keys } from "@/lib/keys";
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
    return { banner: AUTH.bannerNetwork, fields: {} };
  }
  const fieldErrors: FieldErrors = {};
  for (const f of fields) {
    const msg = err.fieldError(f);
    if (msg) fieldErrors[f] = msg;
  }
  if (Object.keys(fieldErrors).length > 0) return { fields: fieldErrors };
  if (err.code === "authentication_failed") {
    return { banner: AUTH.bannerInvalidCredentials, fields: {} };
  }
  if (err.code === "throttled") {
    return { banner: AUTH.bannerThrottled, fields: {} };
  }
  if (err.status === 404) {
    return { banner: AUTH.bannerInviteExpired, fields: {} };
  }
  if (err.status === 409) {
    return { banner: AUTH.bannerInviteUsed, fields: {} };
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
  const navigate = useNavigate();
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
      navigate(getSafeNext() ?? (await firstWorkspaceRoute()), { replace: true });
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
        <Label htmlFor="email">{COMMON.email}</Label>
        <Input
          id="email"
          type="email"
          autoFocus
          autoComplete="email"
          placeholder={AUTH.emailPlaceholder}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          readOnly={pending}
          aria-invalid={!!errors.email}
        />
        <FieldError message={errors.email} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="password">{COMMON.password}</Label>
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
        {pending ? AUTH.signingIn : COMMON.login}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        {AUTH.noAccountQuestion}{" "}
        <Link href="/register" className="font-medium text-primary hover:underline">
          {AUTH.registerCta}
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
    errors.full_name = AUTH.errFullNameTooShort;
  }
  if (!EMAIL_RE.test(v.email.trim())) {
    errors.email = AUTH.errEmailInvalid;
  }
  if (v.password.length < 8) {
    errors.password = AUTH.errPasswordTooShort;
  } else if (/^\d+$/.test(v.password)) {
    errors.password = AUTH.errPasswordAllDigits;
  }
  if (!v.passwordConfirm) {
    errors.password_confirm = AUTH.errPasswordConfirmRequired;
  } else if (v.password !== v.passwordConfirm) {
    errors.password_confirm = AUTH.errPasswordMismatch;
  }
  if (!v.terms) {
    errors.terms = AUTH.errTermsRequired;
  }
  return errors;
}

export function RegisterForm({ invite }: { invite?: InviteContext } = {}) {
  const navigate = useNavigate();
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
      navigate(res.workspace_id ? `/w/${res.workspace_id}` : await firstWorkspaceRoute(), { replace: true });
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
          {AUTH.fullNameLabel}
          {inviteMode ? null : (
            <span className="text-muted-foreground"> {COMMON.optional}</span>
          )}
        </Label>
        <Input
          id="full_name"
          autoFocus
          autoComplete="name"
          placeholder={AUTH.fullNamePlaceholder}
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
        <Label htmlFor="reg_email">{COMMON.email}</Label>
        <Input
          id="reg_email"
          type="email"
          autoComplete="email"
          placeholder={AUTH.emailPlaceholder}
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
          <p className="text-xs text-muted-foreground">{AUTH.inviteEmailLocked}</p>
        ) : null}
        <FieldError message={errorFor("email")} />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="reg_password">{COMMON.password}</Label>
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
          <p className="text-xs text-muted-foreground">{AUTH.passwordHint}</p>
        ) : null}
        <FieldError message={errorFor("password")} />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="reg_password_confirm">{AUTH.passwordConfirmLabel}</Label>
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
          {AUTH.professionLabel}{" "}
          <span className="text-muted-foreground">{COMMON.optional}</span>
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
          <option value="">{COMMON.notSelected}</option>
          {PROFESSION_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <p className="text-xs text-muted-foreground">{AUTH.professionHint}</p>
        <FieldError message={serverErrors.profession} />
      </div>

      {inviteMode ? null : (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="workspace_name">
            {AUTH.workspaceNameLabel}{" "}
            <span className="text-muted-foreground">{COMMON.optional}</span>
          </Label>
          <Input
            id="workspace_name"
            placeholder={AUTH.workspaceNamePlaceholder}
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
            <span className="text-foreground">{AUTH.termsOfService}</span>
            {AUTH.termsAnd}
            <span className="text-foreground">{AUTH.privacyPolicy}</span>
            {AUTH.termsAgreeSuffix}
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
        {pending ? AUTH.creatingAccount : inviteMode ? COMMON.join : AUTH.createAccount}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        {AUTH.haveAccountQuestion}{" "}
        <Link
          href={inviteMode ? invite.loginHref : "/login"}
          className="font-medium text-primary hover:underline"
        >
          {COMMON.login}
        </Link>
      </p>
    </form>
  );
}
