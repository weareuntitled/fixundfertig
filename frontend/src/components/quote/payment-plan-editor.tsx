/**
 * @schema PaymentPlanEditor
 * @purpose Edit a quote's payment plan: installments of percent + occasion, add/move/remove
 * @input {PaymentInstallment[]} value - Installments in order
 * @input {number} gross - Gross total the amounts are computed from (amounts are never stored)
 * @input {(next: PaymentInstallment[]) => void} onChange
 * @output A list with the amount per installment and a warning (not a block) when the sum is not 100 %
 */
import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";
import { installmentAmounts, planPercentTotal, percentLabel } from "@/lib/payment-plan";
import { ICON_BUTTON, INPUT, eur } from "./quote-ui";
import type { PaymentInstallment } from "@/lib/schemas/invoice";

interface PaymentPlanEditorProps {
  value: PaymentInstallment[];
  gross: number;
  onChange: (next: PaymentInstallment[]) => void;
}

export function PaymentPlanEditor({ value, gross, onChange }: PaymentPlanEditorProps) {
  const total = planPercentTotal(value);
  const amounts = installmentAmounts(gross, value.map((rate) => Number(rate.percent) || 0));

  const update = (index: number, patch: Partial<PaymentInstallment>) =>
    onChange(value.map((rate, i) => (i === index ? { ...rate, ...patch } : rate)));
  const move = (index: number, to: number) => {
    const next = [...value];
    const [rate] = next.splice(index, 1);
    next.splice(to, 0, rate);
    onChange(next);
  };
  const add = () => onChange([...value, { percent: Math.max(Math.round((100 - total) * 100) / 100, 0), label: "" }]);

  return (
    <section aria-labelledby="payment-plan-heading">
      <h3 id="payment-plan-heading" className="mb-1 text-[20px] font-semibold text-[var(--color-text-primary)]">
        Zahlungsplan
      </h3>
      <p className="mb-[var(--space-md)] text-[12px] text-[var(--color-text-muted)]">
        Optional. Raten in Prozent vom Gesamtbetrag, z. B. „50 % bei Auftrag“. Steht im PDF mit Betrag je Rate.
      </p>

      {value.length > 0 && (
        <ol className="space-y-[var(--space-xs)]">
          {value.map((rate, index) => {
            const number = index + 1;
            return (
              <li key={index} className="flex flex-wrap items-center gap-[var(--space-xs)] border-b border-[var(--color-border)] pb-[var(--space-xs)]">
                <div className="flex w-28 items-center gap-1">
                  <input
                    type="number"
                    inputMode="decimal"
                    aria-label={`Prozent Rate ${number}`}
                    aria-invalid={!(rate.percent > 0)}
                    min="0.01"
                    max="100"
                    step="any"
                    value={rate.percent}
                    onChange={(e) => update(index, { percent: Number(e.target.value) })}
                    className={`${INPUT} text-right font-mono`}
                  />
                  <span className="text-[14px] text-[var(--color-text-secondary)]">%</span>
                </div>
                <input
                  type="text"
                  aria-label={`Anlass Rate ${number}`}
                  value={rate.label}
                  maxLength={200}
                  placeholder="z. B. bei Auftrag"
                  onChange={(e) => update(index, { label: e.target.value })}
                  className={`${INPUT} min-w-[10rem] flex-1`}
                />
                <span className="w-28 text-right font-mono text-sm text-[var(--color-text-primary)]">{eur(amounts[index] ?? 0)}</span>
                <div className="flex">
                  <button type="button" aria-label={`Rate ${number} nach oben`} disabled={index === 0} onClick={() => move(index, index - 1)} className={ICON_BUTTON}>
                    <ArrowUp size={16} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Rate ${number} nach unten`}
                    disabled={index === value.length - 1}
                    onClick={() => move(index, index + 1)}
                    className={ICON_BUTTON}
                  >
                    <ArrowDown size={16} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Rate ${number} entfernen`}
                    onClick={() => onChange(value.filter((_, i) => i !== index))}
                    className={`${ICON_BUTTON} hover:bg-[var(--color-red-50)] hover:text-[var(--color-red-600)]`}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {value.length > 0 && Math.abs(total - 100) > 0.001 && (
        <p role="status" className="mt-[var(--space-xs)] rounded-[var(--radius)] bg-[var(--color-amber-50)] px-3 py-2 text-[13px] text-[var(--color-amber-700)]">
          Die Raten ergeben zusammen {percentLabel(total)}, nicht 100 %. Speichern geht trotzdem.
        </p>
      )}

      <button
        type="button"
        onClick={add}
        className="mt-[var(--space-sm)] flex min-h-[44px] items-center gap-[var(--space-xs)] text-[14px] font-semibold text-[var(--color-brand-text)] transition-colors hover:text-[var(--color-brand-text-hover)]"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]" aria-hidden="true">
          <path d="M12 5v14M5 12h14" />
        </svg>
        Rate hinzufügen
      </button>
    </section>
  );
}
