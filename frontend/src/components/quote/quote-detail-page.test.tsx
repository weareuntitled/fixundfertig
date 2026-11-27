import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { routeTree } from "@/routeTree.gen";

type Quote = Record<string, unknown>;

const allowed = { allowed: true, reason: "", invoice_id: null, invoice_nr: null };
const blocked = (reason: string, invoice_id: number | null = null, invoice_nr: string | null = null) => ({
  allowed: false,
  reason,
  invoice_id,
  invoice_nr,
});

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
  total_brutto: 357,
  total_net: 300,
  vat_rate: 19,
  totals: { net: 300, vat_rate: 19, tax: 57, gross: 357, deductions: [], rest_net: 300, rest_tax: 57, payable: 357 },
  status: "SENT",
  items: [{ id: 1, description: "DJ-Set", quantity: 2, unit_price: 150 }],
  settlement: { billed_brutto: 0, total_brutto: 357, open_brutto: 357, billed_count: 0 },
  billing: { convert: allowed, down_payment: allowed, final_invoice: allowed, requires_acceptance: false },
};

let fetchMock: ReturnType<typeof vi.fn>;
let current: Quote;
let newValidUntil = "2099-12-31";

function json(body: unknown, status = 200) {
  return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) } as Response);
}

function renderQuote(quote: Quote) {
  current = quote;
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json({ id: 1, email: "owner@example.test" });
    if (url === "/api/customers/3") {
      return json({ id: 3, name: "Club Beispiel", email: "buchhaltung@club.example" });
    }
    if (url === "/api/invoices/7/status" && init?.method === "PUT") {
      current = { ...current, status: JSON.parse(String(init.body)).status };
      return json(current);
    }
    if (url === "/api/invoices/7/mark-sent" && init?.method === "POST") {
      current = { ...current, status: "SENT" };
      return json(current);
    }
    if (url === "/api/invoices/7/extend-validity" && init?.method === "POST") {
      current = { ...current, valid_until: newValidUntil };
      return json(current);
    }
    if (url === "/api/invoices/7/send" && init?.method === "POST") {
      return json({ detail: "Der E-Mail-Versand ist noch nicht eingerichtet." }, 502);
    }
    if (url === "/api/invoices/7/down-payment" && init?.method === "POST") {
      return json({ id: 43, nr: "10000", document_type: "INVOICE", status: "DRAFT", total_brutto: 143 });
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

function postCalls(url: string) {
  return fetchMock.mock.calls.filter(([callUrl]) => callUrl === url);
}

/** Die Primärknöpfe der Seite (genau einer je Status). */
function primaryButtons(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>("[data-primary='true']"));
}

/** Eine Betragszeile der Angebotsseite (Netto, USt, Gesamt). */
function row(label: string): string {
  return screen.getByText(label).closest("div")?.textContent ?? "";
}

async function openMoreMenu() {
  fireEvent.click(await screen.findByRole("button", { name: "Mehr" }));
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

  it("follows a default validity date while editing and saves with Enter", async () => {
    renderQuote({ ...baseQuote, valid_until: "2026-11-22" });
    fireEvent.click(await screen.findByRole("button", { name: "Bearbeiten" }));
    fireEvent.change(screen.getByLabelText("Angebotsdatum"), { target: { value: "2026-11-01" } });
    expect(screen.getByLabelText("Gültig bis")).toHaveValue("2026-12-01");
    fireEvent.submit(screen.getByLabelText("Betreff").closest("form")!);
    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => url === "/api/invoices/7" && init?.method === "PUT")).toBe(true));
  });

  it("keeps a manually changed validity date when the offer date changes", async () => {
    renderQuote({ ...baseQuote, valid_until: "2026-11-22" });
    fireEvent.click(await screen.findByRole("button", { name: "Bearbeiten" }));
    fireEvent.change(screen.getByLabelText("Gültig bis"), { target: { value: "2026-12-10" } });
    fireEvent.change(screen.getByLabelText("Angebotsdatum"), { target: { value: "2026-11-01" } });
    expect(screen.getByLabelText("Gültig bis")).toHaveValue("2026-12-10");
  });

  it("asks before removing a position", async () => {
    renderQuote(baseQuote);
    fireEvent.click(await screen.findByRole("button", { name: "Position 1 entfernen" }));
    expect(screen.getByRole("alertdialog", { name: "Position entfernen?" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url, init]) => url === "/api/invoices/7/items/1" && init?.method === "DELETE")).toBe(false);
  });

  it("keeps an edited position when discarding is declined", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderQuote(baseQuote);
    fireEvent.click(await screen.findByRole("button", { name: "Position 1 bearbeiten" }));
    fireEvent.change(screen.getByLabelText("Beschreibung"), { target: { value: "Neuer Text" } });
    fireEvent.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(confirm).toHaveBeenCalled();
    expect(screen.getByLabelText("Beschreibung")).toHaveValue("Neuer Text");
  });

  it("marks a quote as accepted after confirming and then locks it", async () => {
    renderQuote(baseQuote);
    fireEvent.click(await screen.findByRole("button", { name: "Annehmen" }));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Annehmen" }));

    await waitFor(() => expect(statusCalls()).toHaveLength(1));
    expect(JSON.parse(String(statusCalls()[0][1].body))).toMatchObject({ status: "ACCEPTED" });
    expect(await screen.findByText(/nicht mehr änderbar/)).toBeTruthy();
  });

  it("asks before it rejects a quote", async () => {
    renderQuote(baseQuote);
    fireEvent.click(await screen.findByRole("button", { name: "Abgelehnt" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/nur noch lesbar/)).toBeTruthy();
    expect(statusCalls()).toHaveLength(0);

    fireEvent.click(within(dialog).getByRole("button", { name: "Abgelehnt" }));
    await waitFor(() => expect(statusCalls()).toHaveLength(1));
    expect(JSON.parse(String(statusCalls()[0][1].body))).toMatchObject({ status: "REJECTED" });
  });

  it("shows no edit and no billing actions for a rejected quote", async () => {
    renderQuote({
      ...baseQuote,
      status: "REJECTED",
      payment_plan: [{ percent: 40, label: "bei Auftrag", amount: 143 }],
    });
    expect(await screen.findByText(/nur noch lesbar/)).toBeTruthy();

    expect(screen.queryByRole("button", { name: /Bearbeiten/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /\+ Position/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Position 1 bearbeiten/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Senden" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Abrechnen" })).toBeNull();
    expect(screen.queryByRole("button", { name: /abrechnen/ })).toBeNull();
    expect(primaryButtons()).toHaveLength(0);
  });

  it("marks a draft quote as sent without a mail server", async () => {
    renderQuote({ ...baseQuote, status: "DRAFT" });
    await openMoreMenu();
    fireEvent.click(await screen.findByRole("menuitem", { name: "Als gesendet markieren" }));

    await waitFor(() => expect(postCalls("/api/invoices/7/mark-sent")).toHaveLength(1));
    expect(await screen.findByText("Gesendet")).toBeTruthy();
  });

  it("expires a draft quote that is marked as sent after its valid-until date", async () => {
    renderQuote({ ...baseQuote, status: "DRAFT", valid_until: "2020-01-31" });
    await openMoreMenu();
    fireEvent.click(await screen.findByRole("menuitem", { name: "Als gesendet markieren" }));

    expect(await screen.findByText("Abgelaufen")).toBeTruthy();
    expect(screen.queryByText("Gesendet")).toBeNull();
  });

  it("takes a decision back to sent", async () => {
    renderQuote({ ...baseQuote, status: "REJECTED" });
    await openMoreMenu();
    fireEvent.click(await screen.findByRole("menuitem", { name: "Entscheidung zurücknehmen" }));

    await waitFor(() => expect(postCalls("/api/invoices/7/mark-sent")).toHaveLength(1));
    expect(await screen.findByText("Gesendet")).toBeTruthy();
  });

  it("offers no way back once the quote has an invoice", async () => {
    renderQuote({
      ...baseQuote,
      status: "REJECTED",
      linked_invoices: [
        {
          id: 44,
          nr: "10001",
          status: "SENT",
          total_brutto: 2380,
          installment_index: null,
          is_down_payment: false,
          is_final_invoice: false,
        },
      ],
    });
    expect(await screen.findByText(/nur noch lesbar/)).toBeTruthy();
    await openMoreMenu();
    expect(screen.queryByRole("menuitem", { name: "Entscheidung zurücknehmen" })).toBeNull();
  });

  it("locks the form of an accepted quote", async () => {
    renderQuote({ ...baseQuote, status: "ACCEPTED" });
    expect(await screen.findByText(/nicht mehr änderbar/)).toBeTruthy();
    expect(screen.getAllByText("Angenommen").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /Bearbeiten/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Position/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Annehmen" })).toBeNull();
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
      billing: {
        convert: blocked("Das Angebot ist bereits in Rechnung 10001 umgewandelt.", 44, "10001"),
        down_payment: blocked("Das Angebot ist mit Rechnung 10001 vollständig abgerechnet.", 44, "10001"),
        final_invoice: blocked("Zu diesem Angebot gibt es bereits eine Schlussrechnung.", 44, "10001"),
        requires_acceptance: false,
      },
    });

    const link = await screen.findByRole("link", { name: /Schlussrechnung 10001/ });
    expect(link.getAttribute("href")).toBe("/invoices/44");
    // Gesperrt: kein Knopf, sondern der Grund im Klartext.
    expect(screen.queryByRole("button", { name: "Schlussrechnung" })).toBeNull();
    expect(await screen.findByText(/gibt es bereits eine Schlussrechnung/)).toBeTruthy();
  });
});

