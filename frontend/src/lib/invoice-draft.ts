import type { InvoiceDraft } from "./schemas/invoice";

/** Payment term printed on every invoice and email. Keep in step with PAYMENT_TERM_DAYS in the backend. */
export const PAYMENT_TERM_DAYS = 5;

/** The due date as DD.MM.YYYY for an ISO invoice date, or "" when the date is not set. */
export function dueDateLabel(isoDate: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate);
  if (!match) return "";
  const due = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + PAYMENT_TERM_DAYS));
  const day = String(due.getUTCDate()).padStart(2, "0");
  const month = String(due.getUTCMonth() + 1).padStart(2, "0");
  return `${day}.${month}.${due.getUTCFullYear()}`;
}

/** What is still missing before the invoice can be created, in the order a person would fix it. */
export function invoiceDraftProblems(draft: InvoiceDraft): string[] {
  const problems: string[] = [];
  if (!(draft.customer_id > 0)) problems.push("Kunde auswählen");
  if (draft.items.length === 0) problems.push("mindestens eine Position anlegen");
  draft.items.forEach((item, index) => {
    const label = `Position ${index + 1}`;
    if (!item.description.trim()) problems.push(`${label} beschreiben`);
    else if (!(item.quantity > 0)) problems.push(`${label}: Menge größer 0 eintragen`);
    else if (item.unit_price < 0) problems.push(`${label}: Preis darf nicht negativ sein`);
  });
  return problems;
}
