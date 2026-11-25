import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QuoteList } from "./quote-list";
import { invoiceReadSchema } from "@/lib/schemas/invoice";
import { renderInRouter } from "@/test/render-in-router";

const quote = invoiceReadSchema.parse({
  id: 7,
  customer_id: 3,
  document_type: "QUOTE",
  nr: "A-10000",
  title: "Angebot",
  date: "2026-10-23",
  valid_until: "2026-11-22",
  recipient_name: "Club Beispiel",
  total_brutto: 300,
  status: "DRAFT",
});

describe("QuoteList", () => {
  it("shows number, customer, amount, valid until and status per quote", async () => {
    await renderInRouter(<QuoteList quotes={[quote]} />);
    const row = await screen.findByRole("link", { name: /A-10000/ });
    expect(row.getAttribute("href")).toBe("/quotes/7");
    const cells = within(row);
    expect(cells.getByText("Club Beispiel")).toBeTruthy();
    expect(cells.getByText("300,00 €")).toBeTruthy();
    expect(cells.getByText(/gültig bis 22\.11\.2026/)).toBeTruthy();
    expect(cells.getByText("Entwurf")).toBeTruthy();
  });

  it("invites to write the first quote when there is none", async () => {
    await renderInRouter(<QuoteList quotes={[]} />);
    expect(await screen.findByText("Noch keine Angebote")).toBeTruthy();
  });
});
