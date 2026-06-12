/**
 * @schema SummaryCard
 * @purpose Invoice financial summary with subtotal, tax, discount, and total due
 * @input {number} subtotal - Net subtotal amount
 * @input {number} taxRate - Tax percentage (0-100)
 * @input {boolean} ustEnabled - Whether VAT is applied
 * @input {number} discount - Discount amount (always 0 for now)
 * @output Renders summary card with line-by-line breakdown and prominent total
 * @tokens Uses: card-bg, card-border, card-radius, card-shadow, color-text-primary, color-text-muted
 */

interface SummaryCardProps {
  subtotal: number;
  taxRate: number;
  ustEnabled: boolean;
  discount?: number;
}

export function SummaryCard({ subtotal, taxRate, ustEnabled, discount = 0 }: SummaryCardProps) {
  const taxAmount = ustEnabled ? subtotal * (taxRate / 100) : 0;
  const total = subtotal + taxAmount - discount;

  const fmt = (n: number) =>
    n.toLocaleString("de-DE", { minimumFractionDigits: 2 }) + " €";

  return (
    <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-[var(--card-radius)] shadow-[var(--card-shadow)] p-5">
      <h3 className="text-base font-semibold text-[var(--color-text-primary)] mb-4 border-b border-[var(--color-border)] pb-3">
        Zusammenfassung
      </h3>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-[var(--color-text-muted)]">Nettobetrag</span>
          <span className="font-mono text-[var(--color-text-primary)]">{fmt(subtotal)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[var(--color-text-muted)]">
            USt ({taxRate}%)
          </span>
          <span className="font-mono text-[var(--color-text-primary)]">{fmt(taxAmount)}</span>
        </div>
        <div className="flex justify-between pb-3 border-b border-[var(--color-border)]">
          <span className="text-[var(--color-text-muted)]">Rabatt</span>
          <span className="font-mono text-[var(--color-success)]">-{fmt(discount)}</span>
        </div>
        <div className="flex justify-between items-center pt-1">
          <span className="text-base font-bold text-[var(--color-text-primary)]">Gesamtbetrag</span>
          <span className="font-mono text-xl font-bold text-[var(--color-text-primary)]">{fmt(total)}</span>
        </div>
      </div>
    </div>
  );
}
