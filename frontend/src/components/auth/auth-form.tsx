"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/auth/password-input";
import { isApiError } from "@/lib/api";
import { login, register } from "@/lib/auth";
import { keys } from "@/lib/keys";
import type { Paginated, Workspace } from "@/types/api";
import { api } from "@/lib/api";

interface FieldErrors {
  [field: string]: string | undefined;
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
      <p className="text-center text-sm text-muted-foreground">
        Hisobingiz yo&apos;qmi?{" "}
        <Link href="/register" className="font-medium text-primary hover:underline">
          Ro&apos;yxatdan o&apos;ting
        </Link>
      </p>
    </form>
  );
}

export function RegisterForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [workspaceName, setWorkspaceName] = React.useState("");
  const [pending, setPending] = React.useState(false);
  const [banner, setBanner] = React.useState<string | undefined>();
  const [errors, setErrors] = React.useState<FieldErrors>({});

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPending(true);
    setBanner(undefined);
    setErrors({});
    try {
      const res = await register({
        email: email.trim().toLowerCase(),
        password,
        full_name: fullName.trim() || undefined,
        workspace_name: workspaceName.trim() || undefined,
      });
      queryClient.setQueryData(keys.me, res.user);
      router.replace(await firstWorkspaceRoute());
    } catch (err) {
      const parsed = extractErrors(err, [
        "email",
        "password",
        "full_name",
        "workspace_name",
      ]);
      setBanner(parsed.banner);
      setErrors(parsed.fields);
      setPending(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="flex w-full flex-col gap-4" noValidate>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="full_name">To&apos;liq ism</Label>
        <Input
          id="full_name"
          autoFocus
          autoComplete="name"
          placeholder="Alisher Navoiy"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          readOnly={pending}
          aria-invalid={!!errors.full_name}
        />
        <FieldError message={errors.full_name} />
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
          required
          readOnly={pending}
          aria-invalid={!!errors.email}
        />
        <FieldError message={errors.email} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="reg_password">Parol</Label>
        <PasswordInput
          id="reg_password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          readOnly={pending}
          aria-invalid={!!errors.password}
        />
        <p className="text-xs text-muted-foreground">
          Kamida 8 ta belgi, faqat raqamlardan iborat bo&apos;lmasin.
        </p>
        <FieldError message={errors.password} />
      </div>
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
          aria-invalid={!!errors.workspace_name}
        />
        <FieldError message={errors.workspace_name} />
      </div>
      {banner ? (
        <p role="alert" className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
          {banner}
        </p>
      ) : null}
      <Button type="submit" disabled={pending} aria-busy={pending}>
        {pending ? "Hisob yaratilmoqda…" : "Hisob yaratish"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        Hisobingiz bormi?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Kirish
        </Link>
      </p>
    </form>
  );
}
