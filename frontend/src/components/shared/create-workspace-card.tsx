import * as React from "react";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, isApiError } from "@/lib/api";
import { keys } from "@/lib/keys";
import { AUTH, WORKSPACE_CREATE } from "@/i18n/uz";
import type { Workspace } from "@/types/api";

/** Shown at `/` when the signed-in user has no workspace memberships. */
export function CreateWorkspaceCard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = React.useState("");
  const [pending, setPending] = React.useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setPending(true);
    try {
      const ws = await api.post<Workspace>("workspaces/", { name: name.trim() });
      await queryClient.invalidateQueries({ queryKey: keys.workspaces });
      navigate(`/w/${ws.id}`, { replace: true });
    } catch (err) {
      toast.error(isApiError(err) ? err.message : WORKSPACE_CREATE.failed);
      setPending(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <form
        onSubmit={onSubmit}
        className="flex w-full max-w-[400px] flex-col gap-4 rounded-xl border bg-background p-10 shadow-lg"
      >
        <h1 className="text-xl font-semibold">{WORKSPACE_CREATE.title}</h1>
        <p className="text-sm text-muted-foreground">{WORKSPACE_CREATE.subtitle}</p>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ws-name">{AUTH.workspaceNameLabel}</Label>
          <Input
            id="ws-name"
            autoFocus
            placeholder={AUTH.workspaceNamePlaceholder}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <Button type="submit" disabled={pending || !name.trim()}>
          {pending ? WORKSPACE_CREATE.creating : WORKSPACE_CREATE.submit}
        </Button>
      </form>
    </main>
  );
}
