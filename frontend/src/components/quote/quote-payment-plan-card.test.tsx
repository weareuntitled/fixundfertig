import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { QuotePaymentPlanCard } from "./quote-payment-plan-card";

vi.mock("@/lib/use-notifications", () => ({ useNotification: () => ({ notify: vi.fn() }) }));

const quote = {
  id: 7,
  total_brutto: 357,
  payment_plan: [
    { percent: 50, label: "bei Auftrag", amount: 178.5 },
    { percent: 50, label: "nach Livegang", amount: 178.5 },
  ],
};

let fetchMock: ReturnType<typeof vi.fn>;

function renderCard(props: Partial<Parameters<typeof QuotePaymentPlanCard>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <QuotePaymentPlanCard quoteId={quote.id} gross={quote.total_brutto} plan={quote.payment_plan} locked={false} {...props} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchMock = vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(quote) } as Response));
  globalThis.fetch = fetchMock as unknown as typeof fetch;
});

afterEach(() => vi.restoreAllMocks());

describe("QuotePaymentPlanCard", () => {
  it("lists each installment with percent, occasion and amount", () => {
    renderCard();
    expect(screen.getByText("bei Auftrag")).toBeTruthy();
    expect(screen.getByText("nach Livegang")).toBeTruthy();
    expect(screen.getAllByText("50 %")).toHaveLength(2);
    expect(screen.getAllByText("178,50 €")).toHaveLength(2);
  });

  it("saves an edited plan through the invoice API", async () => {
    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Zahlungsplan bearbeiten" }));
    fireEvent.change(screen.getByLabelText("Prozent Rate 1"), { target: { value: "30" } });
    expect(screen.getByRole("status").textContent).toContain("nicht 100 %");
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/invoices/7");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body)).payment_plan).toEqual([
      { percent: 30, label: "bei Auftrag" },
      { percent: 50, label: "nach Livegang" },
    ]);
  });

  it("cannot be edited once the quote is accepted", () => {
    renderCard({ locked: true });
    expect(screen.queryByRole("button", { name: "Zahlungsplan bearbeiten" })).toBeNull();
  });

  it("says when there is no plan", () => {
    renderCard({ plan: [] });
    expect(screen.getByText(/Kein Zahlungsplan/)).toBeTruthy();
  });
});
