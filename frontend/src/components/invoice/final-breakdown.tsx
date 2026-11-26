import type { FinalBreakdownRead } from "@/lib/schemas/invoice";

const eur = (amount: number) => amount.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

export function FinalBreakdown({ breakdown }: { breakdown: FinalBreakdownRead }) {
  return (
    <section className="rounded-[var(--card-radius)] border border-[var(--card-border)] bg-white p-5 shadow-[var(--card-shadow)]">
      <h2 className="mb-4 text-base font-semibold">Abrechnung</h2>
      <div className="space-y-3 text-sm">
        <div className="flex justify-between gap-3"><span>Gesamtleistung</span><strong>{eur(breakdown.gross)}</strong></div>
        <p>Netto {eur(breakdown.net)} · USt {eur(breakdown.tax)}</p>
        {breakdown.deductions.map((item) => (
          <div key={item.id}>
            <div className="flex justify-between gap-3"><span>Abzüglich Abschlagsrechnung {item.nr}{item.date && ` vom ${item.date}`}</span><span>−{eur(item.total)}</span></div>
            <p>Netto {eur(item.net)} · USt {eur(item.tax)}</p>
          </div>
        ))}
        <div className="flex justify-between gap-3 border-t pt-3 font-bold"><span>Restbetrag</span><span>{eur(breakdown.rest)}</span></div>
        <p>Netto {eur(breakdown.rest_net)} · USt {eur(breakdown.rest_tax)}</p>
      </div>
    </section>
  );
}
