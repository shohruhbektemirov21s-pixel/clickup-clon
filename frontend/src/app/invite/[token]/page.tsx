import type { Metadata } from "next";
import { InviteView } from "@/components/auth/invite-view";

export const metadata: Metadata = {
  title: "Taklif — Clickish",
  // Taklif havolasi hech qachon indekslanmasin.
  robots: { index: false, follow: false },
};

export default async function InvitePage({ params }: PageProps<"/invite/[token]">) {
  const { token } = await params;
  return <InviteView token={token} />;
}
