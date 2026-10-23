import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InvoiceFormV2 } from "./invoice-form-v2";
import { emptyInvoiceDraft, type InvoiceDraft } from "@/lib/schemas/invoice";

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
