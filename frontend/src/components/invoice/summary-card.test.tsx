import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SummaryCard } from "./summary-card";
import { invoiceReadSchema } from "@/lib/schemas/invoice";

describe("Zusammenfassung", () => {
  it("zeigt Netto, USt mit dem Satz des Belegs und Brutto aus totals", () => {
    const totals = { net: 300, vat_rate: 7, tax: 21, gross: 321, payable: 321 };
    const invoice = invoiceReadSchema.parse({ id: 1, customer_id: 1, total_brutto: 321, totals });
    expect(invoice.totals).toEqual(totals);
    render(<SummaryCard totals={invoice.totals!} />);
    expect(screen.getByText("300,00 €")).toBeTruthy();
    expect(screen.getByText("USt (7 %)")).toBeTruthy();
    expect(screen.getByText("21,00 €")).toBeTruthy();
    expect(screen.getByText("321,00 €")).toBeTruthy();
    expect(screen.queryByText(/19/)).toBeNull();
  });

  it("zeigt ohne USt (Kleinunternehmer oder 0 %) keine USt-Zeile", () => {
    render(<SummaryCard totals={{ net: 300, vat_rate: 0, tax: 0, gross: 300, payable: 300 }} />);
    expect(screen.queryByText(/USt/)).toBeNull();
    expect(screen.getAllByText("300,00 €")).toHaveLength(2);
  });
});
