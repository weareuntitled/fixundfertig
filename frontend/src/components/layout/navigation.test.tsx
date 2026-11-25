import { screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { BottomNav } from "./bottom-nav";
import { Sidebar } from "./sidebar";
import { renderInRouter } from "@/test/render-in-router";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ data: { email: "owner@example.test" } }),
  useLogout: () => ({ mutate: vi.fn() }),
}));

const TOUCH_TARGET = ["min-h-[44px]", "min-w-[44px]"];

describe("navigation to quotes", () => {
  it("bottom nav links to quotes with a 44pt touch target", async () => {
    await renderInRouter(<BottomNav />);
    const link = await screen.findByRole("link", { name: "Angebote" });
    expect(link.getAttribute("href")).toBe("/quotes");
    for (const cls of TOUCH_TARGET) expect(link.className).toContain(cls);
  });

  it("sidebar links to quotes with a 44pt touch target", async () => {
    await renderInRouter(
      <QueryClientProvider client={new QueryClient()}>
        <Sidebar />
      </QueryClientProvider>,
    );
    const link = await screen.findByRole("link", { name: "Angebote" });
    expect(link.getAttribute("href")).toBe("/quotes");
    expect(link.className).toContain("min-h-[44px]");
  });
});
