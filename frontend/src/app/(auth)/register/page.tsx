import type { Metadata } from "next";
import { RegisterForm } from "@/components/auth/auth-form";

export const metadata: Metadata = { title: "Create account — Clickish" };

export default function RegisterPage() {
  return (
    <div className="w-full max-w-[400px] rounded-xl border bg-background p-10 shadow-lg">
      <h1 className="text-xl font-semibold">Create your account</h1>
      <p className="mb-6 text-sm text-muted-foreground">Free while in beta.</p>
      <RegisterForm />
    </div>
  );
}
