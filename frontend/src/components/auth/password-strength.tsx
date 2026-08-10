"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export type PasswordScore = 0 | 1 | 2 | 3;

const LEVELS: { label: string; bar: string }[] = [
  { label: "juda zaif", bar: "bg-danger" },
  { label: "zaif", bar: "bg-danger" },
  { label: "o'rtacha", bar: "bg-brand-yellow" },
  { label: "kuchli", bar: "bg-brand-green" },
];

/**
 * Parol kuchi bahosi. Bu FAQAT ko'rsatma — haqiqiy qoidalar serverda
 * (Django parol validatorlari) tekshiriladi.
 */
export function scorePassword(password: string): PasswordScore {
  if (!password) return 0;
  let points = 0;
  if (password.length >= 8) points += 1;
  if (password.length >= 12) points += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) points += 1;
  if (/\d/.test(password)) points += 1;
  if (/[^A-Za-z0-9]/.test(password)) points += 1;
  // Faqat raqamlar yoki juda qisqa — server baribir rad etadi.
  if (password.length < 8 || /^\d+$/.test(password)) return password.length < 5 ? 0 : 1;
  if (points <= 2) return 1;
  if (points === 3) return 2;
  return 3;
}

export function PasswordStrength({
  password,
  className,
}: {
  password: string;
  className?: string;
}) {
  const score = scorePassword(password);
  const level = LEVELS[score];
  if (!password) return null;

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex gap-1" aria-hidden>
        {[1, 2, 3].map((step) => (
          <span
            key={step}
            className={cn(
              "h-1 flex-1 rounded-full transition-colors",
              score >= step ? level.bar : "bg-muted",
            )}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground" aria-live="polite">
        Parol kuchi: <span className="font-medium text-foreground">{level.label}</span>
      </p>
    </div>
  );
}
