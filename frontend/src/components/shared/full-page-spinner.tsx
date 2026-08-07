import { Loader2 } from "lucide-react";

export function FullPageSpinner() {
  return (
    <div className="flex min-h-screen flex-1 items-center justify-center">
      <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Loading" />
    </div>
  );
}
