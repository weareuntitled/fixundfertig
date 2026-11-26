/**
 * @schema QuotePaymentPlanCard
 * @purpose Payment plan of a saved quote: read it (percent, occasion, amount), edit it while the quote is
 *   open, and bill a single installment as a down-payment invoice (#490)
 * @input {number} quoteId
 * @input {number} gross - Gross total; amounts in the editor are computed from it
 * @input {PaymentInstallmentRead[]} plan - Installments with amounts as the API returns them
 * @input {boolean} locked - Accepted quotes cannot be changed (but their installments stay billable)
 * @input {boolean} readOnly - Rejected quotes are read-only: nothing to change, nothing to bill
 * @input {LinkedInvoice[]} invoices - Invoices of this quote; each down payment carries its installment index
 * @output Saving PUTs `payment_plan`; billing POSTs `installment_index` to /api/invoices/{id}/down-payment
 */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { PaymentPlanEditor } from "./payment-plan-editor";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import { percentLabel } from "@/lib/payment-plan";
import { useCreateDownPayment } from "@/lib/use-invoices";
import { useNotification } from "@/lib/use-notifications";
import { SECONDARY_BUTTON, eur } from "./quote-ui";
import type {
  LinkedInvoice,
  PaymentInstallment,
  PaymentInstallmentRead,
} from "@/lib/schemas/invoice";

interface QuotePaymentPlanCardProps {
  quoteId: number;
  gross: number;
  plan: PaymentInstallmentRead[];
  locked: boolean;
  readOnly?: boolean;
  invoices?: LinkedInvoice[];
}

export function QuotePaymentPlanCard({
  quoteId,
  gross,
  plan,
  locked,
  readOnly = false,
  invoices = [],
}: QuotePaymentPlanCardProps) {
  const qc = useQueryClient();
  const { notify } = useNotification();
  const [draft, setDraft] = useState<PaymentInstallment[] | null>(null);
  const bill = useCreateDownPayment();

  // Only an active (not cancelled) down payment blocks its installment.
  const billedRates = new Map<number, LinkedInvoice>();
  for (const invoice of invoices) {
    if (invoice.installment_index != null && invoice.status !== "CANCELLED") {
      billedRates.set(invoice.installment_index, invoice);
    }
  }

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

  const editing = draft !== null && !locked && !readOnly;
  const invalid = (draft ?? []).some((rate) => !(rate.percent > 0));

  return (
    <div className="overflow-hidden rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white shadow-sm">
      {editing ? (
        <div className="p-[var(--space-lg)]">
          <PaymentPlanEditor value={draft} gross={gross} onChange={setDraft} />
          <div className="mt-[var(--space-md)] flex justify-end gap-[var(--space-xs)]">
            <button type="button" onClick={() => setDraft(null)} className={SECONDARY_BUTTON}>
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
            {!locked && !readOnly && (
              <button
                type="button"
                aria-label="Zahlungsplan bearbeiten"
                onClick={() => setDraft(plan.map(({ percent, label }) => ({ percent, label })))}
                className={SECONDARY_BUTTON}
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
              {plan.map((rate, index) => {
                const billed = billedRates.get(index);
                return (
                  <li key={index} className="flex items-center gap-3 border-b border-[var(--color-border)] px-[var(--space-lg)] py-2 last:border-b-0">
                    <span className="w-16 font-mono text-[14px]">{percentLabel(rate.percent)}</span>
                    <span className="min-w-0 flex-1 text-[14px] text-[var(--color-text-heading)]">{rate.label}</span>
                    <span className="font-mono text-[14px] font-bold">{eur(rate.amount)}</span>
                    {billed ? (
                      <span className="flex items-center gap-2">
                        <StatusBadge status={billed.status} />
                        <a
                          href={`/invoices/${billed.id}`}
                          className="inline-flex min-h-[44px] items-center gap-1.5 rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-[var(--color-surface-container-low)] px-[var(--space-md)] text-[14px] font-semibold text-[var(--color-text-primary)] hover:bg-[var(--color-surface-container-high)]"
                        >
                          Rechnung {billed.nr || `#${billed.id}`}
                        </a>
                      </span>
                    ) : readOnly ? (
                      <span className="text-[13px] text-[var(--color-text-secondary)]">nicht abrechenbar</span>
                    ) : (
                      <button
                        type="button"
                        disabled={bill.isPending}
                        onClick={() =>
                          bill.mutate(
                            { quoteId, installmentIndex: index },
                            {
                              onSuccess: (invoice) =>
                                notify(
                                  "success",
                                  invoice.nr
                                    ? `Abschlagsrechnung ${invoice.nr} angelegt`
                                    : "Abschlagsrechnung angelegt",
                                ),
                              onError: (err: Error) => notify("error", err.message),
                            },
                          )
                        }
                        className={SECONDARY_BUTTON}
                      >
                        Abschlagsrechnung
                      </button>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
        </>
      )}
    </div>
  );
}
