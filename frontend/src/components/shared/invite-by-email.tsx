import * as React from "react";
import { AlertTriangle, CheckCircle2, HelpCircle, Loader2, UserPlus, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { INVITE_EMAIL } from "@/i18n/uz";
import { api, isApiError } from "@/lib/api";
import { useCreateInvitation } from "@/hooks/mutations";
import type { EmailCheckResponse, EmailCheckStatus, InvitableRole } from "@/types/api";

/**
 * Tayinlash tanlagichida a'zo topilmaganda ko'rinadigan blok.
 *
 * Oqim: yozilgan matn email'ga o'xshasa → «Tekshirish» → server manzil
 * mavjudligini aytadi → «Taklif qilish» → taklif yuboriladi.
 *
 * Nega tekshiruv ALOHIDA qadam, avtomatik emas: har bir tugmacha bosishda
 * so'rov yuborish serverdan begona MX'larga SMTP probe qildiradi. Bu qimmat,
 * sekin va IP obro'siga ta'sir qiladi, shuning uchun uni foydalanuvchi
 * ataylab boshlaydi.
 */

const STATUS_STYLE: Record<
  EmailCheckStatus,
  { icon: React.ElementType; className: string }
> = {
  valid: { icon: CheckCircle2, className: "text-status-done" },
  invalid: { icon: XCircle, className: "text-priority-urgent" },
  risky: { icon: AlertTriangle, className: "text-priority-high" },
  unknown: { icon: HelpCircle, className: "text-muted-foreground" },
};

/** Ro'yxatda a'zo topilmaganda yozilgan matn email'mi. */
export function looksLikeEmail(text: string): boolean {
  const value = text.trim();
  return /^[^\s@]+@[^\s@.]+\.[^\s@]+$/.test(value);
}

export function InviteByEmail({
  email,
  workspaceId,
  role = "member",
  onInvited,
}: {
  email: string;
  workspaceId: string;
  role?: InvitableRole;
  /** Taklif yuborilgach chaqiriladi — chaqiruvchi popover'ni yopadi. */
  onInvited?: (email: string) => void;
}) {
  const [checking, setChecking] = React.useState(false);
  const [checked, setChecked] = React.useState<EmailCheckResponse | null>(null);
  const createInvitation = useCreateInvitation(workspaceId);

  const trimmed = email.trim();

  // Natija QAYSI manzil uchun olingani bilan solishtiriladi. Effekt bilan
  // tozalash mumkin edi, lekin u ortiqcha render davri hosil qiladi va
  // oradagi kadrda boshqa manzilning javobi ko'rinib qolardi. Render
  // paytida hisoblash bu ikkala muammoni ham yo'q qiladi.
  //
  // Solishtiruv IKKALA tomonda ham registrsiz: server faqat DOMENNI kichik
  // harfga o'tkazadi (local qism RFC bo'yicha registrga sezgir), shuning
  // uchun `Ali@Gmail.com` → `Ali@gmail.com` qaytadi. To'g'ridan-to'g'ri
  // solishtirilsa mos kelmasdi va natija umuman ko'rinmasdi.
  const result =
    checked && checked.email.toLowerCase() === trimmed.toLowerCase() ? checked : null;

  const check = async () => {
    setChecking(true);
    try {
      const response = await api.post<EmailCheckResponse>(
        `workspaces/${workspaceId}/check-email/`,
        { email: trimmed },
      );
      setChecked(response);
    } catch (err) {
      if (isApiError(err) && err.code === "throttled") {
        toast.error(INVITE_EMAIL.throttled);
      } else if (isApiError(err) && err.code === "permission_denied") {
        toast.error(INVITE_EMAIL.forbidden);
      } else {
        toast.error(INVITE_EMAIL.checkFailed);
      }
    } finally {
      setChecking(false);
    }
  };

  const invite = async () => {
    try {
      await createInvitation.mutateAsync({ email: trimmed, role });
      onInvited?.(trimmed);
    } catch {
      // `useCreateInvitation` xabarni o'zi ko'rsatadi.
    }
  };

  const Icon = result ? STATUS_STYLE[result.status].icon : UserPlus;
  const iconClass = result ? STATUS_STYLE[result.status].className : "text-muted-foreground";

  return (
    <div className="border-t px-3 py-2.5">
      <p className="flex items-center gap-2 text-xs">
        <Icon aria-hidden className={`size-3.5 shrink-0 ${iconClass}`} />
        <span className="min-w-0 flex-1 truncate font-medium">{trimmed}</span>
      </p>

      {result ? (
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
          <span className={STATUS_STYLE[result.status].className}>{result.status_label}</span>
          {" — "}
          {result.reason}
        </p>
      ) : (
        <p className="mt-1 text-[11px] text-muted-foreground">
          {INVITE_EMAIL.notInWorkspace}
        </p>
      )}

      <div className="mt-2 flex gap-2">
        <Button
          size="sm"
          variant="outline"
          className="h-7 flex-1 text-xs"
          onClick={check}
          disabled={checking}
        >
          {checking ? <Loader2 className="size-3.5 animate-spin" /> : null}
          {checking
            ? INVITE_EMAIL.checking
            : result
              ? INVITE_EMAIL.recheck
              : INVITE_EMAIL.check}
        </Button>
        <Button
          size="sm"
          className="h-7 flex-1 text-xs"
          onClick={invite}
          // Manzil mavjud emasligi ANIQ bo'lsa taklif yuborishdan to'sadi:
          // bunday taklif hech qachon yetib bormaydi va bounce hosil qiladi.
          // `risky`/`unknown` da to'smaymiz — ular "bilmayman" degani.
          disabled={
            createInvitation.isPending ||
            result?.status === "invalid" ||
            result?.membership === "member" ||
            result?.membership === "invited"
          }
        >
          {createInvitation.isPending ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <UserPlus className="size-3.5" />
          )}
          {result?.membership === "invited"
            ? INVITE_EMAIL.alreadyInvited
            : INVITE_EMAIL.invite}
        </Button>
      </div>

      {result?.status === "risky" || result?.status === "unknown" ? (
        <p className="mt-1.5 text-[11px] text-muted-foreground">{INVITE_EMAIL.uncertain}</p>
      ) : null}
    </div>
  );
}