describe("Angebot-Detailseite: genau eine Primäraktion", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("offers Senden as the only primary action of a draft", async () => {
    renderQuote({ ...baseQuote, status: "DRAFT" });

    expect(await screen.findByRole("button", { name: "Senden" })).toBeTruthy();
    expect(primaryButtons()).toHaveLength(1);
    expect(primaryButtons()[0].textContent).toContain("Senden");
  });

  it("offers Annehmen as the only primary action of a sent quote", async () => {
    renderQuote(baseQuote);

    expect(await screen.findByRole("button", { name: "Annehmen" })).toBeTruthy();
    expect(primaryButtons()).toHaveLength(1);
    expect(primaryButtons()[0].textContent).toContain("Annehmen");
  });

  it("offers Abrechnen as the only primary action of an accepted quote", async () => {
    renderQuote({
      ...baseQuote,
      status: "ACCEPTED",
      billing: {
        convert: allowed,
        down_payment: blocked("Das Angebot hat keinen Zahlungsplan."),
        final_invoice: blocked("Eine Schlussrechnung entsteht nur mit einer gestellten Abschlagsrechnung."),
        requires_acceptance: false,
      },
    });

    expect(await screen.findByRole("button", { name: "Abrechnen" })).toBeTruthy();
    expect(primaryButtons()).toHaveLength(1);
  });

  it("keeps the other actions out of the header", async () => {
    renderQuote({ ...baseQuote, status: "DRAFT" });

    await screen.findByRole("button", { name: "Senden" });
    // Die übrigen Aktionen liegen im Menü und stehen deshalb nicht als Knopf offen herum.
    expect(screen.queryByRole("button", { name: "In Rechnung umwandeln" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Schlussrechnung" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Als gesendet markieren" })).toBeNull();
  });

  it("puts the billing ways into the Abrechnen menu", async () => {
    renderQuote({
      ...baseQuote,
      status: "ACCEPTED",
      payment_plan: [{ percent: 40, label: "bei Auftrag", amount: 142.8 }],
      billing: {
        convert: allowed,
        down_payment: allowed,
        final_invoice: blocked("Eine Schlussrechnung entsteht nur mit einer gestellten Abschlagsrechnung."),
        requires_acceptance: false,
      },
    });

    fireEvent.click(await screen.findByRole("button", { name: "Abrechnen" }));

    expect(await screen.findByRole("menuitem", { name: "Abschlag 142,80 € abrechnen" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "In Rechnung umwandeln" })).toBeTruthy();
  });
});

