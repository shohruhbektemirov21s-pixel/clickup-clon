import * as React from "react";
import { Check, Loader2, Search, UserPlus } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useUserSearch } from "@/hooks/queries";
import { useAddExistingMember, useCreateInvitation } from "@/hooks/mutations";
import { INVITE_DIALOG, COMMON, ROLE_LABEL } from "@/i18n/uz";
import { initials } from "@/lib/format";
import type { InvitableRole, UserSearchResult } from "@/types/api";

type Mode = "search" | "email";

/**
 * «Jamoaga qo'shish» — ikkita yo'l, bitta dialog.
 *
 * 1. **Ro'yxatdan o'tgan foydalanuvchi** (`POST workspaces/{id}/members/`):
 *    a'zolik shu zahoti tug'iladi, odam bildirishnoma oladi va hech qanday
 *    email/token oralig'i yo'q.
 * 2. **Email orqali taklif** (`POST workspaces/{id}/invitations/`): hisobi
 *    hali yo'q odam uchun — yagona holat, unda taklif haqiqatan kerak.
 *
 * Standart yorliq — qidiruv: ko'p hollarda odam allaqachon ro'yxatdan o'tgan
 * bo'ladi va taklif kutish bosqichi ortiqcha.
 */
export function InviteMemberDialog({
  workspaceId,
  open,
  onOpenChange,
}: {
  workspaceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [mode, setMode] = React.useState<Mode>("search");
  const [role, setRole] = React.useState<InvitableRole>("member");
  const [query, setQuery] = React.useState("");
  const [email, setEmail] = React.useState("");

  const createInvitation = useCreateInvitation(workspaceId);
  const addMember = useAddExistingMember(workspaceId);

  // Dialog har ochilganda toza holat.
  const [lastOpen, setLastOpen] = React.useState(open);
  if (open !== lastOpen) {
    setLastOpen(open);
    if (open) {
      setMode("search");
      setRole("member");
      setQuery("");
      setEmail("");
    }
  }

  const onSubmitEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) return;
    try {
      await createInvitation.mutateAsync({ email: trimmed, role });
      onOpenChange(false);
    } catch {
      // Xato toast mutatsiyadan chiqadi; dialog ochiq qoladi, manzilni
      // tuzatish mumkin.
    }
  };

  const onAdd = async (userId: string) => {
    try {
      await addMember.mutateAsync({ user_id: userId, role });
      onOpenChange(false);
    } catch {
      // Xato toast mutatsiyadan chiqadi.
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{INVITE_DIALOG.title}</DialogTitle>
          <DialogDescription>{INVITE_DIALOG.description}</DialogDescription>
        </DialogHeader>

        {/* Rol ikkala yo'l uchun ham bitta — u «kim bo'lib qo'shiladi»
            savoliga javob beradi, qo'shish usuliga bog'liq emas. */}
        <div className="flex flex-col gap-1.5">
          <Label>{INVITE_DIALOG.roleLabel}</Label>
          <RadioGroup
            value={role}
            onValueChange={(v) => setRole(v as InvitableRole)}
            className="flex gap-4"
          >
            {(["admin", "member", "guest"] as const).map((r) => (
              <label key={r} className="flex items-center gap-1.5 text-sm">
                <RadioGroupItem value={r} /> {ROLE_LABEL[r]}
              </label>
            ))}
          </RadioGroup>
          <p className="text-xs text-muted-foreground">{INVITE_DIALOG.guestHint}</p>
        </div>

        <Tabs value={mode} onValueChange={(value) => setMode(value as Mode)}>
          <TabsList className="w-full">
            <TabsTrigger value="search" className="flex-1">
              {INVITE_DIALOG.tabSearch}
            </TabsTrigger>
            <TabsTrigger value="email" className="flex-1">
              {INVITE_DIALOG.tabEmail}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="search" className="mt-3">
            <UserSearchPanel
              workspaceId={workspaceId}
              query={query}
              onQueryChange={setQuery}
              onAdd={onAdd}
              pendingUserId={addMember.isPending ? addMember.variables?.user_id : undefined}
            />
          </TabsContent>

          <TabsContent value="email" className="mt-3">
            <form onSubmit={onSubmitEmail} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="invite-email">{INVITE_DIALOG.emailLabel}</Label>
                <Input
                  id="invite-email"
                  type="email"
                  placeholder={INVITE_DIALOG.emailPlaceholder}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
                <p className="text-xs text-muted-foreground">{INVITE_DIALOG.emailHint}</p>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => onOpenChange(false)}
                >
                  {COMMON.cancel}
                </Button>
                <Button
                  type="submit"
                  disabled={createInvitation.isPending || !email.trim()}
                >
                  {createInvitation.isPending ? INVITE_DIALOG.sending : INVITE_DIALOG.sendInvite}
                </Button>
              </DialogFooter>
            </form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Qidiruv paneli. So'rov 2 belgidan boshlanadi — server ham shu chegarani
 * qo'yadi, shuning uchun bitta harf yozilganda so'rov umuman ketmaydi.
 */
function UserSearchPanel({
  workspaceId,
  query,
  onQueryChange,
  onAdd,
  pendingUserId,
}: {
  workspaceId: string;
  query: string;
  onQueryChange: (value: string) => void;
  onAdd: (userId: string) => void;
  pendingUserId?: string;
}) {
  // Dialog `member.invite` bor joydan ochiladi (yon paneldagi «＋» va
  // sozlamalar sahifasi), shuning uchun bu yerda qayta gate qilinmaydi —
  // server baribir 403 beradi.
  const search = useUserSearch(workspaceId, query, true);
  const results = search.data?.results ?? [];
  const tooShort = query.trim().length < 2;

  return (
    <div className="flex flex-col gap-2">
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          autoFocus
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder={INVITE_DIALOG.searchPlaceholder}
          aria-label={INVITE_DIALOG.searchAria}
          className="pl-8"
        />
      </div>

      <div className="min-h-40">
        {tooShort ? (
          <p className="px-1 py-6 text-center text-sm text-muted-foreground">
            {INVITE_DIALOG.searchTooShort}
          </p>
        ) : search.isPending ? (
          <div className="flex flex-col gap-2 py-2" aria-hidden>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-11 w-full" />
            ))}
          </div>
        ) : search.isError ? (
          <div className="flex flex-col items-start gap-2 py-3">
            <p className="text-sm text-danger">{INVITE_DIALOG.searchFailed}</p>
            <Button variant="outline" size="sm" onClick={() => search.refetch()}>
              {COMMON.retry}
            </Button>
          </div>
        ) : results.length === 0 ? (
          <p className="px-1 py-6 text-center text-sm text-muted-foreground">
            {INVITE_DIALOG.searchEmpty}
          </p>
        ) : (
          <ul className="max-h-56 overflow-y-auto">
            {results.map((row) => (
              <li key={row.user.id}>
                <UserSearchRow
                  row={row}
                  pending={pendingUserId === row.user.id}
                  onAdd={() => onAdd(row.user.id)}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function UserSearchRow({
  row,
  pending,
  onAdd,
}: {
  row: UserSearchResult;
  pending: boolean;
  onAdd: () => void;
}) {
  const name = row.user.full_name || row.user.email || COMMON.someone;
  return (
    <div className="flex items-center gap-2.5 rounded-md px-1.5 py-2 hover:bg-muted/60">
      <Avatar className="size-8 shrink-0">
        {row.user.avatar ? <AvatarImage src={row.user.avatar} alt="" /> : null}
        <AvatarFallback
          className="text-[11px] font-semibold text-primary-foreground"
          style={{ backgroundColor: row.user.avatar_color || "#7B68EE" }}
        >
          {initials(row.user.full_name, row.user.email ?? undefined)}
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{name}</p>
        {row.user.email ? (
          <p className="truncate text-xs text-muted-foreground">{row.user.email}</p>
        ) : null}
      </div>
      {row.is_member ? (
        <Badge variant="secondary" className="shrink-0 gap-1">
          <Check className="size-3" />
          {row.role ? ROLE_LABEL[row.role] : INVITE_DIALOG.inTeam}
        </Badge>
      ) : (
        <div className="flex shrink-0 items-center gap-1.5">
          {row.has_pending_invitation ? (
            <span className="text-[11px] text-muted-foreground">
              {INVITE_DIALOG.invitationPending}
            </span>
          ) : null}
          <Button size="sm" className="h-7 gap-1.5" disabled={pending} onClick={onAdd}>
            {pending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <UserPlus className="size-3.5" />
            )}
            {COMMON.add}
          </Button>
        </div>
      )}
    </div>
  );
}
