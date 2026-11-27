/**
 * @schema SummaryCard
 * @purpose Invoice financial summary: net, VAT with the document's rate, and gross
 * @input {TotalsRead} totals - Belegsummen from the API; the card does not calculate
 * @output Renders summary card with line-by-line breakdown and prominent total
 * @tokens Uses: card-bg, card-border, card-radius, card-shadow, color-text-primary, color-text-muted
 */
import type { TotalsRead } from "@/lib/schemas/invoice";

interface SummaryCardProps {
  totals: TotalsRead;
}

const fmt = (n: number) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

export function SummaryCard({ totals }: SummaryCardProps) {
  return (
    <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-[var(--card-radius)] shadow-[var(--card-shadow)] p-5">
      <h3 className="text-base font-semibold text-[var(--color-text-primary)] mb-4 border-b border-[var(--color-border)] pb-3">
        Zusammenfassung
      </h3>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-[var(--color-text-muted)]">Nettobetrag</span>
          <span className="font-mono text-[var(--color-text-primary)]">{fmt(totals.net)}</span>
        </div>
        {totals.vat_rate > 0 && (
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">
              USt ({totals.vat_rate.toLocaleString("de-DE")} %)
            </span>
            <span className="font-mono text-[var(--color-text-primary)]">{fmt(totals.tax)}</span>
          </div>
        )}
        <div className="flex justify-between items-center pt-3 border-t border-[var(--color-border)]">
          <span className="text-base font-bold text-[var(--color-text-primary)]">Gesamtbetrag</span>
          <span className="font-mono text-xl font-bold text-[var(--color-text-primary)]">{fmt(totals.gross)}</span>
        </div>
      </div>
    </div>
  );
}
