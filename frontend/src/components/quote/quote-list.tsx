/**
 * @schema QuoteList
 * @purpose Quote rows: number, customer, amount, valid until, status
 * @input {InvoiceRead[]} quotes - Quotes from GET /api/invoices?document_type=QUOTE
 * @output One card per quote linking to /quotes/$id, or an empty state
 */
import { Link } from "@tanstack/react-router";
import { FileSignature } from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";
import type { InvoiceRead } from "@/lib/schemas/invoice";
import { quoteDisplayStatus } from "@/lib/quote-status";

const eur = (n: number) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

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
        return (
          <Link
            key={quote.id}
            to="/quotes/$id"
            params={{ id: String(quote.id) }}
            className="group flex min-h-[44px] items-stretch overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-white transition-all duration-150 hover:border-[var(--color-border-strong)] hover:shadow-[0_2px_12px_rgba(0,0,0,0.04)]"
          >
            <div className="w-1 shrink-0 bg-[var(--color-gray-300)]" />
            <div className="flex flex-1 flex-wrap items-center gap-x-5 gap-y-1 px-5 py-3.5">
              <div className="w-28 shrink-0">
                <span className="font-mono text-[12.5px] font-semibold text-[var(--color-text-primary)]">
                  {quote.nr || `#${quote.id}`}
                </span>
                <div className="mt-0.5 text-[11.5px] text-[var(--color-text-tertiary)]">
                  {validUntil ? `gültig bis ${validUntil}` : "—"}
                </div>
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[14px] font-medium text-[var(--color-text-primary)]">
                  {quote.recipient_name || `Kunde #${quote.customer_id}`}
                </div>
                {quote.subject && (
                  <div className="mt-0.5 truncate text-[12.5px] text-[var(--color-text-tertiary)]">{quote.subject}</div>
                )}
              </div>
              <div className="text-right font-mono text-[15px] font-semibold tabular-nums text-[var(--color-text-primary)]">
                {eur(quote.total_brutto)}
              </div>
              <div className="w-24 shrink-0 text-right">
                <StatusBadge status={quoteDisplayStatus(quote)} />
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
