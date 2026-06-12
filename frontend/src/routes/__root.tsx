import { Outlet, createRootRoute, useRouterState } from "@tanstack/react-router";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

export const Route = createRootRoute({
  component: RootComponent,
});

function RootComponent() {
  const { data: user, isLoading } = useAuth();
  const { location } = useRouterState();

  const isLoginPath = location.pathname === "/login";

  // Redirect to /login if not authenticated, except when already on /login.
  useEffect(() => {
    if (!isLoginPath && !isLoading && !user) {
      window.location.assign("/login");
    }
  }, [user, isLoading, isLoginPath]);

  // Loading state: only show the "Lädt…" gate on protected routes,
  // not on the login page (which has its own UI).
  if (isLoading && !isLoginPath) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--ff-bg)] text-[var(--ff-muted)]">
        Lädt…
      </div>
    );
  }

  // Unauthenticated user on a protected route — render nothing while the
  // window.location.assign effect takes effect.
  if (!user && !isLoginPath) {
    return null;
  }

  // Authenticated user, or on /login (which has its own layout).
  return <Outlet />;
}
