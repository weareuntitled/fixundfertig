import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRouter, RouterProvider, createMemoryHistory } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";

function renderWithProviders(initialPath: string = "/") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [initialPath] }),
    defaultPreload: false,
    defaultPreloadStaleTime: 0,
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

describe("M1 hello-world smoke", () => {
  it("App mounts the React tree and renders into the document", () => {
    const { baseElement } = renderWithProviders("/");
    // The body or test container must contain a <div> rendered by React
    const root = baseElement.querySelector("div");
    expect(root).not.toBeNull();
  });
});



