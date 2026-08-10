"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { demoLogin } from "@/lib/auth";
import { DEMO_MODE } from "@/lib/env";
import { keys } from "@/lib/keys";

/**
 * "Demo rejimda kirish".
 *
 * XAVFSIZLIK: demo hisobning paroli bu bundle'da YO'Q — tugma faqat
 * `POST auth/demo/` ni chaqiradi va backend token juftligini qaytaradi.
 * Backend'da `DEMO_MODE` o'chiq bo'lsa endpoint 404 beradi, shuning uchun
 * bayroqning bu yerdagi nusxasi faqat tugmani ko'rsatish/yashirish uchun.
 */
export function DemoLoginButton({
  onWorkspaceRoute,
}: {
  /** Javobda `workspace_id` bo'lmasa qayerga borishni hal qiladi. */
  onWorkspaceRoute: () => Promise<string>;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | undefined>();

  if (!DEMO_MODE) return null;

  const onClick = async () => {
    setPending(true);
    setError(undefined);
    try {
      const res = await demoLogin();
      queryClient.setQueryData(keys.me, res.user);
      router.replace(res.workspace_id ? `/w/${res.workspace_id}` : await onWorkspaceRoute());
    } catch {
      setError("Demo rejim hozir mavjud emas.");
      setPending(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground">yoki</span>
        <span className="h-px flex-1 bg-border" />
      </div>
      <Button
        type="button"
        variant="outline"
        onClick={onClick}
        disabled={pending}
        aria-busy={pending}
      >
        {pending ? "Kirilmoqda…" : "Demo rejimda kirish"}
      </Button>
      <p className="text-center text-xs text-muted-foreground">
        Ro&apos;yxatdan o&apos;tmasdan ilovani sinab ko&apos;ring
      </p>
      {error ? (
        <p role="alert" className="text-center text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
