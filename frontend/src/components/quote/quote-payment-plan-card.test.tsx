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

  it("bills an installment through the down-payment endpoint", async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 201,
        json: () =>
          Promise.resolve({
            id: 43, customer_id: 7, document_type: "INVOICE", nr: "10000",
            total_brutto: 2380, status: "DRAFT", down_payment_index: 0, quote_id: 7,
          }),
      } as Response),
    );
    renderCard();

    fireEvent.click(screen.getAllByRole("button", { name: "Abschlagsrechnung" })[0]);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/invoices/7/down-payment");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ installment_index: 0 });
  });

  it("marks a sent installment as billed and names the status of its invoice", () => {
    renderCard({
      invoices: [
        { id: 43, nr: "10000", status: "SENT", total_brutto: 2380, installment_index: 0, is_down_payment: true, is_final_invoice: false },
      ],
    });

    expect(screen.getByText("Gesendet")).toBeTruthy();
    const link = screen.getByRole("link", { name: /Rechnung 10000/ });
    expect(link.getAttribute("href")).toBe("/invoices/43");
    expect(screen.getAllByRole("button", { name: "Abschlagsrechnung" })).toHaveLength(1);
  });

  it("shows a draft invoice as Entwurf and keeps the rate blocked", () => {
    renderCard({
      invoices: [
        { id: 43, nr: "10000", status: "DRAFT", total_brutto: 2380, installment_index: 0, is_down_payment: true, is_final_invoice: false },
      ],
    });

    expect(screen.getByText("Entwurf")).toBeTruthy();
    const link = screen.getByRole("link", { name: /Rechnung 10000/ });
    expect(link.getAttribute("href")).toBe("/invoices/43");
    expect(screen.queryByText(/Abgerechnet/)).toBeNull();
    expect(screen.getAllByRole("button", { name: "Abschlagsrechnung" })).toHaveLength(1);
  });

  it("lets a rate be billed again after its down-payment invoice was cancelled", () => {
    renderCard({
      invoices: [
        { id: 43, nr: "10000", status: "CANCELLED", total_brutto: 2380, installment_index: 0, is_down_payment: true, is_final_invoice: false },
      ],
    });

    expect(screen.getAllByRole("button", { name: "Abschlagsrechnung" })).toHaveLength(2);
    expect(screen.queryByRole("link", { name: /Rechnung 10000/ })).toBeNull();
    expect(screen.queryByText(/Abgerechnet/)).toBeNull();
  });
});
