import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SummaryCard } from "./summary-card";
import { invoiceReadSchema } from "@/lib/schemas/invoice";

describe("Zusammenfassung", () => {
  it("zeigt Netto, USt mit dem Satz des Belegs und Brutto aus totals", () => {
    const totals = { net: 300, vat_rate: 7, tax: 21, gross: 321, deductions: [], rest_net: 300, rest_tax: 21, payable: 321 };
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
    render(<SummaryCard totals={{ net: 300, vat_rate: 0, tax: 0, gross: 300, deductions: [], rest_net: 300, rest_tax: 0, payable: 300 }} />);
    expect(screen.queryByText(/USt/)).toBeNull();
    expect(screen.getAllByText("300,00 €")).toHaveLength(2);
  });

  it("zeigt bei einer Schlussrechnung Gesamtleistung, je Abschlag eine Abzugszeile und den Restbetrag", () => {
    const totals = {
      net: 4000, vat_rate: 19, tax: 760, gross: 4760,
      deductions: [
        { id: 2, nr: "RE-0042", date: "2026-10-01", net: 1200, tax: 228, gross: 1428 },
        { id: 3, nr: "RE-0043", date: "2026-11-01", net: 1000, tax: 190, gross: 1190 },
      ],
      rest_net: 1800, rest_tax: 342, payable: 2142,
    };
    const invoice = invoiceReadSchema.parse({ id: 1, customer_id: 1, is_final_invoice: true, total_brutto: 2142, totals });
    expect(invoice.totals).toEqual(totals);
    render(<SummaryCard totals={invoice.totals!} finalInvoice />);

    expect(screen.getByText("Gesamtleistung")).toBeTruthy();
    expect(screen.getByText("4.000,00 €")).toBeTruthy();
    expect(screen.getByText("760,00 €")).toBeTruthy();
    expect(screen.getByText("4.760,00 €")).toBeTruthy();
    const first = screen.getByRole("group", { name: /Abschlagsrechnung RE-0042/ });
    expect(within(first).getByText("−1.200,00 €")).toBeTruthy();
    expect(within(first).getByText("−228,00 €")).toBeTruthy();
    expect(screen.getByRole("group", { name: /Abschlagsrechnung RE-0043/ })).toBeTruthy();
    const rest = screen.getByRole("group", { name: "Restbetrag" });
    expect(within(rest).getByText("1.800,00 €")).toBeTruthy();
    expect(within(rest).getByText("342,00 €")).toBeTruthy();
    expect(within(rest).getByText("2.142,00 €")).toBeTruthy();
  });

  it("zeigt eine Schlussrechnung beim Kleinunternehmer ohne Steuerzeilen", () => {
    render(<SummaryCard finalInvoice totals={{
      net: 4000, vat_rate: 0, tax: 0, gross: 4000,
      deductions: [{ id: 2, nr: "RE-0042", date: "", net: 1200, tax: 0, gross: 1200 }],
      rest_net: 2800, rest_tax: 0, payable: 2800,
    }} />);

    expect(screen.getByText("Gesamtleistung")).toBeTruthy();
    expect(screen.queryByText(/USt/)).toBeNull();
    expect(screen.getByText("−1.200,00 €")).toBeTruthy();
    expect(within(screen.getByRole("group", { name: "Restbetrag" })).getAllByText("2.800,00 €").length).toBeGreaterThan(0);
  });
});
