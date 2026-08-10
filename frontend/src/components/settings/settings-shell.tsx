"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MailPlus, ShieldCheck, SlidersHorizontal, Users } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyPermissions, useWorkspace } from "@/hooks/queries";
import { can } from "@/lib/permissions";
import { cn } from "@/lib/utils";
import type { PermissionCode } from "@/types/api";

interface SettingsSection {
  segment: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  /** Section is hidden entirely unless the caller holds this code. */
  requires?: PermissionCode;
}

const SECTIONS: SettingsSection[] = [
  { segment: "", label: "Umumiy", icon: SlidersHorizontal },
  { segment: "members", label: "A'zolar", icon: Users, requires: "member.read" },
  {
    segment: "invitations",
    label: "Takliflar",
    icon: MailPlus,
    requires: "invitation.read",
  },
  {
    segment: "permissions",
    label: "Huquqlar",
    icon: ShieldCheck,
    requires: "workspace.manage_permissions",
  },
];

/**
 * Two-pane workspace settings frame: a section rail on the left, the routed
 * section on the right. Sections the caller cannot read are not rendered at
 * all — the permissions section must not even hint that it exists (§E.3).
 */
export function SettingsShell({
  workspaceId,
  children,
}: {
  workspaceId: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { data: workspace } = useWorkspace(workspaceId);
  const { data: my, isPending } = useMyPermissions(workspaceId);

  const base = `/w/${workspaceId}/settings`;
  const visible = SECTIONS.filter((s) => !s.requires || can(my, s.requires));

  return (
    <div className="flex flex-1 overflow-hidden">
      <nav
        aria-label="Sozlamalar bo'limlari"
        className="hidden w-56 shrink-0 flex-col gap-0.5 overflow-y-auto border-r p-3 md:flex"
      >
        <p className="mb-2 px-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
          Sozlamalar
        </p>
        {isPending ? (
          <div className="space-y-1.5 px-1" aria-hidden>
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : (
          visible.map((section) => {
            const href = section.segment ? `${base}/${section.segment}` : base;
            const active = pathname === href;
            const Icon = section.icon;
            return (
              <Link
                key={section.label}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors",
                  active
                    ? "bg-muted font-medium text-foreground"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                )}
              >
                <Icon className="size-4" />
                {section.label}
              </Link>
            );
          })
        )}
      </nav>

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-4xl p-8">
          <h1 className="mb-6 text-xl font-semibold">
            Ish maydoni sozlamalari{workspace ? ` — ${workspace.name}` : ""}
          </h1>
          {/* Section rail collapses on narrow screens — keep links reachable. */}
          <nav
            aria-label="Sozlamalar bo'limlari"
            className="mb-6 flex flex-wrap gap-1.5 md:hidden"
          >
            {visible.map((section) => {
              const href = section.segment ? `${base}/${section.segment}` : base;
              const active = pathname === href;
              return (
                <Link
                  key={section.label}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "rounded-lg border px-2.5 py-1 text-xs",
                    active
                      ? "border-transparent bg-muted font-medium"
                      : "text-muted-foreground",
                  )}
                >
                  {section.label}
                </Link>
              );
            })}
          </nav>
          {children}
        </div>
      </div>
    </div>
  );
}
