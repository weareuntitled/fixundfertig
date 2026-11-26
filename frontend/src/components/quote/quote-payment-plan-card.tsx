/**
 * @schema QuotePaymentPlanCard
 * @purpose Payment plan of a saved quote: read it (percent, occasion, amount), edit it while the quote is
 *   open, and bill a single installment as a down-payment invoice (#490). The button names the amount
 *   and leads to the invoice afterwards (#499).
 * @input {number} quoteId
 * @input {number} gross - Gross total; amounts in the editor are computed from it
 * @input {PaymentInstallmentRead[]} plan - Installments with amounts as the API returns them
 * @input {boolean} locked - Accepted quotes cannot be changed (but their installments stay billable)
 * @input {boolean} readOnly - Rejected quotes are read-only: nothing to change, nothing to bill
 * @input {LinkedInvoice[]} invoices - Invoices of this quote; each down payment carries its installment index
 * @input {QuoteBilling} billing - Server rules of the quote (#495): what may be billed and why not
 * @input {(index: number) => void} onBillRate - Bills a rate; the page uses it to ask first (#499)
 * @output Saving PUTs `payment_plan`; billing POSTs `installment_index` to /api/invoices/{id}/down-payment
 */
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Pencil } from "lucide-react";
import { PaymentPlanEditor } from "./payment-plan-editor";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import { percentLabel, planPercentTotal } from "@/lib/payment-plan";
import { useBillDownPayment } from "@/lib/use-quote-billing";
import { useNotification } from "@/lib/use-notifications";
import { SECONDARY_BUTTON, eur } from "./quote-ui";
import type {
  LinkedInvoice,
  PaymentInstallment,
  PaymentInstallmentRead,
  QuoteBilling,
} from "@/lib/schemas/invoice";

interface QuotePaymentPlanCardProps {
  quoteId: number;
  gross: number;
  plan: PaymentInstallmentRead[];
  locked: boolean;
  readOnly?: boolean;
  invoices?: LinkedInvoice[];
  billing?: QuoteBilling | null;
  /** Bills a rate; wenn die Seite sie nicht vorgibt, passiert das hier. */
  onBillRate?: (installmentIndex: number) => void;
  billingPending?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
}

export function QuotePaymentPlanCard({
  quoteId,
  gross,
  plan,
  locked,
  readOnly = false,
  invoices = [],
  billing = null,
  onBillRate,
  billingPending = false,
  onDirtyChange,
}: QuotePaymentPlanCardProps) {
  const qc = useQueryClient();
  const { notify } = useNotification();
  const [draft, setDraft] = useState<PaymentInstallment[] | null>(null);
  const dirty = draft !== null && JSON.stringify(draft) !== JSON.stringify(plan.map(({ percent, label }) => ({ percent, label })));
  useEffect(() => {
    onDirtyChange?.(dirty);
    return () => onDirtyChange?.(false);
  }, [dirty, onDirtyChange]);
  const { billRate, isPending: ownBillingPending } = useBillDownPayment(quoteId);

  // Only an active (not cancelled) down payment blocks its installment.
  const billedRates = new Map<number, LinkedInvoice>();
  for (const invoice of invoices) {
    if (invoice.installment_index != null && invoice.status !== "CANCELLED") {
      billedRates.set(invoice.installment_index, invoice);
    }
  }

  // Der Server entscheidet, was abrechenbar ist (#495). Ist eine Rate gesperrt,
  // steht der Grund sichtbar unter den Raten — nicht im Tooltip.
  const downPaymentBlocked = billing && !billing.down_payment.allowed;
  const downPaymentReason = downPaymentBlocked ? billing?.down_payment.reason ?? "" : "";

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
  // Über 100 % fordert mehr als das Angebot: das lässt sich nicht speichern (#495).
  const overTotal = draft !== null && planPercentTotal(draft) > 100;
  const invalid = (draft ?? []).some((rate) => !(rate.percent > 0)) || overTotal;

  return (
    <div className="overflow-hidden rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white shadow-sm">
      {editing ? (
        <div className="p-[var(--space-lg)]">
          <PaymentPlanEditor value={draft} gross={gross} onChange={setDraft} />
          <div className="mt-[var(--space-md)] flex justify-end gap-[var(--space-xs)]">
            <button type="button" onClick={() => { if (!dirty || window.confirm("Ungespeicherte Eingaben verwerfen?")) setDraft(null); }} className={SECONDARY_BUTTON}>
              Abbrechen
            </button>
            <button
              type="button"
              disabled={invalid || save.isPending}
              onClick={() => save.mutate(draft)}
              className="inline-flex min-h-[44px] items-center rounded-[var(--radius-lg)] bg-[#001a42] px-[var(--space-md)] text-[14px] font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {save.isPending ? "Speichiere…" : "Speichern"}
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] px-[var(--space-lg)] py-[var(--space-sm)]">
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
            <>
              {downPaymentReason && (
                <p className="border-b border-[var(--color-border)] px-[var(--space-lg)] py-[var(--space-sm)] text-[14px] text-[var(--color-text-secondary)]">
                  <span className="font-semibold text-[var(--color-text-primary)]">Abschlag nicht möglich:</span>{" "}
                  {downPaymentReason}
                </p>
              )}
              <ol>
                {plan.map((rate, index) => {
                  const billed = billedRates.get(index);
                  const action = billed ? (
                    <span className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={billed.status} />
                      <Link
                        to="/invoices/$id"
                        params={{ id: String(billed.id) }}
                        className="inline-flex min-h-[44px] items-center gap-1.5 rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-[var(--color-surface-container-low)] px-[var(--space-md)] text-[14px] font-semibold text-[var(--color-text-primary)] hover:bg-[var(--color-surface-container-high)]"
                      >
                        Abschlagsrechnung {billed.nr || `#${billed.id}`}
                      </Link>
                    </span>
                  ) : readOnly || downPaymentBlocked ? (
                    <span className="text-[13px] text-[var(--color-text-secondary)]">nicht abrechenbar</span>
                  ) : (
                    <button
                      type="button"
                      disabled={billingPending || ownBillingPending}
                      onClick={() => (onBillRate ? onBillRate(index) : billRate(index))}
                      className={SECONDARY_BUTTON}
                    >
                      Abschlag {eur(rate.amount)} abrechnen
                    </button>
                  );
                  return (
                    <li
                      key={index}
                      data-testid="rate-row"
                      className="flex flex-col gap-2 border-b border-[var(--color-border)] px-[var(--space-lg)] py-2 last:border-b-0 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-3 sm:gap-y-1"
                    >
                      {/* Am Handy zweizeilig: oben Prozent und Anlass, unten Betrag und Aktion (#498). */}
                      <div className="flex min-w-0 items-baseline gap-3 sm:contents">
                        <span className="w-16 shrink-0 whitespace-nowrap font-mono text-[14px]">{percentLabel(rate.percent)}</span>
                        <span data-testid="rate-label" className="min-w-0 grow text-[14px] text-[var(--color-text-heading)]">{rate.label}</span>
                      </div>
                      <div className="flex flex-wrap items-center justify-between gap-2 sm:contents">
                        <span data-testid="rate-amount" className="whitespace-nowrap font-mono text-[14px] font-bold">{eur(rate.amount)}</span>
                        {action}
                      </div>
                    </li>
                  );
                })}
              </ol>
            </>
          )}
        </>
      )}
    </div>
  );
}