describe("Angebot-Detailseite: Abrechnungsstand und Beträge", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows how much of the quote is billed already", async () => {
    renderQuote({
      ...baseQuote,
      settlement: { billed_brutto: 143, total_brutto: 357, open_brutto: 214, billed_count: 1 },
    });

    expect(await screen.findByText(/abgerechnet 143,00 € von 357,00 € · offen 214,00 €/)).toBeTruthy();
  });

  it("shows net, VAT and gross instead of a plain sum", async () => {
    renderQuote(baseQuote);

    expect(await screen.findByText("Netto")).toBeTruthy();
    expect(screen.getByText("USt 19 %")).toBeTruthy();
    expect(screen.getByText("Gesamt (brutto)")).toBeTruthy();
    expect(row("Netto")).toContain("300,00 €");
    expect(row("USt 19 %")).toContain("57,00 €");
    expect(row("Gesamt (brutto)")).toContain("357,00 €");
    expect(screen.queryByText("Summe")).toBeNull();
  });

  it("takes net, VAT and gross from the API totals instead of computing them (#512)", async () => {
    renderQuote({
      ...baseQuote,
      // Gespeicherte Altwerte weichen ab; maßgeblich sind die Belegsummen.
      total_brutto: 107.02,
      total_net: 100.005,
      vat_rate: 19,
      totals: { net: 100.01, vat_rate: 7, tax: 7, gross: 107.01, deductions: [], rest_net: 100.01, rest_tax: 7, payable: 107.01 },
    });

    expect(await screen.findByText("USt 7 %")).toBeTruthy();
    expect(row("Netto")).toContain("100,01 €");
    expect(row("USt 7 %")).toContain("7,00 €");
    expect(row("Gesamt (brutto)")).toContain("107,01 €");
  });

  it("shows no VAT row for a quote without VAT", async () => {
    renderQuote({
      ...baseQuote,
      total_brutto: 300,
      vat_rate: 0,
      totals: { net: 300, vat_rate: 0, tax: 0, gross: 300, deductions: [], rest_net: 300, rest_tax: 0, payable: 300 },
    });

    expect(await screen.findByText("Gesamt (brutto)")).toBeTruthy();
    expect(row("Netto")).toContain("300,00 €");
    expect(screen.queryByText(/^USt/)).toBeNull();
    expect(row("Gesamt (brutto)")).toContain("300,00 €");
  });
});

