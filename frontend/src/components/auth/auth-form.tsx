"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
    return { banner: "Something went wrong. Check your connection and try again.", fields: {} };
  }
  const fieldErrors: FieldErrors = {};
  for (const f of fields) {
    const msg = err.fieldError(f);
    if (msg) fieldErrors[f] = msg;
  }
  if (Object.keys(fieldErrors).length > 0) return { fields: fieldErrors };
  if (err.code === "authentication_failed") {
    return { banner: "No active account with those credentials.", fields: {} };
  }
  if (err.code === "throttled") {
    return { banner: "Too many attempts. Please wait a moment and try again.", fields: {} };
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
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          readOnly={pending}
          aria-invalid={!!errors.email}
        />
        <FieldError message={errors.email} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
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
        {pending ? "Logging in…" : "Log in"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        No account?{" "}
        <Link href="/register" className="font-medium text-primary hover:underline">
          Sign up
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
        <Label htmlFor="full_name">Full name</Label>
        <Input
          id="full_name"
          autoFocus
          autoComplete="name"
          placeholder="Ada Lovelace"
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
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          readOnly={pending}
          aria-invalid={!!errors.email}
        />
        <FieldError message={errors.email} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="reg_password">Password</Label>
        <Input
          id="reg_password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          readOnly={pending}
          aria-invalid={!!errors.password}
        />
        <p className="text-xs text-muted-foreground">
          At least 8 characters, not entirely numeric.
        </p>
        <FieldError message={errors.password} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="workspace_name">
          Workspace name <span className="text-muted-foreground">(optional)</span>
        </Label>
        <Input
          id="workspace_name"
          placeholder="Acme Inc."
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
        {pending ? "Creating account…" : "Create account"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Log in
        </Link>
      </p>
    </form>
  );
}
