import type { ReactNode } from "react";
import { render } from "@testing-library/react";
import {
  createMemoryHistory,
  createRootRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";

/** Renders `ui` inside a minimal router so `<Link>` works in component tests. */
export async function renderInRouter(ui: ReactNode, path = "/") {
  const rootRoute = createRootRoute({ component: () => <>{ui}</> });
  const router = createRouter({
    routeTree: rootRoute,
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  const result = render(<RouterProvider router={router} />);
  await router.load();
  return result;
}