describe("Angebot-Detailseite: gesperrte Aktionen", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("says why a draft cannot be billed, without hovering", async () => {
    renderQuote({
      ...baseQuote,
      status: "DRAFT",
      billing: {
        convert: blocked("Ein Entwurf lässt sich nicht abrechnen. Senden Sie das Angebot zuerst."),
        down_payment: blocked("Ein Entwurf lässt sich nicht abrechnen. Senden Sie das Angebot zuerst."),
        final_invoice: blocked("Ein Entwurf lässt sich nicht abrechnen. Senden Sie das Angebot zuerst."),
        requires_acceptance: false,
      },
    });

    expect(await screen.findByText(/Ein Entwurf lässt sich nicht abrechnen/)).toBeTruthy();
    expect(screen.getAllByText(/Ein Entwurf lässt sich nicht abrechnen/)).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Abrechnen" })).toBeNull();
  });

  it("says that a converted quote is already billed and links the invoice", async () => {
    renderQuote({
      ...baseQuote,
      status: "ACCEPTED",
      linked_invoices: [
        {
          id: 44,
          nr: "10001",
          status: "SENT",
          total_brutto: 357,
          installment_index: null,
          is_down_payment: false,
          is_final_invoice: false,
        },
      ],
      billing: {
        convert: blocked("Das Angebot ist bereits in Rechnung 10001 umgewandelt.", 44, "10001"),
        down_payment: blocked("Das Angebot ist mit Rechnung 10001 vollständig abgerechnet.", 44, "10001"),
        final_invoice: blocked("Das Angebot ist mit Rechnung 10001 vollständig abgerechnet.", 44, "10001"),
        requires_acceptance: false,
      },
    });

    expect(await screen.findByText(/vollständig abgerechnet/)).toBeTruthy();
    const link = screen.getByRole("link", { name: "Rechnung 10001 öffnen" });
    expect(link.getAttribute("href")).toBe("/invoices/44");
  });

  it("says that after a down payment only the final invoice is left", async () => {
    renderQuote({
      ...baseQuote,
      status: "ACCEPTED",
      linked_invoices: [
        {
          id: 43,
          nr: "10000",
          status: "SENT",
          total_brutto: 143,
          installment_index: 0,
          is_down_payment: true,
          is_final_invoice: false,
        },
      ],
      billing: {
        convert: blocked("Es gibt bereits eine Abschlagsrechnung (10000). Rechnen Sie den Rest mit der Schlussrechnung ab.", 43, "10000"),
        down_payment: allowed,
        final_invoice: allowed,
        requires_acceptance: false,
      },
    });

    expect(await screen.findByText(/Rechnen Sie den Rest mit der Schlussrechnung ab/)).toBeTruthy();
    // Die Schlussrechnung ist der nächste Schritt und damit der Primärknopf.
    expect(primaryButtons()).toHaveLength(1);
    expect(primaryButtons()[0].textContent).toContain("Schlussrechnung");
  });
});

