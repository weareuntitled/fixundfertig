import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FinalBreakdown } from "./final-breakdown";
import { invoiceReadSchema } from "@/lib/schemas/invoice";

describe("Schlussrechnung", () => {
  it("übernimmt und zeigt Gesamtleistung, Abschläge und Restbetrag", () => {
    const breakdown = { net: 1000, tax: 190, gross: 1190, deductions: [{ id: 2, nr: "42", date: "2026-01-10", net: 400, tax: 76, total: 476 }], rest_net: 600, rest_tax: 114, rest: 714 };
    const invoice = invoiceReadSchema.parse({ id: 1, customer_id: 1, final_breakdown: breakdown });
    expect(invoice.final_breakdown).toEqual(breakdown);
    render(<FinalBreakdown breakdown={invoice.final_breakdown!} />);
    expect(screen.getByText("Gesamtleistung")).toBeTruthy();
    expect(screen.getByText(/Abschlagsrechnung 42/)).toBeTruthy();
    expect(screen.getByText("1.190,00 €")).toBeTruthy();
    expect(screen.getByText(/476,00 €/)).toBeTruthy();
    expect(screen.getByText("714,00 €")).toBeTruthy();
  });
});
