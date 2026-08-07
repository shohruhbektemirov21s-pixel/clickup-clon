"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Folder as FolderIcon, List as ListIcon, Search, SquareCheck } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useWorkspaceSearch } from "@/hooks/queries";

export function SearchResults({ workspaceId }: { workspaceId: string }) {
  const searchParams = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const { data, isPending, isError } = useWorkspaceSearch(workspaceId, q);

  if (q.trim().length < 2) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-12 text-center text-muted-foreground">
        <Search className="size-6" />
        <p className="text-sm">Qidiruv maydoniga kamida 2 ta belgi kiriting.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-2xl flex-1 overflow-y-auto p-8">
      <h1 className="mb-4 text-lg font-semibold">
        “{q}” bo&apos;yicha natijalar {data ? `(${data.count})` : ""}
      </h1>
      {isPending ? (
        <div className="space-y-2" aria-hidden>
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-danger">Qidiruv amalga oshmadi. Qayta urinib ko&apos;ring.</p>
      ) : data && data.results.length === 0 ? (
        <p className="text-sm text-muted-foreground">“{q}” bo&apos;yicha natija topilmadi.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {data?.results.map((result) => {
            switch (result.type) {
              case "task":
                return (
                  <li key={`task-${result.item.id}`}>
                    <Link
                      href={`/w/${workspaceId}/l/${result.item.list_id}?task=${result.item.id}`}
                      className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted"
                    >
                      <SquareCheck className="size-4 text-muted-foreground" />
                      <span className="truncate">{result.item.title}</span>
                      <span className="ml-auto text-xs text-muted-foreground">Vazifa</span>
                    </Link>
                  </li>
                );
              case "list":
                return (
                  <li key={`list-${result.item.id}`}>
                    <Link
                      href={`/w/${workspaceId}/l/${result.item.id}`}
                      className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted"
                    >
                      <ListIcon className="size-4 text-muted-foreground" />
                      <span className="truncate">{result.item.name}</span>
                      <span className="ml-auto text-xs text-muted-foreground">Ro&apos;yxat</span>
                    </Link>
                  </li>
                );
              case "folder":
                return (
                  <li
                    key={`folder-${result.item.id}`}
                    className="flex items-center gap-2 rounded-md px-3 py-2 text-sm"
                  >
                    <FolderIcon className="size-4 text-muted-foreground" />
                    <span className="truncate">{result.item.name}</span>
                    <span className="ml-auto text-xs text-muted-foreground">Jild</span>
                  </li>
                );
              case "space":
                return (
                  <li
                    key={`space-${result.item.id}`}
                    className="flex items-center gap-2 rounded-md px-3 py-2 text-sm"
                  >
                    <span
                      className="size-2.5 rounded-full"
                      style={{ backgroundColor: result.item.color || "#7B68EE" }}
                    />
                    <span className="truncate">{result.item.name}</span>
                    <span className="ml-auto text-xs text-muted-foreground">Bo&apos;lim</span>
                  </li>
                );
            }
          })}
        </ul>
      )}
    </div>
  );
}
