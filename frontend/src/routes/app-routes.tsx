/**
 * Marshrut jadvali (ADR 0011).
 *
 * DIQQAT: bu yerdagi yigirmata manzil Next'ning `src/app/**` fayl daraxti
 * bilan **bir xil** — E2E testlari, emaildagi taklif havolalari va tashqi
 * havolalar shularga bog'langan. Yangi marshrut qo'shsa bo'ladi, mavjudini
 * qayta nomlash — buzuvchi o'zgarish.
 *
 * Guruh layoutlari (`(app)`, `(auth)`, `invite`) — yo'lsiz (`path`siz)
 * ichma-ich marshrutlar: URL'ga hech narsa qo'shmaydi, faqat `<Outlet />`
 * atrofini o'raydi. Next'dagi qavsli papkalarning aynan ekvivalenti.
 *
 * `createBrowserRouter` (`<Routes>` emas) — kelajakda loader/`errorElement`
 * kerak bo'lsa jadval shaklini o'zgartirmasdan qo'shish uchun.
 */

import { createBrowserRouter, type RouteObject } from "react-router";
import {
  AppAreaLayout,
  AuthLayout,
  InviteLayout,
  WorkspaceLayout,
  WorkspaceSettingsLayout,
} from "@/routes/layouts";
import { NotFound } from "@/routes/not-found";
import {
  AiPage,
  ChatPage,
  DashboardPage,
  HomePage,
  InviteFallbackPage,
  InvitePage,
  ListRoute,
  LoginPage,
  MemberProfilePage,
  NotificationsRoute,
  PlannerPage,
  ProfilePage,
  RegisterPage,
  SearchPage,
  SettingsGeneralPage,
  SettingsInvitationsPage,
  SettingsMembersPage,
  SettingsPermissionsPage,
  SpaceMembersPage,
  WorkspaceHomePage,
} from "@/routes/pages";

/**
 * Marshrut jadvali alohida eksport qilinadi: `src/routes/app-routes.test.ts`
 * uni `matchRoutes` bilan tekshiradi va yigirmata manzilning birortasi
 * o'zgarib ketmasligini kafolatlaydi.
 */
export const routes: RouteObject[] = [
  { path: "/", element: <HomePage /> },

  {
    element: <AuthLayout />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
    ],
  },

  {
    path: "/invite",
    element: <InviteLayout />,
    children: [
      { index: true, element: <InviteFallbackPage /> },
      { path: ":token", element: <InvitePage /> },
    ],
  },

  {
    element: <AppAreaLayout />,
    children: [
      { path: "/settings/profile", element: <ProfilePage /> },
      {
        path: "/w/:workspaceId",
        element: <WorkspaceLayout />,
        children: [
          { index: true, element: <WorkspaceHomePage /> },
          { path: "dashboard", element: <DashboardPage /> },
          { path: "chat", element: <ChatPage /> },
          { path: "ai", element: <AiPage /> },
          { path: "notifications", element: <NotificationsRoute /> },
          { path: "planner", element: <PlannerPage /> },
          { path: "search", element: <SearchPage /> },
          { path: "l/:listId", element: <ListRoute /> },
          { path: "s/:spaceId/members", element: <SpaceMembersPage /> },
          { path: "u/:userId", element: <MemberProfilePage /> },
          {
            path: "settings",
            element: <WorkspaceSettingsLayout />,
            children: [
              { index: true, element: <SettingsGeneralPage /> },
              { path: "members", element: <SettingsMembersPage /> },
              { path: "invitations", element: <SettingsInvitationsPage /> },
              { path: "permissions", element: <SettingsPermissionsPage /> },
            ],
          },
        ],
      },
    ],
  },

  { path: "*", element: <NotFound /> },
];

export const appRouter = createBrowserRouter(routes);
