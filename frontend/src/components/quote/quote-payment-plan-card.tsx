/**
 * @schema QuotePaymentPlanCard
 * @purpose Payment plan of a saved quote: read it (percent, occasion, amount) and edit it while the quote is open
 * @input {number} quoteId
 * @input {number} gross - Gross total; amounts in the editor are computed from it
 * @input {PaymentInstallmentRead[]} plan - Installments with amounts as the API returns them
 * @input {boolean} locked - Accepted quotes cannot be changed
 * @output Saving PUTs `payment_plan` to /api/invoices/{id}; the stored PDF is re-rendered by the backend
 */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { PaymentPlanEditor } from "./payment-plan-editor";
import { api } from "@/lib/api";
import { percentLabel } from "@/lib/payment-plan";
import { useNotification } from "@/lib/use-notifications";
import type { PaymentInstallment, PaymentInstallmentRead } from "@/lib/schemas/invoice";

interface QuotePaymentPlanCardProps {
  quoteId: number;
  gross: number;
  plan: PaymentInstallmentRead[];
  locked: boolean;
}

const eur = (n: number) => `${n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
const BUTTON =
  "inline-flex min-h-[44px] items-center gap-1.5 rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-white px-[var(--space-md)] text-[14px] font-semibold text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-container-low)] disabled:cursor-not-allowed disabled:opacity-50";

export function QuotePaymentPlanCard({ quoteId, gross, plan, locked }: QuotePaymentPlanCardProps) {
  const qc = useQueryClient();
  const { notify } = useNotification();
  const [draft, setDraft] = useState<PaymentInstallment[] | null>(null);

  const save = useMutation({
    mutationFn: (payment_plan: PaymentInstallment[]) =>
      api.put(`/api/invoices/${quoteId}`, { payment_plan, reason: "Zahlungsplan geändert" }),
    onSuccess: () => {
      notify("success", "Zahlungsplan gespeichert");
      setDraft(null);
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["invoice-preview-pdf", quoteId] });
    },
    onError: (err: Error) => notify("error", err.message),
  });

  const editing = draft !== null && !locked;
  const invalid = (draft ?? []).some((rate) => !(rate.percent > 0));

  return (
    <div className="overflow-hidden rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white shadow-sm">
      {editing ? (
        <div className="p-[var(--space-lg)]">
          <PaymentPlanEditor value={draft} gross={gross} onChange={setDraft} />
          <div className="mt-[var(--space-md)] flex justify-end gap-[var(--space-xs)]">
            <button type="button" onClick={() => setDraft(null)} className={BUTTON}>
              Abbrechen
            </button>
            <button
              type="button"
              disabled={invalid || save.isPending}
              onClick={() => save.mutate(draft)}
              className="inline-flex min-h-[44px] items-center rounded-[var(--radius-lg)] bg-[#001a42] px-[var(--space-md)] text-[14px] font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {save.isPending ? "Speichere…" : "Speichern"}
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between border-b border-[var(--color-border)] px-[var(--space-lg)] py-[var(--space-sm)]">
            <h2 className="text-[20px] font-semibold text-[var(--color-text-heading)]">Zahlungsplan</h2>
            {!locked && (
              <button
                type="button"
                aria-label="Zahlungsplan bearbeiten"
                onClick={() => setDraft(plan.map(({ percent, label }) => ({ percent, label })))}
                className={BUTTON}
              >
                <Pencil size={14} /> Bearbeiten
              </button>
            )}
          </div>
          {plan.length === 0 ? (
            <p className="px-[var(--space-lg)] py-6 text-center text-[14px] text-[var(--color-text-secondary)]">
              Kein Zahlungsplan. Das PDF zeigt dann keinen Abschnitt dazu.
            </p>
          ) : (
            <ol>
              {plan.map((rate, index) => (
                <li key={index} className="flex items-center gap-3 border-b border-[var(--color-border)] px-[var(--space-lg)] py-2 last:border-b-0">
                  <span className="w-16 font-mono text-[14px]">{percentLabel(rate.percent)}</span>
                  <span className="min-w-0 flex-1 text-[14px] text-[var(--color-text-heading)]">{rate.label}</span>
                  <span className="font-mono text-[14px] font-bold">{eur(rate.amount)}</span>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </div>
  );
}
