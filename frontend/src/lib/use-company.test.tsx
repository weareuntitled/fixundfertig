import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as companyModule from "./use-company";

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useCompany", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches and parses company from /api/company", async () => {
    const fake = {
      id: 1, name: "Test GmbH", first_name: "", last_name: "",
      business_type: "", is_small_business: false,
      street: "Hauptstr 1", postal_code: "12345", city: "Berlin",
      country: "Deutschland", email: "firma@example.com", phone: "",
      iban: "", bic: "", bank_name: "", tax_id: "", vat_id: "",
    };
    fetchMock.mockResolvedValue({
      ok: true, status: 200, json: () => Promise.resolve(fake),
    } as Response);

    const wrapper = makeWrapper();
    const { result } = renderHook(() => companyModule.useCompany(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.name).toBe("Test GmbH");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/company",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("useUpdateCompany sends PUT with patch and updates cache on success", async () => {
    const original = {
      id: 1, name: "Alter Name", first_name: "", last_name: "",
      business_type: "", is_small_business: false,
      street: "Alt 1", postal_code: "11111", city: "Hamburg",
      country: "Deutschland", email: "", phone: "",
      iban: "", bic: "", bank_name: "", tax_id: "", vat_id: "",
    };
    const updated = { ...original, name: "Neue Firma", street: "Neu 5" };

    fetchMock.mockResolvedValue({
      ok: true, status: 200, json: () => Promise.resolve(updated),
    } as Response);

    const wrapper = makeWrapper();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(["company"], original);

    const { result } = renderHook(
      () => ({ update: companyModule.useUpdateCompany(), company: companyModule.useCompany() }),
      { wrapper: ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider> },
    );
    void wrapper;

    result.current.update.mutate({ name: "Neue Firma", street: "Neu 5" });

    await waitFor(() => expect(result.current.update.isSuccess).toBe(true));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/company",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ name: "Neue Firma", street: "Neu 5" }) }),
    );
  });
});
