"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RegisterForm } from "@/components/auth/auth-form";
import { useInvitationLookup } from "@/hooks/queries";
import { api } from "@/lib/api";
import { keys } from "@/lib/keys";
import { ROLE_LABEL } from "@/lib/roles";
import { useAuthStore } from "@/stores/auth-store";
import type { AcceptInvitationResponse } from "@/types/api";

/**
 * Public taklif sahifasi — `/invite/[token]`.
 *
 * XAVFSIZLIK:
 *  * §F-6 MUST-5 — token URL'da qolmaydi: sahifa yuklangach `replaceState`
 *    bilan `/invite` ga almashtiriladi, token faqat React holatida qoladi.
 *  * Ish maydoni roli FAQAT O'QISH UCHUN ko'rsatiladi; uni o'zgartiradigan
 *    kiritma yo'q va register so'rovi rol yubormaydi (server `Invitation.role`
 *    dan oladi).
 *  * Token yaroqsiz bo'lsa ish maydoni nomi umuman ko'rsatilmaydi.
 */
export function InviteView({ token }: { token: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data, isPending, isError } = useInvitationLookup(token);
  const authStatus = useAuthStore((s) => s.status);
  const me = useAuthStore((s) => s.user);
  const [joining, setJoining] = React.useState(false);
  const [joinError, setJoinError] = React.useState<string | undefined>();

  // Tokenni manzil qatoridan olib tashlaymiz (tarix, referer va yelka orqali
  // o'qishdan himoya). Token komponent props'ida qoladi.
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.location.pathname.startsWith("/invite/")) {
      window.history.replaceState(null, "", "/invite");
    }
  }, []);

  // Sessiya tiklanmaguncha kutamiz — aks holda kirgan foydalanuvchiga bir
  // lahzaga ro'yxatdan o'tish formasi ko'rinib ketadi.
  if (isPending || authStatus === "loading") {
    return (
      <div className="flex w-full flex-col gap-3">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-9 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    // Ish maydoni nomi OSHKOR QILINMAYDI.
    return (
      <div className="flex w-full flex-col gap-4 text-center">
        <h1 className="text-lg font-semibold">Taklif muddati tugagan yoki bekor qilingan</h1>
        <p className="text-sm text-muted-foreground">
          Havola ishlamayapti. Ish maydoni administratoridan yangi taklif so&apos;rang.
        </p>
        <Button render={<Link href="/login" />}>Kirish sahifasiga o&apos;tish</Button>
      </div>
    );
  }

  const roleLabel = ROLE_LABEL[data.role];
  const sameAccount =
    authStatus === "authenticated" &&
    !!me &&
    me.email.toLowerCase() === data.email.toLowerCase();

  const onJoin = async () => {
    setJoining(true);
    setJoinError(undefined);
    try {
      const res = await api.post<AcceptInvitationResponse>("invitations/accept/", { token });
      await queryClient.invalidateQueries({ queryKey: keys.workspaces });
      router.replace(`/w/${res.workspace_id}`);
    } catch {
      setJoinError("Taklifni qabul qilib bo'lmadi. Havola eskirgan bo'lishi mumkin.");
      setJoining(false);
    }
  };

  const header = (
    <div className="flex flex-col gap-2">
      <h1 className="text-lg font-semibold">
        Siz &laquo;{data.workspace_name}&raquo; ish maydoniga taklif qilingansiz
      </h1>
      <p className="text-sm text-muted-foreground">
        Taklif <span className="font-medium text-foreground">{data.email}</span> manziliga
        yuborilgan.
      </p>
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        Sizga <Badge variant="secondary">{roleLabel}</Badge> roli berilgan
      </p>
      <p className="text-xs text-muted-foreground">
        Rolni administrator belgilaydi — uni bu yerda o&apos;zgartirib bo&apos;lmaydi.
      </p>
    </div>
  );

  // 1) Allaqachon to'g'ri hisob bilan kirgan → to'g'ridan-to'g'ri qo'shilish.
  if (sameAccount) {
    return (
      <div className="flex w-full flex-col gap-5">
        {header}
        <Button onClick={onJoin} disabled={joining} aria-busy={joining}>
          {joining ? "Qo'shilmoqda…" : "Ish maydoniga qo'shilish"}
        </Button>
        {joinError ? (
          <p role="alert" className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
            {joinError}
          </p>
        ) : null}
      </div>
    );
  }

  // 2) Boshqa hisob bilan kirgan → taklif emailiga o'tish kerak.
  if (authStatus === "authenticated" && me) {
    return (
      <div className="flex w-full flex-col gap-5">
        {header}
        <p className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
          Siz hozir <span className="font-medium text-foreground">{me.email}</span> hisobi
          bilan kirgansiz. Taklifni qabul qilish uchun {data.email} hisobiga kiring.
        </p>
        <Button render={<Link href={`/login?next=/invite/${token}`} />}>
          Boshqa hisob bilan kirish
        </Button>
      </div>
    );
  }

  // 3) Bu email uchun hisob bor → kirish va qo'shilish.
  if (data.account_exists === true) {
    return (
      <div className="flex w-full flex-col gap-5">
        {header}
        <Button render={<Link href={`/login?next=/invite/${token}`} />}>
          Kirish va qo&apos;shilish
        </Button>
      </div>
    );
  }

  // 4) Hisob yo'q (yoki noma'lum) → ro'yxatdan o'tish formasi.
  return (
    <div className="flex w-full flex-col gap-5">
      {header}
      <RegisterForm
        invite={{
          token,
          email: data.email,
          workspaceName: data.workspace_name,
          role: data.role,
        }}
      />
    </div>
  );
}
