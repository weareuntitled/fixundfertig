import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useQuotes } from "./use-invoices";

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useQuotes", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("asks the invoice API for quotes only", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve([
          { id: 7, customer_id: 3, document_type: "QUOTE", nr: "A-10000", valid_until: "2026-11-22", total_brutto: 300, status: "DRAFT" },
        ]),
    } as Response);

    const { result } = renderHook(() => useQuotes(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.[0].nr).toBe("A-10000");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/invoices?document_type=QUOTE",
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
