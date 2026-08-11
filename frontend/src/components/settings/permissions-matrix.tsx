import * as React from "react";
import {
  AlertTriangle,
  ChevronDown,
  Lock,
  RotateCcw,
  TriangleAlert,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  usePermissionCatalog,
  useMyPermissions,
  useRolePermissions,
} from "@/hooks/queries";
import {
  MATRIX_CONFLICT_MESSAGE,
  useResetRolePermissions,
  useUpdateRolePermissions,
} from "@/hooks/mutations";
import { isApiError } from "@/lib/api";
import { COMMON, PERMISSIONS_MATRIX, ROLE_LABEL } from "@/i18n/uz";
import { can } from "@/lib/permissions";
import { ROLE_COLUMNS } from "@/lib/roles";
import { cn } from "@/lib/utils";
import type {
  AssignableRole,
  PermissionCode,
  PermissionDef,
  Role,
  RolePermissionMatrix,
} from "@/types/api";

/** Sparse patch under construction: only cells the user actually flipped. */
type Draft = Partial<Record<AssignableRole, Partial<Record<PermissionCode, boolean>>>>;

const EDITABLE_ROLES: AssignableRole[] = ["admin", "member", "guest"];

const OWNER_LOCK_TOOLTIP = PERMISSIONS_MATRIX.ownerLockTooltip;

function isEditableRole(role: Role): role is AssignableRole {
  return role !== "owner";
}

/**
 * Yangi matritsa kelganda qoralamani tashlab yubormaymiz, balki unga
 * qaytadan "o'tqazamiz": server allaqachon rozi bo'lgan katakchalar olib
 * tashlanadi, qolganlari saqlanadi.
 *
 * Ilgari 409 (boshqa admin oldinroq saqlab yuborgan) `setDraft({})` qilardi —
 * toast esa "o'zgarishlaringizni ko'rib chiqing" derdi, holbuki ko'rib
 * chiqadigan narsa qolmasdi. Qoralama faqat serverdan farq qiladigan
 * katakchalarni saqlashi (`toggle` dagi invariant) shu yerda ham qo'llanadi.
 */
