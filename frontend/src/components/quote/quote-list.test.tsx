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

  it("shows a sent quote past its valid-until date as expired", async () => {
    await renderInRouter(<QuoteList quotes={[{ ...quote, status: "SENT", valid_until: "2020-01-31" }]} />);
    const row = await screen.findByRole("link", { name: /A-10000/ });
    expect(within(row).getByText("Abgelaufen")).toBeTruthy();
  });

  it.each([
    ["ACCEPTED", "Angenommen"],
    ["REJECTED", "Abgelehnt"],
  ] as const)("shows a %s quote with its German status", async (status, label) => {
    await renderInRouter(<QuoteList quotes={[{ ...quote, status, valid_until: "2020-01-31" }]} />);
    const row = await screen.findByRole("link", { name: /A-10000/ });
    expect(within(row).getByText(label)).toBeTruthy();
  });

  it("invites to write the first quote when there is none", async () => {
    await renderInRouter(<QuoteList quotes={[]} />);
    expect(await screen.findByText("Noch keine Angebote")).toBeTruthy();
  });

  it("shows the billing progress of a quote", async () => {
    await renderInRouter(
      <QuoteList
        quotes={[
          {
            ...quote,
            settlement: { billed_brutto: 143, total_brutto: 357, open_brutto: 214, billed_count: 1 },
          },
        ]}
      />,
    );
    const row = await screen.findByRole("link", { name: /A-10000/ });
    expect(within(row).getByText(/abgerechnet 143,00 € von 357,00 € · offen 214,00 €/)).toBeTruthy();
  });

  it("says that nothing is billed yet", async () => {
    await renderInRouter(<QuoteList quotes={[{ ...quote, settlement: { billed_brutto: 0, total_brutto: 300, open_brutto: 300, billed_count: 0 } }]} />);
    const row = await screen.findByRole("link", { name: /A-10000/ });
    expect(within(row).getByText("noch nichts abgerechnet")).toBeTruthy();
  });
});
