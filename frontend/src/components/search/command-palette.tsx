"use client";

/**
 * S12 — global buyruqlar paneli (`Ctrl+K` / `Cmd+K`).
 *
 * Global `keydown` tinglovchisi shu komponentning o'zida: panel ilova
 * qobig'ining ichida bir marta mount qilinadi va boshqa hech kim klaviatura
 * hodisasiga obuna bo'lmaydi. Panel ochilganda hech qanday so'rov ketmaydi —
 * daraxt va a'zolar allaqachon keshda, faqat matn kiritilgandan keyingina
 * `workspaces/{id}/search/` chaqiriladi (250 ms debounce bilan).
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Clock,
  CornerDownLeft,
  Folder as FolderIcon,
  List as ListIcon,
  Search,
  SquareCheck,
  Users,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusDot, PriorityFlag } from "@/components/task/pickers";
import { useMembers, useStatusesByListIds, useWorkspaceTree } from "@/hooks/queries";
import { initials, PRIORITY_META } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Highlight } from "@/components/search/highlight";
import { pushRecent, useRecentItems, type RecentItem } from "@/components/search/recent-items";
import {
  buildTreeIndex,
  containerHref,
  joinPath,
  listHref,
  memberHref,
  taskHref,
  taskPath,
} from "@/components/search/tree-index";
import { filterMembers, groupResults, useSearch } from "@/components/search/use-search";

export function CommandPalette({ workspaceId }: { workspaceId: string }) {
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey)) return;
      if (event.key.toLowerCase() !== "k") return;
      // IME kompozitsiyasi o'rtasida (masalan, kirill/xitoy kiritish) panelni
      // ochib yubormaymiz — bu foydalanuvchining yozayotganini buzadi.
      if (event.isComposing) return;
      event.preventDefault();
      setOpen((value) => !value);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        showCloseButton={false}
        className="top-[12vh] w-full max-w-[calc(100%-2rem)] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-2xl"
      >
        <DialogTitle className="sr-only">Tezkor qidiruv</DialogTitle>
        <DialogDescription className="sr-only">
          Vazifa, ro&apos;yxat, bo&apos;lim yoki a&apos;zoni qidiring. Yurish uchun yuqori/quyi
          o&apos;q, ochish uchun Enter, yopish uchun Esc.
        </DialogDescription>
        {/* Faqat panel ochiq bo'lganda mount bo'ladi: shu sababli qidiruv
            holati har safar toza boshlanadi va fokus effekti ishlaydi. */}
        {open ? <PaletteBody workspaceId={workspaceId} onClose={() => setOpen(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function PaletteBody({
  workspaceId,
  onClose,
}: {
  workspaceId: string;
  onClose: () => void;
}) {
  const router = useRouter();
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [query, setQuery] = React.useState("");

  const { data: tree } = useWorkspaceTree(workspaceId);
  const index = React.useMemo(() => buildTreeIndex(tree), [tree]);
  const { data: membersPage } = useMembers(workspaceId);

  const search = useSearch(workspaceId, query);
  const groups = React.useMemo(() => groupResults(search.data?.results), [search.data]);
  // A'zolar klientda filtrlanadi, lekin ular ham ekrandagi natijalar bilan
  // bitta so'rovga tegishli bo'lishi kerak — shuning uchun `resultQuery`.
  const members = React.useMemo(
    () => filterMembers(membersPage?.results ?? [], search.resultQuery),
    [membersPage, search.resultQuery],
  );

  const listIds = React.useMemo(
    () => Array.from(new Set(groups.tasks.map((task) => task.list_id))),
    [groups.tasks],
  );
  const { statusById } = useStatusesByListIds(listIds);

  const recent = useRecentItems(workspaceId);

  React.useEffect(() => {
    // Base UI dialog fokusni popup'ga oladi; keyingi kadrda inputga qaytaramiz.
    const frame = window.requestAnimationFrame(() => inputRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const go = React.useCallback(
    (href: string, remember?: Omit<RecentItem, "at">) => {
      if (remember) pushRecent(remember);
      onClose();
      router.push(href);
    },
    [onClose, router],
  );

  const trimmed = query.trim();
  const hasQuery = trimmed.length > 0;
  const showRecent = !hasQuery && recent.length > 0;
  const resultCount =
    groups.tasks.length +
    groups.lists.length +
    groups.folders.length +
    groups.spaces.length +
    members.length;
  // `!isError`: xato bo'lganda yuqorida "Qidiruv amalga oshmadi" chiqadi —
  // uning ostiga yana "hech narsa topilmadi" qo'shish yolg'on bo'lardi.
  const showEmpty =
    !search.isTooShort && !search.isInitialLoading && !search.isError && resultCount === 0;

  return (
    <Command
      shouldFilter={false}
      loop
      // Ctrl+K panelni yopadi (global tinglovchi) — cmdk'ning vim
      // qisqartmalari o'sha paytda tanlovni ham surib yuborardi.
      vimBindings={false}
      // cmdk o'zi filtrlamaydi — filtrlash serverda; bu yerda faqat tanlov
      // va klaviatura navigatsiyasi kerak.
      className="bg-transparent"
      label="Tezkor qidiruv"
    >
      <CommandInput
        ref={inputRef}
        value={query}
        onValueChange={setQuery}
        placeholder="Vazifa, ro'yxat, bo'lim yoki a'zoni qidiring…"
      />

      <CommandList className="max-h-[min(60vh,26rem)] px-1 pb-1">
        {/* --- qisqa so'rov --- */}
        {hasQuery && search.isTooShort ? (
          <PaletteHint icon={<Search className="size-4" />} title="Kamida 2 belgi kiriting">
            Qidiruv 2 ta belgidan boshlab ishlaydi.
          </PaletteHint>
        ) : null}

        {/* --- bo'sh so'rov: yaqinda ochilganlar --- */}
        {!hasQuery && !showRecent ? (
          <PaletteHint icon={<Search className="size-4" />} title="Nimani qidiramiz?">
            Vazifalar, ro&apos;yxatlar, bo&apos;limlar va a&apos;zolar bo&apos;yicha qidiring.
          </PaletteHint>
        ) : null}

        {showRecent ? (
          <CommandGroup heading="Yaqinda ochilganlar">
            {recent.map((item) => (
              <CommandItem
                key={`recent-${item.kind}-${item.id}`}
                value={`recent-${item.kind}-${item.id}`}
                onSelect={() => go(item.href, item)}
              >
                <Clock className="size-4 text-muted-foreground" />
                <span className="truncate">{item.title}</span>
                {item.path ? (
                  <span className="ml-auto truncate pl-3 text-xs text-muted-foreground">
                    {item.path}
                  </span>
                ) : null}
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}

        {/* --- yuklanmoqda --- */}
        {!search.isTooShort && search.isInitialLoading ? (
          <div className="space-y-1 p-1" aria-hidden>
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex items-center gap-2 px-2 py-1.5">
                <Skeleton className="size-4 shrink-0 rounded-full" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            ))}
          </div>
        ) : null}

        {search.isError ? (
          <div className="px-3 py-6 text-center text-sm text-danger">
            Qidiruv amalga oshmadi.{" "}
            <button type="button" className="underline" onClick={() => search.refetch()}>
              Qayta urinish
            </button>
          </div>
        ) : null}

        <div className={cn(search.isStale && "opacity-60 transition-opacity")}>
          {groups.tasks.length > 0 ? (
            <CommandGroup heading="Vazifalar">
              {groups.tasks.map((task) => {
                const status = statusById.get(task.status_id);
                const path = taskPath(index, task.list_id);
                return (
                  <CommandItem
                    key={`task-${task.id}`}
                    value={`task-${task.id}`}
                    onSelect={() =>
                      go(taskHref(workspaceId, task.list_id, task.id), {
                        kind: "task",
                        id: task.id,
                        workspaceId,
                        title: task.title,
                        href: taskHref(workspaceId, task.list_id, task.id),
                        path,
                      })
                    }
                  >
                    <SquareCheck className="size-4 text-muted-foreground" />
                    <span className="truncate">
                      <Highlight text={task.title} query={search.resultQuery} />
                    </span>
                    {task.priority !== "none" ? (
                      <span className="shrink-0" title={PRIORITY_META[task.priority].label}>
                        <PriorityFlag priority={task.priority} />
                      </span>
                    ) : null}
                    <span className="ml-auto flex shrink-0 items-center gap-2 pl-3 text-xs text-muted-foreground">
                      {status ? (
                        <span className="flex items-center gap-1">
                          <StatusDot status={status} />
                          <span className="max-sm:hidden">{status.name}</span>
                        </span>
                      ) : null}
                      {path ? <span className="max-w-48 truncate max-sm:hidden">{path}</span> : null}
                    </span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          ) : null}

          {groups.lists.length > 0 ? (
            <CommandGroup heading="Ro'yxatlar">
              {groups.lists.map((list) => {
                const path = joinPath(index.lists.get(list.id)?.path ?? []);
                return (
                  <CommandItem
                    key={`list-${list.id}`}
                    value={`list-${list.id}`}
                    onSelect={() =>
                      go(listHref(workspaceId, list.id), {
                        kind: "list",
                        id: list.id,
                        workspaceId,
                        title: list.name,
                        href: listHref(workspaceId, list.id),
                        path,
                      })
                    }
                  >
                    <ListIcon className="size-4 text-muted-foreground" />
                    <span className="truncate">
                      <Highlight text={list.name} query={search.resultQuery} />
                    </span>
                    <span className="ml-auto truncate pl-3 text-xs text-muted-foreground">
                      {path}
                    </span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          ) : null}

          {groups.spaces.length > 0 || groups.folders.length > 0 ? (
            <CommandGroup heading="Bo'limlar va jildlar">
              {groups.spaces.map((space) => {
                const href = containerHref(
                  workspaceId,
                  index.spaces.get(space.id)?.firstListId ?? null,
                );
                return (
                  <CommandItem
                    key={`space-${space.id}`}
                    value={`space-${space.id}`}
                    disabled={!href}
                    onSelect={() => href && go(href)}
                  >
                    <span
                      aria-hidden
                      className="size-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: space.color || "#7B68EE" }}
                    />
                    <span className="truncate">
                      <Highlight text={space.name} query={search.resultQuery} />
                    </span>
                    <span className="ml-auto shrink-0 pl-3 text-xs text-muted-foreground">
                      {href ? "Bo'lim" : "Bo'lim — ro'yxat yo'q"}
                    </span>
                  </CommandItem>
                );
              })}
              {groups.folders.map((folder) => {
                const indexed = index.folders.get(folder.id);
                const href = containerHref(workspaceId, indexed?.firstListId ?? null);
                return (
                  <CommandItem
                    key={`folder-${folder.id}`}
                    value={`folder-${folder.id}`}
                    disabled={!href}
                    onSelect={() => href && go(href)}
                  >
                    <FolderIcon className="size-4 text-muted-foreground" />
                    <span className="truncate">
                      <Highlight text={folder.name} query={search.resultQuery} />
                    </span>
                    <span className="ml-auto truncate pl-3 text-xs text-muted-foreground">
                      {joinPath(indexed?.path ?? []) || "Jild"}
                    </span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          ) : null}

          {members.length > 0 ? (
            <CommandGroup heading="A'zolar">
              {members.map((member) => (
                <CommandItem
                  key={`member-${member.user.id}`}
                  value={`member-${member.user.id}`}
                  onSelect={() => go(memberHref(workspaceId, member.user.id))}
                >
                  <Avatar className="size-5">
                    {member.user.avatar ? <AvatarImage src={member.user.avatar} alt="" /> : null}
                    <AvatarFallback
                      className="text-[9px] font-semibold text-primary-foreground"
                      style={{ backgroundColor: member.user.avatar_color || "#7B68EE" }}
                    >
                      {initials(member.user.full_name, member.user.email ?? undefined)}
                    </AvatarFallback>
                  </Avatar>
                  <span className="truncate">
                    <Highlight text={member.user.full_name} query={search.resultQuery} />
                  </span>
                  {/* Mehmonga email `null` keladi (§4) — ustunni bo'sh qoldiramiz. */}
                  {member.user.email ? (
                    <span className="ml-auto truncate pl-3 text-xs text-muted-foreground">
                      <Highlight text={member.user.email} query={search.resultQuery} />
                    </span>
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}
        </div>

        {showEmpty ? (
          <PaletteHint
            icon={<Search className="size-4" />}
            title={`«${search.resultQuery}» bo'yicha hech narsa topilmadi`}
          >
            Imloni tekshiring yoki qisqaroq so&apos;z bilan urinib ko&apos;ring.
          </PaletteHint>
        ) : null}

        {/* Natija bo'lmaganda bu qatorni ham chiqarmaymiz: aks holda cmdk
            tanlovni o'sha yagona elementga qo'yib qo'yadi va keyin kelgan
            birinchi vazifa o'rniga shu qator tanlangan bo'lib qolardi. */}
        {!search.isTooShort && resultCount > 0 ? (
          <>
            {/* `alwaysRender`: cmdk ajratgichni matn kiritilganda yashiradi. */}
            <CommandSeparator alwaysRender className="my-1" />
            <CommandGroup>
              {/* Bu qator — natijalarning tavsifi emas, harakat: u foydalanuvchi
                  yozgan so'rov bilan to'liq qidiruv sahifasini ochadi. Shuning
                  uchun bu yerda ataylab `debouncedQuery`, `resultQuery` emas —
                  havola ham, yozuv ham bir xil matnni ko'rsatadi. */}
              <CommandItem
                value="see-all-results"
                onSelect={() =>
                  go(`/w/${workspaceId}/search?q=${encodeURIComponent(search.debouncedQuery)}`)
                }
              >
                <ArrowRight className="size-4 text-muted-foreground" />
                <span className="truncate">
                  «{search.debouncedQuery}» bo&apos;yicha barcha natijalar
                </span>
              </CommandItem>
            </CommandGroup>
          </>
        ) : null}
      </CommandList>

      <PaletteFooter isSyncing={search.isSyncing} />
    </Command>
  );
}

function PaletteHint({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-1.5 px-4 py-10 text-center">
      <span className="text-muted-foreground">{icon}</span>
      <p className="text-sm font-medium">{title}</p>
      <p className="text-xs text-muted-foreground">{children}</p>
    </div>
  );
}

function PaletteFooter({ isSyncing }: { isSyncing: boolean }) {
  return (
    <div className="flex items-center gap-3 border-t px-3 py-1.5 text-[11px] text-muted-foreground">
      <span className="flex items-center gap-1">
        <Kbd>↑</Kbd>
        <Kbd>↓</Kbd> tanlash
      </span>
      <span className="flex items-center gap-1">
        <Kbd>
          <CornerDownLeft className="size-2.5" />
        </Kbd>{" "}
        ochish
      </span>
      <span className="flex items-center gap-1">
        <Kbd>esc</Kbd> yopish
      </span>
      <span className="ml-auto flex items-center gap-1">
        {isSyncing ? (
          <>
            <span
              aria-hidden
              className="size-3 animate-spin rounded-full border-[1.5px] border-muted-foreground/30 border-t-muted-foreground"
            />
            Qidirilmoqda…
          </>
        ) : (
          <>
            <Users className="size-3" />
            Ish maydoni bo&apos;yicha
          </>
        )}
      </span>
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
