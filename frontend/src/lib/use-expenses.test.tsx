import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as expensesModule from "./use-expenses";

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useExpenses", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches and parses expenses from /api/expenses", async () => {
    const fakeExpense = {
      id: 1, company_id: 1, date: "2026-06-10", category: "Büro",
      description: "Tinte", amount: 9.99, source: "MANUAL",
    };
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([fakeExpense]),
    } as Response);

    const wrapper = makeWrapper();
    const { result } = renderHook(() => expensesModule.useExpenses(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([fakeExpense]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/expenses",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("returns empty array when no expenses exist", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([]),
    } as Response);

    const wrapper = makeWrapper();
    const { result } = renderHook(() => expensesModule.useExpenses(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });

  it("exposes isLoading=true while fetching", () => {
    fetchMock.mockReturnValue(new Promise(() => {})); // never resolves
    const wrapper = makeWrapper();
    const { result } = renderHook(() => expensesModule.useExpenses(), { wrapper });
    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
  });
});