function rebaseDraft(draft: Draft, matrix: RolePermissionMatrix): Draft {
  const out: Draft = {};
  for (const role of EDITABLE_ROLES) {
    const cells = draft[role];
    if (!cells) continue;
    const serverGrants = new Set(matrix.roles[role]?.permissions ?? []);
    const kept: Partial<Record<PermissionCode, boolean>> = {};
    const entries = Object.entries(cells) as [PermissionCode, boolean | undefined][];
    for (const [code, next] of entries) {
      if (next !== undefined && serverGrants.has(code) !== next) kept[code] = next;
    }
    if (Object.keys(kept).length > 0) out[role] = kept;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

/**
 * Role × permission matrix editor (DESIGN_PERMISSIONS §E.3).
 *
 * The whole screen is hidden behind `workspace.manage_permissions`; without it
 * we render a plain not-found view so the section's existence is not disclosed.
 * Client-side gating is cosmetic — the server rejects every unauthorised write
 * independently.
 */
export function PermissionsMatrix({ workspaceId }: { workspaceId: string }) {
  const { data: my, isPending: myPending, isError: myError } = useMyPermissions(workspaceId);
  const canManage = can(my, "workspace.manage_permissions");

  const catalog = usePermissionCatalog();
  const matrix = useRolePermissions(workspaceId, canManage);

  if (myPending) return <MatrixSkeleton />;
  if (myError || !canManage) return <NotFoundView />;
  if (catalog.isPending || matrix.isPending) return <MatrixSkeleton />;

  if (catalog.isError || matrix.isError || !catalog.data || !matrix.data) {
    return (
      <div className="rounded-lg border border-danger/40 bg-danger/5 p-4 text-sm text-danger">
        {PERMISSIONS_MATRIX.loadFailed}
      </div>
    );
  }

  return (
    <MatrixEditor
      workspaceId={workspaceId}
      groups={catalog.data.groups}
      matrix={matrix.data}
    />
  );
}

function MatrixEditor({
  workspaceId,
  groups,
  matrix,
}: {
  workspaceId: string;
  groups: { key: string; label: string; permissions: PermissionDef[] }[];
  matrix: RolePermissionMatrix;
}) {
  const update = useUpdateRolePermissions(workspaceId);
  const reset = useResetRolePermissions(workspaceId);

  const [draft, setDraft] = React.useState<Draft>({});
  const [baseVersion, setBaseVersion] = React.useState(matrix.version);
  const [resetTarget, setResetTarget] = React.useState<AssignableRole | null | undefined>(
    undefined,
  );

  // The server version moved (our own save, a reset, or a 409 refetch) → the
  // draft was built on a state that no longer exists. Re-base it instead of
  // dropping it: a successful save leaves nothing behind anyway, while a 409
  // keeps every edit the winner did not already make.
  if (matrix.version !== baseVersion) {
    setBaseVersion(matrix.version);
    setDraft((prev) => rebaseDraft(prev, matrix));
  }

  /** Server-side grants per role, as sets for O(1) cell lookups. */
  const granted = React.useMemo(() => {
    const out = {} as Record<Role, Set<PermissionCode>>;
    for (const role of ROLE_COLUMNS) {
      out[role] = new Set(matrix.roles[role]?.permissions ?? []);
    }
    return out;
  }, [matrix.roles]);

  /** Cells that already deviate from the catalog defaults (§D.2 `overrides`). */
  const overridden = React.useMemo(
    () => new Set(matrix.overrides.map((o) => `${o.role}:${o.permission}`)),
    [matrix.overrides],
  );

  const valueOf = (role: AssignableRole, code: PermissionCode): boolean => {
    const local = draft[role]?.[code];
    return local !== undefined ? local : granted[role].has(code);
  };

  const toggle = (role: AssignableRole, code: PermissionCode, next: boolean) => {
    // A fresh edit invalidates the previous conflict banner.
    if (update.isError) update.reset();
    setDraft((prev) => {
      const forRole = { ...(prev[role] ?? {}) };
      if (granted[role].has(code) === next) {
        delete forRole[code]; // back to the server value — nothing to send
      } else {
        forRole[code] = next;
      }
      const out: Draft = { ...prev };
      if (Object.keys(forRole).length === 0) delete out[role];
      else out[role] = forRole;
      return out;
    });
  };

  const dirtyCount = EDITABLE_ROLES.reduce(
    (sum, role) => sum + Object.keys(draft[role] ?? {}).length,
    0,
  );

  const conflict = isApiError(update.error) && update.error.code === "conflict";
  const busy = update.isPending || reset.isPending;

  const save = () => {
    if (dirtyCount === 0) return;
    update.mutate({ expected_version: matrix.version, roles: draft });
  };

  return (
    <TooltipProvider delay={300}>
      <section className="mb-8">
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
              {PERMISSIONS_MATRIX.heading}
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              {PERMISSIONS_MATRIX.subtitle(matrix.version)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger
                render={<Button variant="outline" size="sm" disabled={busy} />}
              >
                <RotateCcw /> {PERMISSIONS_MATRIX.resetMenu}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {EDITABLE_ROLES.map((role) => (
                  <DropdownMenuItem key={role} onClick={() => setResetTarget(role)}>
                    {PERMISSIONS_MATRIX.resetRole(ROLE_LABEL[role])}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuItem onClick={() => setResetTarget(null)}>
                  {PERMISSIONS_MATRIX.resetEveryRole}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button size="sm" disabled={dirtyCount === 0 || busy} onClick={save}>
              {update.isPending
                ? COMMON.saving
                : dirtyCount > 0
                  ? PERMISSIONS_MATRIX.saveWithCount(dirtyCount)
                  : COMMON.save}
            </Button>
          </div>
        </header>

        {conflict ? (
          <div
            role="alert"
            className="mb-4 flex items-start gap-2 rounded-lg border border-danger/40 bg-danger/5 p-3 text-sm text-danger"
          >
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <span>{MATRIX_CONFLICT_MESSAGE}</span>
          </div>
        ) : null}

        <Legend />

        <div className="space-y-3">
          {groups.map((group) => (
            <PermissionGroupCard
              key={group.key}
              label={group.label}
              permissions={group.permissions}
              granted={granted}
              overridden={overridden}
              draft={draft}
              disabled={busy}
              valueOf={valueOf}
              onToggle={toggle}
            />
          ))}
        </div>

        <ResetDialog
          target={resetTarget}
          pending={reset.isPending}
          onOpenChange={(open) => {
            if (!open) setResetTarget(undefined);
          }}
          onConfirm={() => {
            if (resetTarget === undefined) return;
            reset.mutate(
              { role: resetTarget },
              {
                // Standartga qaytarish — ataylab qilingan buzg'unchi amal:
                // saqlanmagan qoralama ham u bilan birga bekor bo'ladi.
                onSuccess: () => setDraft({}),
                onSettled: () => setResetTarget(undefined),
              },
            );
          }}
        />
      </section>
    </TooltipProvider>
  );
}

// ---------------------------------------------------------------------------
// Group card
// ---------------------------------------------------------------------------

function PermissionGroupCard({
  label,
  permissions,
  granted,
  overridden,
  draft,
  disabled,
  valueOf,
  onToggle,
}: {
  label: string;
  permissions: PermissionDef[];
  granted: Record<Role, Set<PermissionCode>>;
  overridden: Set<string>;
  draft: Draft;
  disabled: boolean;
  valueOf: (role: AssignableRole, code: PermissionCode) => boolean;
  onToggle: (role: AssignableRole, code: PermissionCode, next: boolean) => void;
}) {
  const changedInGroup = permissions.filter((p) =>
    EDITABLE_ROLES.some((r) => overridden.has(`${r}:${p.code}`)),
  ).length;

  return (
    <Collapsible defaultOpen className="rounded-lg border">
      <CollapsibleTrigger
        render={
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-t-lg px-3 py-2.5 text-left text-sm font-medium hover:bg-muted/50"
          />
        }
      >
        <ChevronDown className="size-4 shrink-0 -rotate-90 text-muted-foreground transition-transform in-data-[panel-open]:rotate-0" />
        <span>{label}</span>
        <span className="text-xs font-normal text-muted-foreground">
          ({permissions.length})
        </span>
        {changedInGroup > 0 ? (
          <Badge variant="outline" className="ml-1">
            {PERMISSIONS_MATRIX.changedInGroup(changedInGroup)}
          </Badge>
        ) : null}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <Table className="table-fixed border-t">
          <TableHeader>
            <TableRow>
              <TableHead>{PERMISSIONS_MATRIX.colPermission}</TableHead>
              {ROLE_COLUMNS.map((role) => (
                <TableHead key={role} className="w-24 text-center">
                  <span className="inline-flex items-center gap-1">
                    {ROLE_LABEL[role]}
                    {role === "owner" ? <Lock className="size-3" /> : null}
                  </span>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {permissions.map((perm) => (
              <TableRow key={perm.code}>
                <TableCell className="align-middle">
                  <PermissionLabel perm={perm} />
                </TableCell>
                {ROLE_COLUMNS.map((role) => (
                  <TableCell key={role} className="text-center align-middle">
                    {isEditableRole(role) ? (
                      <MatrixCell
                        role={role}
                        perm={perm}
                        checked={valueOf(role, perm.code)}
                        dirty={draft[role]?.[perm.code] !== undefined}
                        changed={overridden.has(`${role}:${perm.code}`)}
                        disabled={disabled || perm.owner_only}
                        onToggle={onToggle}
                      />
                    ) : (
                      <OwnerCell granted={granted.owner.has(perm.code)} />
                    )}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CollapsibleContent>
    </Collapsible>
  );
}

function PermissionLabel({ perm }: { perm: PermissionDef }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Tooltip>
        <TooltipTrigger
          render={
            <span className="cursor-help font-medium underline decoration-dotted underline-offset-4" />
          }
        >
          {perm.label}
        </TooltipTrigger>
        <TooltipContent side="right">{perm.description}</TooltipContent>
      </Tooltip>
      {perm.sensitive ? (
        <Tooltip>
          <TooltipTrigger render={<span className="inline-flex" />}>
            <TriangleAlert className="size-3.5 text-amber-500" aria-hidden />
            <span className="sr-only">{PERMISSIONS_MATRIX.sensitiveLabel}</span>
          </TooltipTrigger>
          <TooltipContent>{PERMISSIONS_MATRIX.sensitiveTooltip}</TooltipContent>
        </Tooltip>
      ) : null}
      {perm.owner_only ? (
        <Tooltip>
          <TooltipTrigger render={<span className="inline-flex" />}>
            <Lock className="size-3.5 text-muted-foreground" aria-hidden />
            <span className="sr-only">{PERMISSIONS_MATRIX.ownerOnlyLabel}</span>
          </TooltipTrigger>
          <TooltipContent>{PERMISSIONS_MATRIX.ownerOnlyTooltip}</TooltipContent>
        </Tooltip>
      ) : null}
      <code className="text-[11px] text-muted-foreground">{perm.code}</code>
    </span>
  );
}

/** Owner column: always granted, never editable (AD-3). */
function OwnerCell({ granted }: { granted: boolean }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={<span className="inline-flex items-center justify-center gap-1" />}
      >
        <Checkbox checked={granted} disabled aria-label={OWNER_LOCK_TOOLTIP} />
        <Lock className="size-3 text-muted-foreground" aria-hidden />
      </TooltipTrigger>
      <TooltipContent>{OWNER_LOCK_TOOLTIP}</TooltipContent>
    </Tooltip>
  );
}

function MatrixCell({
  role,
  perm,
  checked,
  dirty,
  changed,
  disabled,
  onToggle,
}: {
  role: AssignableRole;
  perm: PermissionDef;
  checked: boolean;
  dirty: boolean;
  changed: boolean;
  disabled: boolean;
  onToggle: (role: AssignableRole, code: PermissionCode, next: boolean) => void;
}) {
  return (
    <span className="relative inline-flex items-center justify-center">
      <Checkbox
        data-cell={`${role}:${perm.code}`}
        aria-label={`${ROLE_LABEL[role]} — ${perm.label}`}
        checked={checked}
        disabled={disabled}
        onCheckedChange={(next) => onToggle(role, perm.code, next)}
        className={cn(dirty && "ring-3 ring-amber-400/60")}
      />
      {changed || dirty ? (
        <span
          aria-label={dirty ? PERMISSIONS_MATRIX.dirtyDot : PERMISSIONS_MATRIX.changedDot}
          title={
            dirty ? PERMISSIONS_MATRIX.dirtyDot : PERMISSIONS_MATRIX.changedDotTitle
          }
          className={cn(
            "pointer-events-none absolute -top-1 -right-2 size-1.5 rounded-full",
            dirty ? "bg-amber-500" : "bg-primary",
          )}
        />
      ) : null}
    </span>
  );
}

function Legend() {
  return (
    <ul className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <li className="inline-flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-primary" />
        {PERMISSIONS_MATRIX.legendChanged}
      </li>
      <li className="inline-flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-amber-500" />
        {PERMISSIONS_MATRIX.dirtyDot}
      </li>
      <li className="inline-flex items-center gap-1.5">
        <TriangleAlert className="size-3.5 text-amber-500" />
        {PERMISSIONS_MATRIX.sensitiveLabel}
      </li>
      <li className="inline-flex items-center gap-1.5">
        <Lock className="size-3.5" />
        {PERMISSIONS_MATRIX.legendOwnerOnly}
      </li>
    </ul>
  );
}

function ResetDialog({
  target,
  pending,
  onOpenChange,
  onConfirm,
}: {
  target: AssignableRole | null | undefined;
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  const open = target !== undefined;
  const what =
    target === null || target === undefined
      ? PERMISSIONS_MATRIX.resetTargetAll
      : PERMISSIONS_MATRIX.resetTargetRole(ROLE_LABEL[target]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{PERMISSIONS_MATRIX.resetTitle}</DialogTitle>
          <DialogDescription>
            <span className="font-medium text-foreground">{what}</span>{" "}
            {PERMISSIONS_MATRIX.resetDescription}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            {COMMON.cancel}
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={pending}
            onClick={onConfirm}
          >
            {pending ? PERMISSIONS_MATRIX.resetting : PERMISSIONS_MATRIX.resetConfirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MatrixSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <Skeleton className="h-9 w-72" />
      <Skeleton className="h-5 w-full max-w-lg" />
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-40 w-full" />
      ))}
    </div>
  );
}

/**
 * Rendered instead of the matrix when the caller lacks
 * `workspace.manage_permissions`: the page must not reveal that a permissions
 * section exists at all (§E.3).
 */
function NotFoundView() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-24 text-center">
      <p className="text-4xl font-semibold text-muted-foreground">404</p>
      <p className="text-sm text-muted-foreground">{PERMISSIONS_MATRIX.notFound}</p>
    </div>
  );
}