describe("Angebot-Detailseite: Gültigkeit", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
    newValidUntil = "2099-12-31";
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("extends the validity of an expired quote", async () => {
    renderQuote({ ...baseQuote, valid_until: "2020-01-31" });
    expect(await screen.findByText(/abgelaufen/)).toBeTruthy();

    newValidUntil = "2099-12-31";
    fireEvent.click(screen.getByRole("button", { name: "Gültigkeit verlängern" }));

    await waitFor(() => expect(postCalls("/api/invoices/7/extend-validity")).toHaveLength(1));
    await waitFor(() => expect(screen.queryByText("Abgelaufen")).toBeNull());
  });

  it("mentions the expiry when it asks before accepting the quote", async () => {
    renderQuote({ ...baseQuote, valid_until: "2020-01-31" });
    fireEvent.click(await screen.findByRole("button", { name: "Annehmen" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/31\.01\.2020/)).toBeTruthy();
    expect(within(dialog).getByText(/nicht mehr ändern/)).toBeTruthy();
  });
});

describe("Angebot-Detailseite: Abrechnen fragt nach der Annahme", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });
  it("asks before it bills a quote that is only sent", async () => {
    renderQuote({
      ...baseQuote,
      status: "SENT",
      billing: {
        convert: allowed,
        down_payment: blocked("Das Angebot hat keinen Zahlungsplan."),
        final_invoice: blocked("Eine Schlussrechnung entsteht nur mit einer gestellten Abschlagsrechnung."),
        requires_acceptance: true,
      },
    });

    await openMoreMenu();
    fireEvent.click(await screen.findByRole("menuitem", { name: "In Rechnung umwandeln" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/gilt das Angebot als angenommen/)).toBeTruthy();
    expect(postCalls("/api/invoices/7/convert")).toHaveLength(0);
  });

  it("asks before it bills a rate of a quote that is only sent", async () => {
    renderQuote({
      ...baseQuote,
      status: "SENT",
      payment_plan: [{ percent: 40, label: "bei Auftrag", amount: 142.8 }],
      billing: {
        convert: allowed,
        down_payment: allowed,
        final_invoice: blocked("Eine Schlussrechnung entsteht nur mit einer gestellten Abschlagsrechnung."),
        requires_acceptance: true,
      },
    });

    fireEvent.click(await screen.findByRole("button", { name: "Abschlag 142,80 € abrechnen" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/gilt das Angebot als angenommen/)).toBeTruthy();
    expect(postCalls("/api/invoices/7/down-payment")).toHaveLength(0);
  });
});

describe("Angebot-Detailseite: Versand ohne Mailserver", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps the send error in the dialog and offers a way out", async () => {
    renderQuote({ ...baseQuote, status: "DRAFT" });
    // Der Sendedialog braucht die E-Mail-Adresse des Kunden.
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => url === "/api/customers/3")).toBe(true),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Senden" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Senden" }));

    expect(await screen.findByText("Der E-Mail-Versand ist noch nicht eingerichtet.")).toBeTruthy();
    const openDialog = screen.getByRole("dialog");
    expect(openDialog).toBeTruthy();
    expect(within(openDialog).getByRole("link", { name: /Einstellungen/ })).toBeTruthy();
    expect(within(openDialog).getByRole("link", { name: /PDF herunterladen/ })).toBeTruthy();
    expect(within(openDialog).getByRole("button", { name: /Als gesendet markieren/ })).toBeTruthy();
  });
});
