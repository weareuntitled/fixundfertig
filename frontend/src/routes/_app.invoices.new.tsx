/**
 * @schema NewInvoicePage
 * @purpose Invoice creation: form, live PDF preview, draft or final creation
 * @output Header with three actions, a line that says what is still missing, one form card.
 *         Creating asks for confirmation (the number is assigned) and opens the new invoice.
 */
import { useEffect, useMemo, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { InvoiceFormV2 } from "@/components/forms/invoice-form-v2";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PageHeader } from "@/components/ui/page-header";
import { PdfPreviewModal } from "@/components/ui/pdf-preview-modal";
import { useInvoicePreview } from "@/lib/use-invoice-preview";
import { useCompany, type Company } from "@/lib/use-company";
import { useNotification } from "@/lib/use-notifications";
import { invoiceDraftProblems } from "@/lib/invoice-draft";
import { emptyInvoiceDraft, type InvoiceDraft } from "@/lib/schemas/invoice";
import { api } from "@/lib/api";

export const Route = createFileRoute("/_app/invoices/new")({
  component: NewInvoicePage,
});

interface CreatedInvoice {
  id: number;
  nr?: string;
}

/** A new invoice starts without a customer and follows the company's VAT status. */
function initialDraft(company: Company | undefined): InvoiceDraft {
  const smallBusiness = Boolean(company?.is_small_business);
  return { ...emptyInvoiceDraft(0), ust_enabled: !smallBusiness, vat_rate: smallBusiness ? 0 : 19 };
}

const SECONDARY_BUTTON =
  "rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-white px-[var(--space-md)] py-[var(--space-xs)] text-[14px] font-semibold text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-container-low)] disabled:cursor-not-allowed disabled:opacity-50";

function NewInvoicePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { notify } = useNotification();
  const { data: company, isLoading: companyLoading } = useCompany();
  const [draft, setDraft] = useState<InvoiceDraft | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  useEffect(() => {
    if (!companyLoading && !draft) setDraft(initialDraft(company));
  }, [companyLoading, company, draft]);

  const preview = useInvoicePreview(draft ?? emptyInvoiceDraft(0), 800);
  const previewUrl = useMemo(
    () => (preview.data ? URL.createObjectURL(preview.data) : null),
    [preview.data],
  );

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const created = (message: string) => (data: CreatedInvoice) => {
    qc.invalidateQueries({ queryKey: ["invoices"] });
    notify("success", message.replace("{nr}", data.nr ?? ""));
    setConfirmOpen(false);
    void navigate({ to: "/invoices/$id", params: { id: String(data.id) } });
  };

  const submit = useMutation({
    mutationFn: (payload: InvoiceDraft) => api.post<CreatedInvoice>("/api/invoices", payload),
    onSuccess: created("Rechnung {nr} erstellt."),
    onError: () => setConfirmOpen(false),
  });

  const saveDraft = useMutation({
    mutationFn: (payload: InvoiceDraft) => api.post<CreatedInvoice>("/api/invoices", { ...payload, status: "DRAFT" }),
    onSuccess: created("Entwurf {nr} gespeichert."),
  });

  if (!draft) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-brand-text)]" />
      </div>
    );
  }

  const problems = invoiceDraftProblems(draft);
  const ready = problems.length === 0;
  const previewReady = draft.items.length > 0 && draft.customer_id > 0;
  const busy = submit.isPending || saveDraft.isPending;
  const failure = submit.error ?? saveDraft.error;
  const hintId = "create-hint";

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Rechnung erstellen"
        subtitle="Kunde, Datum und Positionen erfassen."
        actions={
          <>
            <button
              type="button"
              onClick={() => setPreviewOpen(true)}
              disabled={!previewReady}
              title={previewReady ? undefined : "Erst Kunde wählen und eine Position anlegen"}
              className={`${SECONDARY_BUTTON} flex items-center gap-2`}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]" aria-hidden="true">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              PDF-Vorschau
            </button>
            <button
              type="button"
              onClick={() => saveDraft.mutate(draft)}
              disabled={!ready || busy}
              aria-describedby={ready ? undefined : hintId}
              className={SECONDARY_BUTTON}
            >
              {saveDraft.isPending ? "Speichere…" : "Als Entwurf speichern"}
            </button>
            <button
              type="button"
              onClick={() => setConfirmOpen(true)}
              disabled={!ready || busy}
              aria-describedby={ready ? undefined : hintId}
              className="rounded-[var(--radius-lg)] bg-[#001a42] px-[var(--space-md)] py-[var(--space-xs)] text-[14px] font-semibold text-white shadow-sm transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Rechnung erstellen
            </button>
          </>
        }
      />

      {!ready && (
        <p id={hintId} role="status" className="-mt-4 mb-[var(--space-md)] text-[13px] text-[var(--color-text-secondary)]">
          Noch nötig: {problems.join(" · ")}
        </p>
      )}

      {failure && (
        <div role="alert" className="mb-[var(--space-md)] rounded-[var(--radius-lg)] border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-600">
          <strong>Das hat nicht geklappt.</strong>{" "}
          {failure instanceof Error ? failure.message : "Unbekannter Fehler."} Deine Eingaben sind noch da, du kannst es noch einmal versuchen.
        </div>
      )}

      <div className="rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white p-[var(--space-xl)] shadow-[0_8px_30px_rgba(0,0,0,0.02)]">
        <InvoiceFormV2 value={draft} onChange={setDraft} />
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Rechnung erstellen?"
        message="Die Rechnungsnummer wird jetzt vergeben und lässt sich danach nicht mehr ändern. Gesendet wird noch nichts."
        confirmLabel={submit.isPending ? "Erstelle…" : "Erstellen"}
        pending={submit.isPending}
        onConfirm={() => submit.mutate(draft)}
        onCancel={() => setConfirmOpen(false)}
      />

      <PdfPreviewModal open={previewOpen} pdfUrl={previewUrl} invoiceNr="entwurf" onClose={() => setPreviewOpen(false)} />
    </div>
  );
}
