import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as documentsModule from "./use-documents";

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useDocuments", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches documents from /api/documents", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([
        { id: 1, original_filename: "r.pdf", title: "", vendor: "", doc_number: "", doc_date: "", amount_total: null, amount_net: null, amount_tax: null, currency: "", mime: "application/pdf", size: 1024, source: "MANUAL", type: "pdf", description: "", created_at: "2026-06-10" },
      ]),
    } as Response);

    const wrapper = makeWrapper();
    const { result } = renderHook(() => documentsModule.useDocuments(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data![0].original_filename).toBe("r.pdf");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/documents",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("returns empty array when no documents exist", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([]),
    } as Response);

    const wrapper = makeWrapper();
    const { result } = renderHook(() => documentsModule.useDocuments(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });
});
