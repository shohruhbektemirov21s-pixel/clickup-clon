import { HomeRedirect } from "@/components/auth/home-redirect";
import { Landing } from "@/components/marketing/landing";

/**
 * `<Landing />` is passed as a child so it stays a server component: only
 * `HomeRedirect` (the auth/redirect logic) ships to the browser, while the
 * marketing tree renders to HTML on the server.
 */
export default function HomePage() {
  return (
    <HomeRedirect>
      <Landing />
    </HomeRedirect>
  );
}
