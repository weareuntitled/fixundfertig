/**
 * @schema QuoteList
 * @purpose Quote rows: number, customer, amount, valid until, status and how much is billed already
 * @input {InvoiceRead[]} quotes - Quotes from GET /api/invoices?document_type=QUOTE
 * @output One card per quote linking to /quotes/$id, or an empty state
 */
import { Link } from "@tanstack/react-router";
import { FileSignature } from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";
import type { InvoiceRead } from "@/lib/schemas/invoice";
import { quoteDisplayStatus } from "@/lib/quote-status";
import { eur, settlementLabel, settlementPercent } from "./quote-ui";

/** DD.MM.YYYY for an ISO date, or "" when it is not set. */
export function germanDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return match ? `${match[3]}.${match[2]}.${match[1]}` : "";
}

export function QuoteList({ quotes }: { quotes: InvoiceRead[] }) {
  if (quotes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-[12px] border border-dashed border-[var(--color-border)] bg-white py-16">
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-gray-50)]">
          <FileSignature size={20} className="text-[var(--color-text-tertiary)]" />
        </div>
        <p className="text-[15px] font-medium text-[var(--color-text-primary)]">Noch keine Angebote</p>
        <p className="mt-1 text-[13px] text-[var(--color-text-tertiary)]">Schreibe dein erstes Angebot</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {quotes.map((quote) => {
        const validUntil = germanDate(quote.valid_until);
        const percent = settlementPercent(quote.settlement);
        return (
          <Link
            key={quote.id}
            to="/quotes/$id"
            params={{ id: String(quote.id) }}
            className="group flex min-h-[44px] items-stretch overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-white transition-all duration-150 hover:border-[var(--color-border-strong)] hover:shadow-[0_2px_12px_rgba(0,0,0,0.04)]"
          >
            <div className="w-1 shrink-0 bg-[var(--color-gray-300)]" />
            {/* Am Handy: Kunde und Betreff lesbar, Betrag und Status unten (#498). */}
            <div className="flex flex-1 flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 md:gap-x-5 md:px-5 md:py-3.5">
              <div className="order-2 w-full md:order-none md:w-28 md:shrink-0">
                <span className="font-mono text-[12.5px] font-semibold text-[var(--color-text-primary)]">
                  {quote.nr || `#${quote.id}`}
                </span>
                <div className="mt-0.5 text-[11.5px] text-[var(--color-text-tertiary)]">
                  {validUntil ? `gültig bis ${validUntil}` : "—"}
                </div>
              </div>
              <div className="order-1 w-full min-w-0 md:order-none md:w-auto md:flex-1">
                <div className="text-[14px] font-medium text-[var(--color-text-primary)] md:truncate">
                  {quote.recipient_name || `Kunde #${quote.customer_id}`}
                </div>
                {quote.subject && (
                  <div className="mt-0.5 text-[12.5px] text-[var(--color-text-tertiary)] md:truncate">{quote.subject}</div>
                )}
                <div className="mt-1 flex items-center gap-2 text-[12px] text-[var(--color-text-tertiary)]">
                  <span
                    className="h-1.5 w-16 shrink-0 overflow-hidden rounded-full bg-[var(--color-gray-200)]"
                    aria-hidden="true"
                  >
                    <span
                      className="block h-full rounded-full bg-[var(--color-brand-text)]"
                      style={{ width: `${percent}%` }}
                    />
                  </span>
                  <span>{settlementLabel(quote.settlement)}</span>
                </div>
              </div>
              <div className="order-3 grow whitespace-nowrap text-right font-mono text-[15px] font-semibold tabular-nums text-[var(--color-text-primary)] md:order-none md:grow-0">
                {eur(quote.total_brutto)}
              </div>
              <div className="order-4 w-24 shrink-0 text-right md:order-none">
                <StatusBadge status={quoteDisplayStatus(quote)} />
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
