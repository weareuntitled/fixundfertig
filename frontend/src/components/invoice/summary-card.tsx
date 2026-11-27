/**
 * @schema SummaryCard
 * @purpose Invoice financial summary: net, VAT with the document's rate, and gross;
 *   for a Schlussrechnung the Gesamtleistung, one line per deducted down payment and the Restbetrag
 * @input {TotalsRead} totals - Belegsummen from the API; the card does not calculate
 * @input {boolean} finalInvoice - render the Schlussrechnung layout (Gesamtleistung, Abzüge, Restbetrag)
 * @output Renders summary card with line-by-line breakdown and prominent total
 * @tokens Uses: card-bg, card-border, card-radius, card-shadow, color-text-primary, color-text-muted
 */
import type { TotalsRead } from "@/lib/schemas/invoice";

interface SummaryCardProps {
  totals: TotalsRead;
  finalInvoice?: boolean;
}

const fmt = (n: number) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

const formatDate = (iso: string) => {
  const [y, m, d] = iso.split("-");
  return y && m && d ? `${d}.${m}.${y}` : iso;
};

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <span className={strong ? "font-semibold text-[var(--color-text-primary)]" : "text-[var(--color-text-muted)]"}>{label}</span>
      <span className={`font-mono text-[var(--color-text-primary)] ${strong ? "font-semibold" : ""}`}>{value}</span>
    </div>
  );
}

export function SummaryCard({ totals, finalInvoice = false }: SummaryCardProps) {
  const withVat = totals.vat_rate > 0;
  const vatLabel = `USt (${totals.vat_rate.toLocaleString("de-DE")} %)`;

  return (
    <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-[var(--card-radius)] shadow-[var(--card-shadow)] p-5">
      <h3 className="text-base font-semibold text-[var(--color-text-primary)] mb-4 border-b border-[var(--color-border)] pb-3">
        {finalInvoice ? "Abrechnung" : "Zusammenfassung"}
      </h3>

      {finalInvoice ? (
        <div className="space-y-4 text-sm">
          <div role="group" aria-label="Gesamtleistung" className="space-y-1">
            <Row label="Gesamtleistung" value={fmt(totals.gross)} strong />
            {withVat && (
              <>
                <Row label="Netto" value={fmt(totals.net)} />
                <Row label={vatLabel} value={fmt(totals.tax)} />
              </>
            )}
          </div>

          {totals.deductions.map((d) => {
            const label = `Abzüglich Abschlagsrechnung ${d.nr}${d.date ? ` vom ${formatDate(d.date)}` : ""}`;
            return (
              <div key={d.id} role="group" aria-label={label} className="space-y-1">
                <p className="text-[var(--color-text-primary)]">{label}</p>
                <Row label="Netto" value={`−${fmt(d.net)}`} />
                {withVat && <Row label="USt" value={`−${fmt(d.tax)}`} />}
              </div>
            );
          })}

          <div role="group" aria-label="Restbetrag" className="space-y-1 pt-3 border-t border-[var(--color-border)]">
            {withVat && (
              <>
                <Row label="Netto" value={fmt(totals.rest_net)} />
                <Row label={vatLabel} value={fmt(totals.rest_tax)} />
              </>
            )}
            <div className="flex justify-between items-center pt-1">
              <span className="text-base font-bold text-[var(--color-text-primary)]">Restbetrag</span>
              <span className="font-mono text-xl font-bold text-[var(--color-text-primary)]">{fmt(totals.payable)}</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-2 text-sm">
          <Row label="Nettobetrag" value={fmt(totals.net)} />
          {withVat && <Row label={vatLabel} value={fmt(totals.tax)} />}
          <div className="flex justify-between items-center pt-3 border-t border-[var(--color-border)]">
            <span className="text-base font-bold text-[var(--color-text-primary)]">Gesamtbetrag</span>
            <span className="font-mono text-xl font-bold text-[var(--color-text-primary)]">{fmt(totals.gross)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
