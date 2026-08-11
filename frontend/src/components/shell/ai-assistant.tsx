import * as React from "react";
import { CornerDownLeft, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { TaskRow } from "@/components/shared/task-row";
import {
  useMe,
  useMembers,
  useMyPermissions,
  useMyTasks,
  useWorkspaceTree,
  useWorkspaceTasks,
} from "@/hooks/queries";
import { AI_ASSISTANT, COMMON } from "@/i18n/uz";
import { can } from "@/lib/permissions";
import { byDueDate, groupByDue } from "@/lib/task-buckets";
import { cn } from "@/lib/utils";
import type { Member, Task, WorkspaceTree } from "@/types/api";

/**
 * «AI yordamchi» — ish maydoni ma'lumotlari ustidagi savol-javob.
 *
 * MUHIM va ataylab: bu yerda TASHQI MODEL CHAQIRILMAYDI. Javoblar
 * brauzerdagi keshdan (vazifalar, daraxt, a'zolar) hisoblanadi, ya'ni ular
 * har doim aynan REST qaytargan ma'lumotga teng, hech narsa "o'ylab
 * topilmaydi" va hech qanday ish maydoni ma'lumoti tashqariga chiqmaydi.
 * Interfeys suhbat shaklida, chunki savol berish menyu qidirishdan tez;
 * lekin javob deterministik va manbasi ko'rsatilgan.
 */
interface Answer {
  text: string;
  detail?: string;
  tasks?: Task[];
}

interface Intent {
  key: string;
  /** Chipdagi matn — bosilganda aynan shu savol yoziladi. */
  prompt: string;
  /** Erkin matnni shu niyatga bog'laydigan kalit so'zlar. */
  keywords: string[];
}

const INTENTS: Intent[] = [
  {
    key: "mine",
    prompt: AI_ASSISTANT.promptMine,
    keywords: ["menga", "mening", "biriktir", "vazifalarim"],
  },
  {
    key: "overdue",
    prompt: AI_ASSISTANT.promptOverdue,
    keywords: ["muddat", "kechik", "o'tgan", "otgan", "overdue"],
  },
  {
    key: "today",
    prompt: AI_ASSISTANT.promptToday,
    keywords: ["bugun", "bugungi", "kunlik"],
  },
  {
    key: "team",
    prompt: AI_ASSISTANT.promptTeam,
    keywords: ["kim", "jamoa", "yuklama", "band"],
  },
  {
    key: "spaces",
    prompt: AI_ASSISTANT.promptSpaces,
    keywords: ["bo'lim", "bolim", "loyiha", "space"],
  },
];

function listNamesOf(tree: WorkspaceTree | undefined): Map<string, string> {
  const names = new Map<string, string>();
  for (const space of tree?.spaces ?? []) {
    for (const list of [...space.lists, ...space.folders.flatMap((f) => f.lists)]) {
      names.set(list.id, list.name);
    }
  }
  return names;
}

function pluralTasks(count: number): string {
  return AI_ASSISTANT.taskCount(count);
}

export function AiAssistant({ workspaceId }: { workspaceId: string }) {
  const { data: me } = useMe();
  const { data: myPermissions } = useMyPermissions(workspaceId);
  const canReadTasks = can(myPermissions, "task.read");
  const canReadMembers = can(myPermissions, "member.read");

  const myTasks = useMyTasks(workspaceId);
  const teamTasks = useWorkspaceTasks(workspaceId, canReadTasks);
  const members = useMembers(workspaceId);
  const { data: tree } = useWorkspaceTree(workspaceId);

  const [input, setInput] = React.useState("");
  const [answer, setAnswer] = React.useState<Answer | null>(null);
  const [asked, setAsked] = React.useState<string | null>(null);

  const openMine = React.useMemo(
    () => (myTasks.data?.results ?? []).filter((t) => !t.completed_at),
    [myTasks.data],
  );
  const openTeam = React.useMemo(
    () => (teamTasks.data?.results ?? []).filter((t) => !t.completed_at),
    [teamTasks.data],
  );
  const listNames = React.useMemo(() => listNamesOf(tree), [tree]);


  const pending = myTasks.isPending || (canReadTasks && teamTasks.isPending);

  const answerFor = React.useCallback(
    (question: string): Answer => {
      const normalized = question.trim().toLowerCase();
      const intent = INTENTS.find((i) =>
        i.keywords.some((keyword) => normalized.includes(keyword)),
      );
      const now = new Date();
      const buckets = groupByDue(openMine);
      const scope = canReadTasks ? openTeam : openMine;

      switch (intent?.key) {
        case "mine": {
          const sorted = [...openMine].sort(byDueDate);
          return {
            text:
              sorted.length === 0
                ? AI_ASSISTANT.mineEmpty
                : AI_ASSISTANT.mineText(pluralTasks(sorted.length)),
            detail:
              buckets.overdue.length > 0
                ? AI_ASSISTANT.mineOverdueDetail(buckets.overdue.length)
                : undefined,
            tasks: sorted.slice(0, 8),
          };
        }
        case "overdue": {
          const overdue = scope
            .filter((t) => t.due_date && new Date(t.due_date) < now)
            .sort(byDueDate);
          return {
            text:
              overdue.length === 0
                ? AI_ASSISTANT.overdueEmpty
                : AI_ASSISTANT.overdueText(pluralTasks(overdue.length)),
            detail: canReadTasks
              ? AI_ASSISTANT.overdueScopeAll
              : AI_ASSISTANT.overdueScopeMine,
            tasks: overdue.slice(0, 8),
          };
        }
        case "today": {
          const today = [...buckets.today, ...buckets.overdue].sort(byDueDate);
          return {
            text:
              today.length === 0
                ? AI_ASSISTANT.todayEmpty
                : AI_ASSISTANT.todayText(pluralTasks(today.length)),
            tasks: today.slice(0, 8),
          };
        }
        case "team": {
          if (!canReadTasks || !canReadMembers) {
            return {
              text: AI_ASSISTANT.teamDenied,
            };
          }
          const counts = new Map<string, number>();
          let unassigned = 0;
          for (const task of openTeam) {
            if (task.assignees.length === 0) unassigned += 1;
            for (const assignee of task.assignees) {
              counts.set(assignee.id, (counts.get(assignee.id) ?? 0) + 1);
            }
          }
          const roster: Member[] = members.data?.results ?? [];
          const lines = roster
            .map((m) => ({
              name: m.user.full_name || m.user.email || COMMON.someone,
              count: counts.get(m.user.id) ?? 0,
            }))
            .sort((a, b) => b.count - a.count)
            .slice(0, 8)
            .map((row) => AI_ASSISTANT.teamLine(row.name, row.count));
          if (unassigned > 0) lines.push(AI_ASSISTANT.teamUnassignedLine(unassigned));
          return {
            text:
              lines.length === 0
                ? AI_ASSISTANT.teamEmpty
                : AI_ASSISTANT.teamText,
            detail: lines.join("\n"),
          };
        }
        case "spaces": {
          const lines = (tree?.spaces ?? [])
            .map((space) => {
              const open = [
                ...space.lists,
                ...space.folders.flatMap((f) => f.lists),
              ].reduce((sum, list) => sum + list.open_task_count, 0);
              return AI_ASSISTANT.spaceLine(space.name, open);
            })
            .slice(0, 12);
          return {
            text:
              lines.length === 0
                ? AI_ASSISTANT.spacesEmpty
                : AI_ASSISTANT.spacesText,
            detail: lines.join("\n"),
          };
        }
        default: {
          // Niyat topilmadi — savolni kalit so'z sifatida o'qib, ko'rinadigan
          // vazifalar sarlavhasidan qidiramiz. Bu "javob o'ylab topish"dan
          // ko'ra halolroq: nima topilgani aniq ko'rinadi.
          const needle = normalized;
          if (needle.length < 2) {
            return { text: AI_ASSISTANT.tooShort };
          }
          const found = scope
            .filter((t) => t.title.toLowerCase().includes(needle))
            .sort(byDueDate);
          return {
            text:
              found.length === 0
                ? AI_ASSISTANT.searchEmpty(question.trim())
                : AI_ASSISTANT.searchText(question.trim(), pluralTasks(found.length)),
            tasks: found.slice(0, 8),
          };
        }
      }
    },
    [canReadMembers, canReadTasks, members.data, openMine, openTeam, tree],
  );

  const ask = (question: string) => {
    const trimmed = question.trim();
    if (!trimmed) return;
    setAsked(trimmed);
    setAnswer(answerFor(trimmed));
    setInput("");
  };

  const firstName = (me?.full_name || me?.email || "").split(/[\s@]/)[0];

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-3xl space-y-5 p-6 lg:p-8">
        <header>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Sparkles className="size-5 text-primary" />
            {AI_ASSISTANT.title}
          </h1>
          <p className="text-sm text-muted-foreground">{AI_ASSISTANT.description}</p>
        </header>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
          className="flex gap-2"
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              firstName
                ? AI_ASSISTANT.inputPlaceholder(firstName)
                : AI_ASSISTANT.inputPlaceholderAnon
            }
            aria-label={AI_ASSISTANT.inputAria}
          />
          <Button type="submit" disabled={!input.trim()} className="gap-1.5">
            <CornerDownLeft className="size-4" />
            {AI_ASSISTANT.submit}
          </Button>
        </form>

        <div className="flex flex-wrap gap-2">
          {INTENTS.map((intent) => (
            <button
              key={intent.key}
              type="button"
              onClick={() => ask(intent.prompt)}
              className="rounded-full border px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
            >
              {intent.prompt}
            </button>
          ))}
        </div>

        {pending ? (
          <div className="space-y-2" aria-hidden>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-11 w-full" />
          </div>
        ) : answer ? (
          <section className="space-y-3" aria-live="polite">
            {asked ? (
              <p className="text-sm font-medium text-muted-foreground">
                Savol: <span className="text-foreground">{asked}</span>
              </p>
            ) : null}
            <div className="rounded-lg border bg-card p-4">
              <p className="text-sm">{answer.text}</p>
              {answer.detail ? (
                <p
                  className={cn(
                    "mt-2 text-sm whitespace-pre-line text-muted-foreground",
                  )}
                >
                  {answer.detail}
                </p>
              ) : null}
            </div>
            {answer.tasks && answer.tasks.length > 0 ? (
              <div className="overflow-hidden rounded-lg border">
                {answer.tasks.map((task) => (
                  <TaskRow
                    key={task.id}
                    workspaceId={workspaceId}
                    task={task}
                    listName={listNames.get(task.list_id)}
                    overdue={!!task.due_date && new Date(task.due_date) < new Date()}
                  />
                ))}
              </div>
            ) : null}
          </section>
        ) : (
          <div className="rounded-lg border border-dashed p-10 text-center">
            <Sparkles className="mx-auto size-6 text-muted-foreground" />
            <p className="mt-2 text-sm font-medium">{AI_ASSISTANT.idleTitle}</p>
            <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
              {AI_ASSISTANT.idleHint}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
