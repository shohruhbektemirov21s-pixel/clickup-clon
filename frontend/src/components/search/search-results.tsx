"use client";

/**
 * S8 — to'liq qidiruv natijalari sahifasi (`/w/{id}/search?q=`).
 *
 * URL — haqiqat manbai: `?q=` almashinadigan havola bo'lib qoladi va sahifa
 * yangilangandan keyin ham tirik. Kiritish maydoni esa lokal holatda turadi va
 * 250 ms debounce'dan keyingina URL'ni `replace` qiladi, ya'ni har bir harf
 * uchun brauzer tarixiga yozuv qo'shilmaydi.
 */

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Folder as FolderIcon,
  List as ListIcon,
  Search,
  SquareCheck,
  Clock,
  X,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { PriorityFlag, StatusDot } from "@/components/task/pickers";
import { useMembers, useStatusesByListIds, useWorkspaceTree } from "@/hooks/queries";
import { formatDueDate, initials, isOverdue, PRIORITY_META } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Highlight } from "@/components/search/highlight";
import {
  clearRecent,
  pushRecent,
  useRecentItems,
} from "@/components/search/recent-items";
import {
  buildTreeIndex,
  containerHref,
  joinPath,
  listHref,
  memberHref,
  taskHref,
  taskPath,
} from "@/components/search/tree-index";
import { filterMembers, groupResults, MIN_QUERY_LENGTH, useSearch } from "@/components/search/use-search";
import type { Member, Status, Task } from "@/types/api";

