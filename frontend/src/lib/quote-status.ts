/**
 * Angebotsstatus für die Anzeige.
 *
 * Gespeichert werden nur DRAFT, SENT, ACCEPTED und REJECTED (Spalte `status`).
 * „Abgelaufen“ (EXPIRED) wird nie gespeichert: ein gesendetes Angebot, dessen
 * „gültig bis“ vor heute liegt. Ein angenommenes Angebot ist gesperrt.
 */
import type { InvoiceStatus } from "@/lib/schemas/invoice";

export type QuoteDisplayStatus = InvoiceStatus | "EXPIRED";

/** Heutiges Datum (lokale Zeit) als ISO-String YYYY-MM-DD. */
export function todayIso(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function quoteDisplayStatus(
  quote: { status: InvoiceStatus; valid_until: string },
  today: string = todayIso(),
): QuoteDisplayStatus {
  if (quote.status === "SENT" && quote.valid_until && quote.valid_until < today) return "EXPIRED";
  return quote.status;
}

export function isQuoteLocked(quote: { status: InvoiceStatus }): boolean {
  return quote.status === "ACCEPTED";
}

/**
 * „Gestellt": der Status ist weder Entwurf noch storniert.
 * Dieselbe Regel wie im Backend (`is_issued_status` in app/models/schema.py):
 * eine Abschlagsrechnung zählt erst ab dem Versand als gestellt.
 */
export function isIssuedStatus(status: InvoiceStatus | string): boolean {
  return status !== "DRAFT" && status !== "CANCELLED";
}
