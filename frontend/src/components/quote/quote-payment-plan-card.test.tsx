import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
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

/** Die Karte braucht einen Router (Link und Sprung zur Rechnung). */
async function renderCard(props: Partial<Parameters<typeof QuotePaymentPlanCard>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const rootRoute = createRootRoute({ component: () => <Outlet /> });
  const cardRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: () => (
      <QuotePaymentPlanCard
        quoteId={quote.id}
        gross={quote.total_brutto}
        plan={quote.payment_plan}
        locked={false}
        {...props}
      />
    ),
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([cardRoute]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  const result = render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  // Der Router rendert die Route erst im nächsten Tick.
  await screen.findByRole("heading", { name: "Zahlungsplan" });
  return result;
}

beforeEach(() => {
  fetchMock = vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(quote) } as Response));
  globalThis.fetch = fetchMock as unknown as typeof fetch;
});

afterEach(() => vi.restoreAllMocks());

describe("QuotePaymentPlanCard", () => {
  it("lists each installment with percent, occasion and amount", async () => {
    await renderCard();
    expect(screen.getByText("bei Auftrag")).toBeTruthy();
    expect(screen.getByText("nach Livegang")).toBeTruthy();
    expect(screen.getAllByText("50 %")).toHaveLength(2);
    expect(screen.getAllByText("178,50 €")).toHaveLength(2);
  });

  it("saves an edited plan through the invoice API", async () => {
    await renderCard();
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

  it("keeps changes when discarding the payment plan is declined", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    await renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Zahlungsplan bearbeiten" }));
    fireEvent.change(screen.getByLabelText("Prozent Rate 1"), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(confirm).toHaveBeenCalled();
    expect(screen.getByLabelText("Prozent Rate 1")).toHaveValue(30);
  });

  it("blocks a plan over 100 % and says why", async () => {
    await renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Zahlungsplan bearbeiten" }));
    fireEvent.change(screen.getByLabelText("Prozent Rate 1"), { target: { value: "80" } });

    expect(screen.getByRole("alert").textContent).toContain("mehr als 100 %");
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
  });

  it("cannot be edited once the quote is accepted", async () => {
    await renderCard({ locked: true });
    expect(screen.queryByRole("button", { name: "Zahlungsplan bearbeiten" })).toBeNull();
  });

  it("says when there is no plan", async () => {
    await renderCard({ plan: [] });
    expect(screen.getByText(/Kein Zahlungsplan/)).toBeTruthy();
  });

  it("names the amount of the installment in the billing button", async () => {
    await renderCard();
    expect(screen.getAllByRole("button", { name: "Abschlag 178,50 € abrechnen" })).toHaveLength(2);
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
    await renderCard();

    fireEvent.click(screen.getAllByRole("button", { name: "Abschlag 178,50 € abrechnen" })[0]);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/invoices/7/down-payment");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ installment_index: 0 });
  });

  it("marks a sent installment as billed and names the status of its invoice", async () => {
    await renderCard({
      invoices: [
        { id: 43, nr: "10000", status: "SENT", total_brutto: 2380, installment_index: 0, is_down_payment: true, is_final_invoice: false },
      ],
    });

    expect(screen.getByText("Gesendet")).toBeTruthy();
    const link = screen.getByRole("link", { name: /Abschlagsrechnung 10000/ });
    expect(link.getAttribute("href")).toBe("/invoices/43");
    expect(screen.getAllByRole("button", { name: /Abschlag .* abrechnen/ })).toHaveLength(1);
  });

  it("shows a draft invoice as Entwurf and keeps the rate blocked", async () => {
    await renderCard({
      invoices: [
        { id: 43, nr: "10000", status: "DRAFT", total_brutto: 2380, installment_index: 0, is_down_payment: true, is_final_invoice: false },
      ],
    });

    expect(screen.getByText("Entwurf")).toBeTruthy();
    const link = screen.getByRole("link", { name: /Abschlagsrechnung 10000/ });
    expect(link.getAttribute("href")).toBe("/invoices/43");
    expect(screen.queryByText(/Abgerechnet/)).toBeNull();
    expect(screen.getAllByRole("button", { name: /Abschlag .* abrechnen/ })).toHaveLength(1);
  });

  it("lets a rate be billed again after its down-payment invoice was cancelled", async () => {
    await renderCard({
      invoices: [
        { id: 43, nr: "10000", status: "CANCELLED", total_brutto: 2380, installment_index: 0, is_down_payment: true, is_final_invoice: false },
      ],
    });

    expect(screen.getAllByRole("button", { name: /Abschlag .* abrechnen/ })).toHaveLength(2);
    expect(screen.queryByRole("link", { name: /Abschlagsrechnung 10000/ })).toBeNull();
    expect(screen.queryByText(/Abgerechnet/)).toBeNull();
  });

  it("shows the reason when the server does not allow a down payment", async () => {
    await renderCard({
      billing: {
        convert: { allowed: false, reason: "Ein Entwurf lässt sich nicht abrechnen.", invoice_id: null, invoice_nr: null },
        down_payment: { allowed: false, reason: "Ein Entwurf lässt sich nicht abrechnen.", invoice_id: null, invoice_nr: null },
        final_invoice: { allowed: false, reason: "Ein Entwurf lässt sich nicht abrechnen.", invoice_id: null, invoice_nr: null },
        requires_acceptance: false,
      },
    });

    expect(screen.getByText(/Ein Entwurf lässt sich nicht abrechnen/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Abschlag .* abrechnen/ })).toBeNull();
    expect(screen.getAllByText(/nicht abrechenbar/)).toHaveLength(2);
  });
});
