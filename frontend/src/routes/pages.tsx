/**
 * Marshrut sahifalari — Next'ning `page.tsx` fayllarining aynan ekvivalenti.
 *
 * Har biri o'sha faylda nima bo'lsa shuni qiladi: URL segmentini o'qib
 * komponentga uzatadi. Yagona farq — `params` endi `Promise` emas (Next 16'da
 * shunday edi), React Router uni oddiy satr sifatida beradi, ya'ni `async` va
 * `await` qobiqlari kerak emas.
 */

import { Suspense } from "react";
import { useParams } from "react-router";
import { HomeRedirect } from "@/components/auth/home-redirect";
import { InviteView } from "@/components/auth/invite-view";
import { LoginForm, RegisterForm } from "@/components/auth/auth-form";
import { Landing } from "@/components/marketing/landing";
import { ListPage } from "@/components/list/list-page";
import { SearchResults } from "@/components/search/search-results";
import { PermissionsMatrix } from "@/components/settings/permissions-matrix";
import { ProfileSettings } from "@/components/settings/profile-settings";
import {
  GeneralSection,
  InvitationsSection,
  MembersSection,
} from "@/components/settings/workspace-settings";
import { Button } from "@/components/ui/button";
import { Link } from "@/components/ui/link";
import { FullPageSpinner } from "@/components/shared/full-page-spinner";
import { AiAssistant } from "@/components/shell/ai-assistant";
import { ChatView } from "@/components/chat/chat-view";
import { DashboardView } from "@/components/shell/dashboard-view";
import { NotificationsPage } from "@/components/shell/notifications-page";
import { PlannerView } from "@/components/shell/planner-view";
import { WorkspaceHome } from "@/components/shell/workspace-home";
import { MemberProfile } from "@/components/workspace/member-profile";
import { SpaceMembersPanel } from "@/components/workspace/space-members-panel";
import { APP, AUTH, COMMON, INVITE } from "@/i18n/uz";
import { usePageTitle } from "@/hooks/use-page-title";

/** `/w/:workspaceId/...` ostidagi har bir sahifa uchun umumiy o'qish. */
function useWorkspaceId(): string {
  const { workspaceId = "" } = useParams<{ workspaceId: string }>();
  return workspaceId;
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

/**
 * `<Landing />` `children` sifatida uzatiladi — faqat `HomeRedirect`
 * (auth/redirect mantiqi) marketing daraxtini import qilmasin degani.
 */
export function HomePage() {
  return (
    <HomeRedirect>
      <Landing />
    </HomeRedirect>
  );
}

export function LoginPage() {
  usePageTitle(APP.pageTitle(COMMON.login));
  return (
    <div className="w-full max-w-[400px] rounded-xl border bg-background p-10 shadow-lg">
      <h1 className="text-xl font-semibold">{COMMON.login}</h1>
      <p className="mb-6 text-sm text-muted-foreground">{AUTH.loginWelcome}</p>
      <LoginForm />
    </div>
  );
}

export function RegisterPage() {
  usePageTitle(APP.pageTitle(COMMON.register));
  return (
    <div className="w-full max-w-[400px] rounded-xl border bg-background p-10 shadow-lg">
      <h1 className="text-xl font-semibold">{AUTH.registerTitle}</h1>
      <p className="mb-6 text-sm text-muted-foreground">{AUTH.registerSubtitle}</p>
      <RegisterForm />
    </div>
  );
}

export function InvitePage() {
  usePageTitle(APP.pageTitle(INVITE.pageTitle), { noIndex: true });
  const { token = "" } = useParams<{ token: string }>();
  return <InviteView token={token} />;
}

/**
 * `/invite/:token` sahifasi yuklangach tokenni manzil qatoridan olib tashlaydi
 * (§F-6 MUST-5), shuning uchun sahifa yangilansa foydalanuvchi shu yerga
 * tushadi. Bu ekran hech qanday taklif ma'lumotini oshkor qilmaydi.
 */
export function InviteFallbackPage() {
  usePageTitle(APP.pageTitle(INVITE.pageTitle), { noIndex: true });
  return (
    <div className="flex flex-col gap-4 text-center">
      <h1 className="text-lg font-semibold">{INVITE.fallbackTitle}</h1>
      <p className="text-sm text-muted-foreground">{INVITE.fallbackHint}</p>
      <div className="flex justify-center gap-2">
        <Button variant="outline" render={<Link href="/register" />}>
          {COMMON.register}
        </Button>
        <Button render={<Link href="/login" />}>{COMMON.login}</Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export function ProfilePage() {
  return <ProfileSettings />;
}

export function WorkspaceHomePage() {
  return <WorkspaceHome workspaceId={useWorkspaceId()} />;
}

export function DashboardPage() {
  return <DashboardView workspaceId={useWorkspaceId()} />;
}

export function ChatPage() {
  return <ChatView workspaceId={useWorkspaceId()} />;
}

export function AiPage() {
  return <AiAssistant workspaceId={useWorkspaceId()} />;
}

export function NotificationsRoute() {
  return <NotificationsPage workspaceId={useWorkspaceId()} />;
}

export function PlannerPage() {
  return <PlannerView workspaceId={useWorkspaceId()} />;
}

export function SearchPage() {
  const workspaceId = useWorkspaceId();
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <SearchResults workspaceId={workspaceId} />
    </Suspense>
  );
}

export function ListRoute() {
  const workspaceId = useWorkspaceId();
  const { listId = "" } = useParams<{ listId: string }>();
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <ListPage workspaceId={workspaceId} listId={listId} />
    </Suspense>
  );
}

export function SpaceMembersPage() {
  const workspaceId = useWorkspaceId();
  const { spaceId = "" } = useParams<{ spaceId: string }>();
  return <SpaceMembersPanel workspaceId={workspaceId} spaceId={spaceId} />;
}

export function MemberProfilePage() {
  const workspaceId = useWorkspaceId();
  const { userId = "" } = useParams<{ userId: string }>();
  return <MemberProfile workspaceId={workspaceId} userId={userId} />;
}

export function SettingsGeneralPage() {
  return <GeneralSection workspaceId={useWorkspaceId()} />;
}

export function SettingsMembersPage() {
  return <MembersSection workspaceId={useWorkspaceId()} />;
}

export function SettingsInvitationsPage() {
  return <InvitationsSection workspaceId={useWorkspaceId()} />;
}

export function SettingsPermissionsPage() {
  return <PermissionsMatrix workspaceId={useWorkspaceId()} />;
}