export function SearchResults({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlQuery = searchParams.get("q") ?? "";

  const [value, setValue] = React.useState(urlQuery);
  // URL bilan ikki tomonlama sinxron: tashqaridan (yuqori paneldan, orqaga
  // tugmasidan) kelgan o'zgarish maydonni yangilaydi, teskarisi emas.
  const syncedQuery = React.useRef(urlQuery);
  React.useEffect(() => {
    if (urlQuery !== syncedQuery.current) {
      syncedQuery.current = urlQuery;
      setValue(urlQuery);
    }
  }, [urlQuery]);

  const search = useSearch(workspaceId, value);
  const { debouncedQuery } = search;

  React.useEffect(() => {
    if (debouncedQuery === syncedQuery.current) return;
    syncedQuery.current = debouncedQuery;
    const next = debouncedQuery
      ? `/w/${workspaceId}/search?q=${encodeURIComponent(debouncedQuery)}`
      : `/w/${workspaceId}/search`;
    router.replace(next, { scroll: false });
  }, [debouncedQuery, router, workspaceId]);

  const { data: tree } = useWorkspaceTree(workspaceId);
  const index = React.useMemo(() => buildTreeIndex(tree), [tree]);
  const { data: membersPage } = useMembers(workspaceId);

  const groups = React.useMemo(() => groupResults(search.data?.results), [search.data]);
  const members = React.useMemo(
    () => filterMembers(membersPage?.results ?? [], debouncedQuery, 10),
    [membersPage, debouncedQuery],
  );

  const listIds = React.useMemo(
    () => Array.from(new Set(groups.tasks.map((task) => task.list_id))),
    [groups.tasks],
  );
  const { statusById } = useStatusesByListIds(listIds);

  const total = groups.total + members.length;
  const inputRef = React.useRef<HTMLInputElement>(null);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-3xl p-6 md:p-8">
        <h1 className="mb-4 text-lg font-semibold">Qidiruv</h1>

        <div className="relative mb-6">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            ref={inputRef}
            autoFocus
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Vazifa, ro'yxat, bo'lim yoki a'zoni qidiring…"
            aria-label="Ish maydoni bo'yicha qidirish"
            className="h-11 pr-24 pl-9 text-base"
          />
          <div className="absolute top-1/2 right-2 flex -translate-y-1/2 items-center gap-1.5">
            {search.isSyncing ? (
              <span
                aria-label="Qidirilmoqda"
                className="size-4 animate-spin rounded-full border-2 border-muted-foreground/25 border-t-muted-foreground"
              />
            ) : null}
            {value ? (
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label="Qidiruvni tozalash"
                onClick={() => {
                  setValue("");
                  inputRef.current?.focus();
                }}
              >
                <X />
              </Button>
            ) : null}
          </div>
        </div>

        {search.isTooShort ? (
          <ShortQueryState workspaceId={workspaceId} hasText={value.trim().length > 0} />
        ) : search.isError ? (
          <div className="rounded-lg border border-danger/30 bg-danger/5 p-4 text-sm">
            <p className="font-medium text-danger">Qidiruv amalga oshmadi.</p>
            <p className="mt-1 text-muted-foreground">
              Tarmoqni tekshirib, qayta urinib ko&apos;ring.
            </p>
            <Button variant="outline" size="sm" className="mt-3" onClick={search.refetch}>
              Qayta urinish
            </Button>
          </div>
        ) : search.isInitialLoading ? (
          <ResultsSkeleton />
        ) : total === 0 ? (
          <NoResultsState query={debouncedQuery} />
        ) : (
          <div className={cn("space-y-6", search.isStale && "opacity-60 transition-opacity")}>
            <p className="text-sm text-muted-foreground" aria-live="polite">
              «{debouncedQuery}» bo&apos;yicha {total} ta natija
            </p>

            <ResultGroup title="Vazifalar" count={groups.tasks.length}>
              {groups.tasks.map((task) => (
                <TaskResultRow
                  key={task.id}
                  workspaceId={workspaceId}
                  task={task}
                  status={statusById.get(task.status_id)}
                  path={taskPath(index, task.list_id)}
                  query={debouncedQuery}
                />
              ))}
            </ResultGroup>

            <ResultGroup title="Ro'yxatlar" count={groups.lists.length}>
              {groups.lists.map((list) => (
                <ResultRow
                  key={list.id}
                  href={listHref(workspaceId, list.id)}
                  icon={<ListIcon className="size-4 text-muted-foreground" />}
                  name={list.name}
                  path={joinPath(index.lists.get(list.id)?.path ?? [])}
                  query={debouncedQuery}
                  meta={
                    <span className="text-xs text-muted-foreground">
                      {list.open_task_count} ochiq / {list.task_count} vazifa
                    </span>
                  }
                  onOpen={() =>
                    pushRecent({
                      kind: "list",
                      id: list.id,
                      workspaceId,
                      title: list.name,
                      href: listHref(workspaceId, list.id),
                      path: joinPath(index.lists.get(list.id)?.path ?? []),
                    })
                  }
                />
              ))}
            </ResultGroup>

            <ResultGroup title="Jildlar" count={groups.folders.length}>
              {groups.folders.map((folder) => {
                const indexed = index.folders.get(folder.id);
                return (
                  <ResultRow
                    key={folder.id}
                    href={containerHref(workspaceId, indexed?.firstListId ?? null)}
                    icon={<FolderIcon className="size-4 text-muted-foreground" />}
                    name={folder.name}
                    path={joinPath(indexed?.path ?? [])}
                    query={debouncedQuery}
                  />
                );
              })}
            </ResultGroup>

            <ResultGroup title="Bo'limlar" count={groups.spaces.length}>
              {groups.spaces.map((space) => (
                <ResultRow
                  key={space.id}
                  href={containerHref(workspaceId, index.spaces.get(space.id)?.firstListId ?? null)}
                  icon={
                    <span
                      aria-hidden
                      className="size-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: space.color || "#7B68EE" }}
                    />
                  }
                  name={space.name}
                  path=""
                  query={debouncedQuery}
                />
              ))}
            </ResultGroup>

            <ResultGroup title="A'zolar" count={members.length}>
              {members.map((member) => (
                <MemberResultRow
                  key={member.user.id}
                  workspaceId={workspaceId}
                  member={member}
                  query={debouncedQuery}
                />
              ))}
            </ResultGroup>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Guruh va qatorlar
// ---------------------------------------------------------------------------

function ResultGroup({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  if (count === 0) return null;
  return (
    <section>
      <h2 className="mb-1.5 flex items-center gap-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {title}
        <Badge variant="secondary" className="h-4 px-1.5 text-[10px]">
          {count}
        </Badge>
      </h2>
      <ul className="divide-y rounded-lg border">{children}</ul>
    </section>
  );
}

const ROW_CLASS =
  "flex items-center gap-3 px-3 py-2.5 text-sm transition-colors hover:bg-muted/50";

function TaskResultRow({
  workspaceId,
  task,
  status,
  path,
  query,
}: {
  workspaceId: string;
  task: Task;
  status?: Status;
  path: string;
  query: string;
}) {
  const href = taskHref(workspaceId, task.list_id, task.id);
  const overdue = isOverdue(task.due_date, status?.type);

  return (
    <li>
      <Link
        href={href}
        className={ROW_CLASS}
        onClick={() =>
          pushRecent({ kind: "task", id: task.id, workspaceId, title: task.title, href, path })
        }
      >
        <SquareCheck className="size-4 shrink-0 text-muted-foreground" />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate">
            <Highlight text={task.title} query={query} />
          </span>
          {path ? (
            <span className="truncate text-xs text-muted-foreground">{path}</span>
          ) : null}
        </span>
        {task.priority !== "none" ? (
          <span
            className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground max-sm:hidden"
            title={PRIORITY_META[task.priority].label}
          >
            <PriorityFlag priority={task.priority} />
            {PRIORITY_META[task.priority].label}
          </span>
        ) : null}
        {status ? (
          <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
            <StatusDot status={status} />
            <span className="max-sm:hidden">{status.name}</span>
          </span>
        ) : null}
        <span
          className={cn(
            "w-20 shrink-0 text-right text-xs max-sm:hidden",
            overdue ? "font-medium text-danger" : "text-muted-foreground",
          )}
        >
          {task.due_date ? formatDueDate(task.due_date) : "—"}
        </span>
      </Link>
    </li>
  );
}

function ResultRow({
  href,
  icon,
  name,
  path,
  query,
  meta,
  onOpen,
}: {
  /** `null` — ochiladigan sahifa yo'q (masalan, ro'yxatsiz bo'lim). */
  href: string | null;
  icon: React.ReactNode;
  name: string;
  path: string;
  query: string;
  meta?: React.ReactNode;
  onOpen?: () => void;
}) {
  const body = (
    <>
      {icon}
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate">
          <Highlight text={name} query={query} />
        </span>
        {path ? <span className="truncate text-xs text-muted-foreground">{path}</span> : null}
      </span>
      {meta}
    </>
  );

  return (
    <li>
      {href ? (
        <Link href={href} className={ROW_CLASS} onClick={onOpen}>
          {body}
        </Link>
      ) : (
        <div className={cn(ROW_CLASS, "cursor-default")} title="Ichida ro'yxat yo'q">
          {body}
        </div>
      )}
    </li>
  );
}

function MemberResultRow({
  workspaceId,
  member,
  query,
}: {
  workspaceId: string;
  member: Member;
  query: string;
}) {
  return (
    <li>
      <Link href={memberHref(workspaceId, member.user.id)} className={ROW_CLASS}>
        <Avatar className="size-6 shrink-0">
          {member.user.avatar ? <AvatarImage src={member.user.avatar} alt="" /> : null}
          <AvatarFallback
            className="text-[10px] font-semibold text-primary-foreground"
            style={{ backgroundColor: member.user.avatar_color || "#7B68EE" }}
          >
            {initials(member.user.full_name, member.user.email ?? undefined)}
          </AvatarFallback>
        </Avatar>
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate">
            <Highlight text={member.user.full_name} query={query} />
          </span>
          {member.user.email ? (
            <span className="truncate text-xs text-muted-foreground">
              <Highlight text={member.user.email} query={query} />
            </span>
          ) : null}
        </span>
      </Link>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Holatlar
// ---------------------------------------------------------------------------

function ShortQueryState({
  workspaceId,
  hasText,
}: {
  workspaceId: string;
  hasText: boolean;
}) {
  const recent = useRecentItems(workspaceId);

  return (
    <div className="space-y-6">
      <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-10 text-center">
        <Search className="size-6 text-muted-foreground" />
        <p className="text-sm font-medium">
          {hasText
            ? `Kamida ${MIN_QUERY_LENGTH} belgi kiriting`
            : "Vazifa, ro'yxat, bo'lim yoki a'zoni qidiring"}
        </p>
        <p className="text-xs text-muted-foreground">
          Istalgan joydan <Kbd>Ctrl</Kbd> + <Kbd>K</Kbd> bilan tezkor qidiruvni oching.
        </p>
      </div>

      {recent.length > 0 ? (
        <section>
          <h2 className="mb-1.5 flex items-center text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Yaqinda ochilganlar
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto h-6 text-xs font-normal"
              onClick={() => clearRecent(workspaceId)}
            >
              Tozalash
            </Button>
          </h2>
          <ul className="divide-y rounded-lg border">
            {recent.map((item) => (
              <li key={`${item.kind}-${item.id}`}>
                <Link href={item.href} className={ROW_CLASS}>
                  <Clock className="size-4 shrink-0 text-muted-foreground" />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate">{item.title}</span>
                    {item.path ? (
                      <span className="truncate text-xs text-muted-foreground">{item.path}</span>
                    ) : null}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function NoResultsState({ query }: { query: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-10 text-center">
      <Search className="size-6 text-muted-foreground" />
      <p className="text-sm font-medium">
        «{query}» bo&apos;yicha hech narsa topilmadi
      </p>
      <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
        <li>Imloni tekshiring.</li>
        <li>Qisqaroq yoki boshqa so&apos;z bilan urinib ko&apos;ring.</li>
        <li>Arxivlangan va o&apos;chirilgan yozuvlar qidiruvga tushmaydi.</li>
      </ul>
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div className="space-y-2 rounded-lg border p-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 py-1.5">
          <Skeleton className="size-4 shrink-0 rounded-full" />
          <Skeleton className="h-3 w-1/2" />
          <Skeleton className="ml-auto h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex h-4 min-w-4 items-center justify-center rounded border bg-muted px-1 font-sans text-[10px] leading-none">
      {children}
    </kbd>
  );
}
