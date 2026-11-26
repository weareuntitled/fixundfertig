import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InvoiceFormV2 } from "./invoice-form-v2";
import { emptyInvoiceDraft, emptyQuoteDraft, type InvoiceDraft } from "@/lib/schemas/invoice";

vi.mock("./customer-selector", () => ({
  CustomerSelector: () => <div>Kunde wählen</div>,
}));

function Harness({ initial }: { initial: InvoiceDraft }) {
  const [draft, setDraft] = useState(initial);
  return <InvoiceFormV2 value={draft} onChange={setDraft} />;
}

const base: InvoiceDraft = {
  ...emptyInvoiceDraft(3),
  date: "2026-10-23",
  items: [{ description: "DJ-Set", quantity: 1, unit_price: 400 }],
};

describe("InvoiceFormV2", () => {
  it("says what an empty service date means and shows the payment deadline", () => {
    render(<Harness initial={base} />);
    expect(screen.getByLabelText("Leistungsdatum").getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByText(/Leer = wie Rechnungsdatum/)).toBeTruthy();
    expect(screen.getByText(/Zahlungsziel 5 Tage/).textContent).toContain("28.10.2026");
  });

  it("does not pretend the invoice number is a field", () => {
    render(<Harness initial={base} />);
    expect(screen.queryByDisplayValue(/Wird beim Finalisieren vergeben/)).toBeNull();
    expect(screen.getByText(/lässt sich danach nicht mehr ändern/)).toBeTruthy();
  });

  it("adds an empty position and focuses its description", () => {
    render(<Harness initial={base} />);
    fireEvent.click(screen.getByRole("button", { name: "Neue Position" }));
    const field = screen.getByLabelText("Beschreibung Position 2");
    expect(document.activeElement).toBe(field);
  });

  it("removes a position visibly and brings it back with undo", () => {
    render(<Harness initial={base} />);
    fireEvent.click(screen.getByRole("button", { name: "Position 1 entfernen" }));
    expect(screen.queryByLabelText("Beschreibung Position 1")).toBeNull();
    expect(screen.getByRole("status").textContent).toContain("Position 1 entfernt");
    fireEvent.click(screen.getByRole("button", { name: "Rückgängig" }));
    expect((screen.getByLabelText("Beschreibung Position 1") as HTMLInputElement).value).toBe("DJ-Set");
  });

  it("flags a quantity that is not positive", () => {
    render(<Harness initial={base} />);
    const quantity = screen.getByLabelText("Menge Position 1");
    expect(quantity.getAttribute("aria-invalid")).toBe("false");
    fireEvent.change(quantity, { target: { value: "0" } });
    expect(quantity.getAttribute("aria-invalid")).toBe("true");
  });

  it("hides the rate when VAT is switched off and brings back 19 percent", () => {
    render(<Harness initial={{ ...base, ust_enabled: false, vat_rate: 0 }} />);
    expect(screen.queryByLabelText("USt-Satz")).toBeNull();
    expect(screen.getByText(/keine Umsatzsteuer ausgewiesen/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Umsatzsteuer ausweisen"));
    expect((screen.getByLabelText("USt-Satz") as HTMLInputElement).value).toBe("19");
  });

  it("shows net, VAT and total", () => {
    render(<Harness initial={{ ...base, ust_enabled: true, vat_rate: 19 }} />);
    expect(screen.getByText("476,00 €")).toBeTruthy();
    expect(screen.getByText("76,00 €")).toBeTruthy();
  });
});

describe("InvoiceFormV2 for a quote", () => {
  const quote: InvoiceDraft = {
    ...emptyQuoteDraft(3, "2026-10-23"),
    items: [{ description: "DJ-Set", quantity: 1, unit_price: 400 }],
  };

  it("starts with valid until 30 days after the quote date", () => {
    expect(quote.document_type).toBe("QUOTE");
    expect(quote.valid_until).toBe("2026-11-22");
  });

  it("asks for quote date and valid until instead of service date and payment term", () => {
    render(<Harness initial={quote} />);
    expect(screen.getByText("Angebotsnummer")).toBeTruthy();
    expect((screen.getByLabelText("Angebotsdatum") as HTMLInputElement).value).toBe("2026-10-23");
    expect((screen.getByLabelText("Gültig bis") as HTMLInputElement).value).toBe("2026-11-22");
    expect(screen.queryByLabelText("Leistungsdatum")).toBeNull();
    expect(screen.queryByText(/Zahlungsziel/)).toBeNull();
  });

  it("moves an untouched valid until along with the quote date", () => {
    render(<Harness initial={quote} />);
    fireEvent.change(screen.getByLabelText("Angebotsdatum"), { target: { value: "2026-12-01" } });
    expect((screen.getByLabelText("Gültig bis") as HTMLInputElement).value).toBe("2026-12-31");
  });

  it("keeps a chosen valid until when the quote date changes", () => {
    render(<Harness initial={quote} />);
    fireEvent.change(screen.getByLabelText("Gültig bis"), { target: { value: "2027-01-15" } });
    fireEvent.change(screen.getByLabelText("Angebotsdatum"), { target: { value: "2026-12-01" } });
    expect((screen.getByLabelText("Gültig bis") as HTMLInputElement).value).toBe("2027-01-15");
  });

  it("names the default intro of the quote, not the one of the invoice", () => {
    render(<Harness initial={quote} />);
    expect(screen.getByText(/Hiermit biete ich folgende Leistungen an/)).toBeTruthy();
    expect(screen.queryByText(/Hiermit stelle ich folgende Leistungen in Rechnung/)).toBeNull();
  });
});

describe("InvoiceFormV2 payment plan", () => {
  const quote: InvoiceDraft = {
    ...emptyQuoteDraft(3, "2026-10-23"),
    ust_enabled: true,
    vat_rate: 19,
    items: [{ description: "Website", quantity: 1, unit_price: 1000 }],
  };
  const percent = (n: number) => screen.getByLabelText(`Prozent Rate ${n}`) as HTMLInputElement;
  const occasion = (n: number) => screen.getByLabelText(`Anlass Rate ${n}`) as HTMLInputElement;

  it("adds installments with percent and occasion and shows each amount from the gross total", () => {
    render(<Harness initial={quote} />);
    fireEvent.click(screen.getByRole("button", { name: "Rate hinzufügen" }));
    fireEvent.change(percent(1), { target: { value: "50" } });
    fireEvent.change(occasion(1), { target: { value: "bei Auftrag" } });
    fireEvent.click(screen.getByRole("button", { name: "Rate hinzufügen" }));
    fireEvent.change(occasion(2), { target: { value: "nach Livegang" } });

    // the second installment starts with what is left to 100 %
    expect(percent(2).value).toBe("50");
    expect(screen.getAllByText("595,00 €")).toHaveLength(2);
    expect(screen.queryByText(/ergeben zusammen/)).toBeNull();
  });

  it("warns when the installments do not add up to 100 percent", () => {
    render(<Harness initial={{ ...quote, payment_plan: [{ percent: 30, label: "bei Auftrag" }] }} />);
    expect(screen.getByRole("status").textContent).toContain("ergeben zusammen 30 %, nicht 100 %");
  });

  it("moves and removes installments", () => {
    render(
      <Harness
        initial={{
          ...quote,
          payment_plan: [
            { percent: 30, label: "bei Auftrag" },
            { percent: 70, label: "nach Livegang" },
          ],
        }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Rate 2 nach oben" }));
    expect(occasion(1).value).toBe("nach Livegang");
    expect(occasion(2).value).toBe("bei Auftrag");

    fireEvent.click(screen.getByRole("button", { name: "Rate 1 entfernen" }));
    expect(occasion(1).value).toBe("bei Auftrag");
    expect(screen.queryByLabelText("Anlass Rate 2")).toBeNull();
  });

  it("invoices have no payment plan", () => {
    render(<Harness initial={base} />);
    expect(screen.queryByText("Zahlungsplan")).toBeNull();
    expect(screen.queryByRole("button", { name: "Rate hinzufügen" })).toBeNull();
  });
});
