import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { routeTree } from "@/routeTree.gen";

type Quote = Record<string, unknown>;

const baseQuote: Quote = {
  id: 7,
  customer_id: 3,
  document_type: "QUOTE",
  nr: "A-10000",
  title: "Angebot",
  subject: "Hochzeit",
  date: "2026-10-23",
  valid_until: "2099-12-31",
  recipient_name: "Club Beispiel",
  total_brutto: 300,
  status: "SENT",
  items: [{ id: 1, description: "DJ-Set", quantity: 2, unit_price: 150 }],
};

let fetchMock: ReturnType<typeof vi.fn>;
let current: Quote;

function json(body: unknown, status = 200) {
  return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) } as Response);
}

function renderQuote(quote: Quote) {
  current = quote;
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json({ id: 1, email: "owner@example.test" });
    if (url === "/api/invoices/7/status" && init?.method === "PUT") {
      current = { ...current, status: JSON.parse(String(init.body)).status };
      return json(current);
    }
    if (url === "/api/invoices/7") return json(current);
    return json({}, 404);
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: ["/quotes/7"] }) });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

function statusCalls() {
  return fetchMock.mock.calls.filter(([url]) => url === "/api/invoices/7/status");
}

describe("Angebot-Detailseite: Status", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a sent quote past its valid-until date as expired", async () => {
    renderQuote({ ...baseQuote, valid_until: "2020-01-31" });
    expect(await screen.findByText("Abgelaufen")).toBeTruthy();
  });

  it("marks a quote as accepted after confirming and then locks it", async () => {
    renderQuote(baseQuote);
    fireEvent.click(await screen.findByRole("button", { name: "Angenommen" }));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Annehmen" }));

    await waitFor(() => expect(statusCalls()).toHaveLength(1));
    expect(JSON.parse(String(statusCalls()[0][1].body))).toMatchObject({ status: "ACCEPTED" });
    expect(await screen.findByText(/nicht mehr änderbar/)).toBeTruthy();
  });

  it("marks a quote as rejected", async () => {
    renderQuote(baseQuote);
    fireEvent.click(await screen.findByRole("button", { name: "Abgelehnt" }));

    await waitFor(() => expect(statusCalls()).toHaveLength(1));
    expect(JSON.parse(String(statusCalls()[0][1].body))).toMatchObject({ status: "REJECTED" });
  });

  it("locks the form of an accepted quote", async () => {
    renderQuote({ ...baseQuote, status: "ACCEPTED" });
    expect(await screen.findByText(/nicht mehr änderbar/)).toBeTruthy();
    expect(screen.getAllByText("Angenommen").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /Bearbeiten/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Position/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Angenommen" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Abgelehnt" })).toBeNull();
  });

  it("lists a final invoice as Schlussrechnung and links it", async () => {
    renderQuote({
      ...baseQuote,
      status: "ACCEPTED",
      linked_invoices: [
        {
          id: 44,
          nr: "10001",
          status: "DRAFT",
          total_brutto: 2380,
          installment_index: null,
          is_down_payment: false,
          is_final_invoice: true,
        },
      ],
    });

    const link = await screen.findByRole("link", { name: /Schlussrechnung 10001/ });
    expect(link.getAttribute("href")).toBe("/invoices/44");
    expect(screen.queryByRole("button", { name: "Schlussrechnung" })).toBeDisabled();
  });
});

describe("Angebot-Detailseite: Schlussrechnung", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const downPayment = (status: string) => ({
    id: 43,
    nr: "10000",
    status,
    total_brutto: 2380,
    installment_index: 0,
    is_down_payment: true,
    is_final_invoice: false,
  });

  it("cannot be created without a down-payment invoice and says why", async () => {
    renderQuote({ ...baseQuote, linked_invoices: [] });

    const button = await screen.findByRole("button", { name: "Schlussrechnung" });
    expect(button).toBeDisabled();
    expect(await screen.findByText(/Abschlagsrechnung zuerst senden/)).toBeTruthy();
  });

  it("cannot be created while the down-payment invoice is still a draft", async () => {
    renderQuote({ ...baseQuote, linked_invoices: [downPayment("DRAFT")] });

    const button = await screen.findByRole("button", { name: "Schlussrechnung" });
    expect(button).toBeDisabled();
    expect(await screen.findByText(/Abschlagsrechnung zuerst senden/)).toBeTruthy();
  });

  it("can be created once the down-payment invoice has been sent", async () => {
    renderQuote({ ...baseQuote, linked_invoices: [downPayment("SENT")] });

    const button = await screen.findByRole("button", { name: "Schlussrechnung" });
    expect(button).not.toBeDisabled();
    expect(screen.queryByText(/Abschlagsrechnung zuerst senden/)).toBeNull();
  });
});
