/**
 * @schema AppShell
 * @purpose Apple-style app shell: glass sidebar, top bar, content area
 */
import { Outlet, createFileRoute } from "@tanstack/react-router";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { BottomNav } from "@/components/layout/bottom-nav";
import { NotificationProvider } from "@/lib/use-notifications";

export const Route = createFileRoute("/_app")({
  component: AppShell,
});

export function AppShell() {
  return (
    <NotificationProvider>
      <div className="flex h-screen overflow-hidden bg-[var(--color-background)]">
        <Sidebar className="hidden md:flex" />
        <div className="hidden md:block w-[260px] shrink-0" aria-hidden />
        <div className="flex flex-1 flex-col min-w-0">
          <TopBar className="hidden md:flex" />
          <main className="flex-1 overflow-auto">
            <div className="mx-auto w-full max-w-[1280px] px-6 py-8 md:px-10 md:py-10">
              <Outlet />
            </div>
          </main>
        </div>
        <BottomNav className="md:hidden" />
      </div>
      <div id="portal-root" />
    </NotificationProvider>
  );
}
