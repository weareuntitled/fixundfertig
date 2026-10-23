import { describe, expect, it } from "vitest";
import { dueDateLabel, invoiceDraftProblems, PAYMENT_TERM_DAYS } from "./invoice-draft";
import { emptyInvoiceDraft } from "./schemas/invoice";

describe("dueDateLabel", () => {
  it("adds the payment term and crosses month ends", () => {
    expect(PAYMENT_TERM_DAYS).toBe(5);
    expect(dueDateLabel("2026-10-23")).toBe("28.10.2026");
    expect(dueDateLabel("2026-10-29")).toBe("03.11.2026");
  });
  it("is empty without a date", () => {
    expect(dueDateLabel("")).toBe("");
  });
});

describe("invoiceDraftProblems", () => {
  const draft = { ...emptyInvoiceDraft(3), items: [{ description: "DJ-Set", quantity: 1, unit_price: 400 }] };

  it("is empty for a complete draft", () => {
    expect(invoiceDraftProblems(draft)).toEqual([]);
  });
  it("asks for the customer and a position first", () => {
    expect(invoiceDraftProblems(emptyInvoiceDraft(0))).toEqual(["Kunde auswählen", "mindestens eine Position anlegen"]);
  });
  it("names the position that is incomplete", () => {
    const items = [
      { description: "DJ-Set", quantity: 1, unit_price: 400 },
      { description: "  ", quantity: 1, unit_price: 10 },
      { description: "Technik", quantity: 0, unit_price: 10 },
      { description: "Rabatt", quantity: 1, unit_price: -5 },
    ];
    expect(invoiceDraftProblems({ ...draft, items })).toEqual([
      "Position 2 beschreiben",
      "Position 3: Menge größer 0 eintragen",
      "Position 4: Preis darf nicht negativ sein",
    ]);
  });
});
