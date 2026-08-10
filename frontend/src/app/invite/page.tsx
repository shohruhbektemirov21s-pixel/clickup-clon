import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Taklif — Clickish",
  robots: { index: false, follow: false },
};

/**
 * `/invite/[token]` sahifasi yuklangach tokenni manzil qatoridan olib tashlaydi
 * (§F-6 MUST-5), shuning uchun sahifa yangilansa foydalanuvchi shu yerga
 * tushadi. Bu ekran hech qanday taklif ma'lumotini oshkor qilmaydi.
 */
export default function InviteFallbackPage() {
  return (
    <div className="flex flex-col gap-4 text-center">
      <h1 className="text-lg font-semibold">Taklif havolasi to&apos;liq emas</h1>
      <p className="text-sm text-muted-foreground">
        Xavfsizlik uchun taklif kodi manzil qatorida saqlanmaydi. Emaildagi
        havolani qaytadan oching yoki hisobingizga kiring.
      </p>
      <div className="flex justify-center gap-2">
        <Button variant="outline" render={<Link href="/register" />}>
          Ro&apos;yxatdan o&apos;tish
        </Button>
        <Button render={<Link href="/login" />}>Kirish</Button>
      </div>
    </div>
  );
}
