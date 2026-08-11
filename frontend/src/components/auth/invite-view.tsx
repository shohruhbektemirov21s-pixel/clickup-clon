import * as React from "react";
import { Link } from "@/components/ui/link";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RegisterForm } from "@/components/auth/auth-form";
import { useInvitationLookup } from "@/hooks/queries";
import { INVITE, ROLE_LABEL } from "@/i18n/uz";
import { api } from "@/lib/api";
import { keys } from "@/lib/keys";
import { useAuthStore } from "@/stores/auth-store";
import type { AcceptInvitationResponse } from "@/types/api";

// ---------------------------------------------------------------------------
// Token handoff (§F-6 MUST-5)
// ---------------------------------------------------------------------------

/**
 * "Hisobim bor" oqimida foydalanuvchi `/login` ga borib qaytadi. Ilgari bu
 * `?next=/invite/<token>` orqali qilinardi — ya'ni bearer token yana manzil
 * qatoriga chiqib, brauzer tarixiga, back/forward stekiga va bir xil manbali
 * so'rovlarning `Referer` sarlavhasiga tushardi. Sahifa yuklanishidagi
 * `replaceState` mudofaasi shu bilan butunlay bekor bo'lardi.
 *
 * Endi token shu tabning `sessionStorage`'ida qoladi, manzilga esa hech qanday
 * ma'lumot bermaydigan o'zgarmas bo'lak — `/invite/continue` — yoziladi.
 * Haqiqiy token `secrets.token_urlsafe(32)`, ya'ni 43 belgi, shuning uchun
 * sentinel bilan hech qachon to'qnashmaydi.
 */
const HANDOFF_KEY = "clickish.invite-handoff";
const HANDOFF_TTL_MS = 15 * 60_000;
const HANDOFF_PARAM = "continue";

/** `/login` havolasi — tokensiz, o'zgarmas. */
const LOGIN_HREF = `/login?next=/invite/${HANDOFF_PARAM}`;

interface Handoff {
  token: string;
  exp: number;
}

function readHandoffToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(HANDOFF_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Handoff>;
    if (
      typeof parsed.token !== "string" ||
      typeof parsed.exp !== "number" ||
      Date.now() > parsed.exp
    ) {
      window.sessionStorage.removeItem(HANDOFF_KEY);
      return null;
    }
    return parsed.token;
  } catch {
    return null;
  }
}

/**
 * Manzildagi bo'lak sentinel bo'lsa tokenni storage'dan olamiz; topilmasa
 * bo'sh satr qaytadi va sahifa "havola topilmadi" holatini ko'rsatadi.
 */
function resolveToken(param: string): string {
  if (param !== HANDOFF_PARAM) return param;
  return readHandoffToken() ?? "";
}

function stashToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    const handoff: Handoff = { token, exp: Date.now() + HANDOFF_TTL_MS };
    window.sessionStorage.setItem(HANDOFF_KEY, JSON.stringify(handoff));
  } catch {
    // Private rejim / o'chirilgan storage — qaytib kelganda "havola
    // topilmadi" ko'rsatiladi, lekin token baribir URL'ga chiqmaydi.
  }
}

function clearHandoff(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(HANDOFF_KEY);
  } catch {
    // Storage yo'q bo'lsa tozalanadigan narsa ham yo'q.
  }
}

/** Taklifni ko'rsatib bo'lmaydigan holatlar — ish maydoni nomi oshkor qilinmaydi. */
function InviteProblem({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="flex w-full flex-col gap-4 text-center">
      <h1 className="text-lg font-semibold">{title}</h1>
      <p className="text-sm text-muted-foreground">{hint}</p>
      <Button render={<Link href="/login" />}>{INVITE.goToLogin}</Button>
    </div>
  );
}

