import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as accountModule from "./use-account";

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useChangePassword", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends POST /api/auth/password with payload", async () => {
    fetchMock.mockResolvedValue({
      ok: true, status: 204, json: () => Promise.resolve(undefined),
    } as Response);

    const wrapper = makeWrapper();
    const { result } = renderHook(() => accountModule.useChangePassword(), { wrapper });

    result.current.mutate({ current_password: "old123", new_password: "new456" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/password",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ current_password: "old123", new_password: "new456" }),
      }),
    );
  });

  it("exposes isError when backend returns 400", async () => {
    fetchMock.mockResolvedValue({
      ok: false, status: 400, json: () => Promise.resolve({ detail: "Current password is incorrect" }),
    } as Response);

    const wrapper = makeWrapper();
    const { result } = renderHook(() => accountModule.useChangePassword(), { wrapper });

    result.current.mutate({ current_password: "wrong", new_password: "new456" });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
