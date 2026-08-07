import { AuthGate } from "@/components/auth/auth-gate";

export default function AppAreaLayout({ children }: { children: React.ReactNode }) {
  return <AuthGate>{children}</AuthGate>;
}