/**
 * Public taklif sahifasi — `/invite/[token]`.
 *
 * XAVFSIZLIK:
 *  * §F-6 MUST-5 — token URL'da qolmaydi: sahifa yuklangach `replaceState`
 *    bilan `/invite` ga almashtiriladi, token faqat React holatida qoladi.
 *    `/login` ga o'tishda ham token URL'ga qaytmaydi — yuqoridagi
 *    sessionStorage almashinuvi ishlatiladi.
 *  * Ish maydoni roli FAQAT O'QISH UCHUN ko'rsatiladi; uni o'zgartiradigan
 *    kiritma yo'q va register so'rovi rol yubormaydi (server `Invitation.role`
 *    dan oladi).
 *  * Token yaroqsiz bo'lsa ish maydoni nomi umuman ko'rsatilmaydi.
 */
export function InviteView({ token: tokenParam }: { token: string }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Manzildagi bo'lak `/login` dan qaytishda sentinel bo'ladi — birinchi
  // renderdayoq haqiqiy tokenga aylantiramiz, so'rov to'g'ri ketsin.
  const [token] = React.useState(() => resolveToken(tokenParam));
  const { data, isPending, isError } = useInvitationLookup(token);
  const authStatus = useAuthStore((s) => s.status);
  const me = useAuthStore((s) => s.user);
  const [joining, setJoining] = React.useState(false);
  const [joinError, setJoinError] = React.useState<string | undefined>();

  // Tokenni manzil qatoridan olib tashlaymiz (tarix, referer va yelka orqali
  // o'qishdan himoya) va `/login` ga borib qaytish uchun uni shu tabda
  // saqlaymiz. Token komponent holatida qoladi.
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.location.pathname.startsWith("/invite/")) {
      window.history.replaceState(null, "", "/invite");
    }
    if (token) stashToken(token);
  }, [token]);

  // Sentinel bilan keldik, lekin bu tabda saqlangan token yo'q: boshqa tab,
  // yopilgan sessiya yoki o'chirilgan storage.
  if (!token) {
    return (
      <InviteProblem title={INVITE.missingLinkTitle} hint={INVITE.missingLinkHint} />
    );
  }

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
      <InviteProblem title={INVITE.expiredTitle} hint={INVITE.expiredHint} />
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
      clearHandoff();
      await queryClient.invalidateQueries({ queryKey: keys.workspaces });
      navigate(`/w/${res.workspace_id}`, { replace: true });
    } catch {
      setJoinError(INVITE.acceptFailed);
      setJoining(false);
    }
  };

  const header = (
    <div className="flex flex-col gap-2">
      <h1 className="text-lg font-semibold">{INVITE.heading(data.workspace_name)}</h1>
      <p className="text-sm text-muted-foreground">
        {INVITE.sentToPrefix}
        <span className="font-medium text-foreground">{data.email}</span>
        {INVITE.sentToSuffix}
      </p>
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        {INVITE.roleGivenPrefix}
        <Badge variant="secondary">{roleLabel}</Badge>
        {INVITE.roleGivenSuffix}
      </p>
      <p className="text-xs text-muted-foreground">{INVITE.roleReadOnly}</p>
    </div>
  );

  // 1) Allaqachon to'g'ri hisob bilan kirgan → to'g'ridan-to'g'ri qo'shilish.
  if (sameAccount) {
    return (
      <div className="flex w-full flex-col gap-5">
        {header}
        <Button onClick={onJoin} disabled={joining} aria-busy={joining}>
          {joining ? INVITE.joining : INVITE.joinWorkspace}
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
          {INVITE.signedInPrefix}
          <span className="font-medium text-foreground">{me.email}</span>
          {INVITE.signedInSuffix}
          {INVITE.invitedAccountHint(data.email)}
        </p>
        <Button render={<Link href={LOGIN_HREF} />}>{INVITE.loginWithOtherAccount}</Button>
      </div>
    );
  }

  // 3) Bu email uchun hisob bor → kirish va qo'shilish.
  if (data.account_exists === true) {
    return (
      <div className="flex w-full flex-col gap-5">
        {header}
        <Button render={<Link href={LOGIN_HREF} />}>{INVITE.loginAndJoin}</Button>
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
          loginHref: LOGIN_HREF,
        }}
      />
    </div>
  );
}
