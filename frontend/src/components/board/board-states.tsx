"use client";

import { AlertTriangle, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Loading state — four column shells that match the real column chrome
 * (accent bar + header row + 68px cards) so the swap to data does not jump.
 */
export function BoardSkeleton({ columns = 4 }: { columns?: number }) {
  return (
    <div
      className="flex flex-1 items-start gap-4 overflow-hidden p-4"
      role="status"
      aria-label="Doska yuklanmoqda"
    >
      {Array.from({ length: columns }).map((_, col) => (
        <div
          key={col}
          className="flex w-72 shrink-0 flex-col overflow-hidden rounded-lg bg-muted/50"
          aria-hidden
        >
          <Skeleton className="h-0.5 w-full rounded-none" />
          <div className="flex items-center gap-2 px-3 py-2.5">
            <Skeleton className="size-2.5 rounded-full" />
            <Skeleton className="h-3 w-24" />
            <Skeleton className="ml-auto h-4 w-6 rounded-full" />
          </div>
          <div className="flex flex-col gap-2 px-2 pb-2">
            {Array.from({ length: 3 - (col % 2) }).map((_, i) => (
              <div
                key={i}
                className="flex h-[68px] flex-col justify-between rounded-lg border bg-card p-3"
              >
                <Skeleton className="h-3 w-4/5" />
                <div className="flex items-center gap-2">
                  <Skeleton className="h-3 w-12" />
                  <Skeleton className="ml-auto size-5 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      <span className="sr-only">Doska yuklanmoqda…</span>
    </div>
  );
}

/** Full-board error with a retry affordance (UI_SPEC S6 → "Error"). */
export function BoardError({
  onRetry,
  isRetrying,
}: {
  onRetry: () => void;
  isRetrying?: boolean;
}) {
  return (
    <div
      role="alert"
      className="flex flex-1 flex-col items-center justify-center gap-3 p-12 text-center"
    >
      <span className="flex size-10 items-center justify-center rounded-full bg-danger/10 text-danger">
        <AlertTriangle className="size-5" />
      </span>
      <div className="space-y-1">
        <p className="text-sm font-medium">Doskani yuklab bo&apos;lmadi</p>
        <p className="text-xs text-muted-foreground">
          Ulanishni tekshiring va qaytadan urinib ko&apos;ring.
        </p>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry} disabled={isRetrying}>
        <RotateCw className={isRetrying ? "animate-spin" : undefined} />
        Qayta urinish
      </Button>
    </div>
  );
}
