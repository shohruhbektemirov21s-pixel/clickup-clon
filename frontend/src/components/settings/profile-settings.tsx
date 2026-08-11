import * as React from "react";
import { Link } from "@/components/ui/link";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/hooks/queries";
import { useLogout } from "@/hooks/use-logout";
import { api, isApiError } from "@/lib/api";
import { keys } from "@/lib/keys";
import { initials } from "@/lib/format";
import { AUTH, COMMON, PROFILE_SETTINGS } from "@/i18n/uz";
import { useAuthStore } from "@/stores/auth-store";
import type { User } from "@/types/api";

export function ProfileSettings() {
  const queryClient = useQueryClient();
  const { data: me, isPending } = useMe();
  const setUser = useAuthStore((s) => s.setUser);
  const [fullName, setFullName] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [seededFrom, setSeededFrom] = React.useState<string | null>(null);
  // Seed the form once the profile arrives (render-time adjustment).
  if (me && seededFrom !== me.id) {
    setSeededFrom(me.id);
    setFullName(me.full_name);
  }

  const onSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await api.patch<User>("me/", { full_name: fullName.trim() });
      queryClient.setQueryData(keys.me, updated);
      setUser(updated);
      toast.success("Profil yangilandi");
    } catch (err) {
      toast.error(isApiError(err) ? err.message : PROFILE_SETTINGS.saveFailed);
    } finally {
      setSaving(false);
    }
  };

  const onLogout = useLogout();

  return (
    <main className="mx-auto w-full max-w-lg p-8">
      <Link
        href="/"
        className="mb-6 flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> {COMMON.backToWorkspace}
      </Link>
      <h1 className="mb-6 text-xl font-semibold">{PROFILE_SETTINGS.title}</h1>

      {isPending || !me ? (
        <div className="space-y-3" aria-hidden>
          <Skeleton className="size-16 rounded-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : (
        <form onSubmit={onSave} className="flex flex-col gap-4">
          <Avatar className="size-16">
            {me.avatar ? <AvatarImage src={me.avatar} alt="" /> : null}
            <AvatarFallback
              className="text-lg font-semibold text-primary-foreground"
              style={{ backgroundColor: me.avatar_color || "#7B68EE" }}
            >
              {initials(me.full_name, me.email ?? undefined)}
            </AvatarFallback>
          </Avatar>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="full-name">{AUTH.fullNameLabel}</Label>
            <Input
              id="full-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="profile-email">{COMMON.email}</Label>
            <Input id="profile-email" value={me.email} readOnly disabled />
            <p className="text-xs text-muted-foreground">
              {PROFILE_SETTINGS.emailReadOnly}
            </p>
          </div>
          <div className="flex items-center justify-between pt-2">
            <Button type="submit" disabled={saving || !fullName.trim()}>
              {saving ? COMMON.saving : COMMON.save}
            </Button>
            <Button type="button" variant="destructive" onClick={onLogout}>
              {PROFILE_SETTINGS.logout}
            </Button>
          </div>
        </form>
      )}
    </main>
  );
}
