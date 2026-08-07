import type { Metadata } from "next";
import { LoginForm } from "@/components/auth/auth-form";

export const metadata: Metadata = { title: "Kirish — Clickish" };

export default function LoginPage() {
  return (
    <div className="w-full max-w-[400px] rounded-xl border bg-background p-10 shadow-lg">
      <h1 className="text-xl font-semibold">Kirish</h1>
      <p className="mb-6 text-sm text-muted-foreground">Xush kelibsiz!</p>
      <LoginForm />
    </div>
  );
}
