import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as invitesModule from "./use-invites";

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useInvites", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches invites from /api/invites", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([{ email: "a@b.de", invited_at: "2026-06-10" }]),
    } as Response);

    const wrapper = makeWrapper();
    const { result } = renderHook(() => invitesModule.useInvites(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([{ email: "a@b.de", invited_at: "2026-06-10" }]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/invites",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("returns empty array when no invites exist", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([]),
    } as Response);

    const wrapper = makeWrapper();
    const { result } = renderHook(() => invitesModule.useInvites(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });
});
