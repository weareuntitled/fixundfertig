/**
 * @schema NewQuotePage
 * @purpose Quote creation with the invoice form plus "Gültig bis"
 * @output Saving creates a draft quote (the quote number is assigned now) and opens it.
 */
import { useEffect, useMemo, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { InvoiceFormV2 } from "@/components/forms/invoice-form-v2";
import { PageHeader } from "@/components/ui/page-header";
import { PdfPreviewModal } from "@/components/ui/pdf-preview-modal";
import { useInvoicePreview } from "@/lib/use-invoice-preview";
import { useCompany, type Company } from "@/lib/use-company";
import { useNotification } from "@/lib/use-notifications";
import { invoiceDraftProblems } from "@/lib/invoice-draft";
import { emptyQuoteDraft, type InvoiceDraft } from "@/lib/schemas/invoice";
import { api } from "@/lib/api";

export const Route = createFileRoute("/_app/quotes/new")({
  component: NewQuotePage,
});

interface CreatedQuote {
  id: number;
  nr?: string;
}

/** A new quote starts without a customer and follows the company's VAT status. */
function initialDraft(company: Company | undefined): InvoiceDraft {
  const smallBusiness = Boolean(company?.is_small_business);
  return { ...emptyQuoteDraft(0), ust_enabled: !smallBusiness, vat_rate: smallBusiness ? 0 : 19 };
}

function NewQuotePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { notify } = useNotification();
  const { data: company, isLoading: companyLoading } = useCompany();
  const [draft, setDraft] = useState<InvoiceDraft | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const preview = useInvoicePreview(draft ?? emptyQuoteDraft(0), 800);
  const previewUrl = useMemo(() => (preview.data ? URL.createObjectURL(preview.data) : null), [preview.data]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  useEffect(() => {
    if (!companyLoading && !draft) setDraft(initialDraft(company));
  }, [companyLoading, company, draft]);

  const save = useMutation({
    mutationFn: (payload: InvoiceDraft) =>
      api.post<CreatedQuote>("/api/invoices", { ...payload, document_type: "QUOTE", status: "DRAFT" }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      notify("success", `Angebot ${data.nr ?? ""} gespeichert.`);
      void navigate({ to: "/quotes/$id", params: { id: String(data.id) } });
    },
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
  const hintId = "create-hint";
  const previewReady = draft.items.length > 0 && draft.customer_id > 0;

  return (
    <div className="animate-fade-in pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
      <PageHeader
        backTo="/quotes"
        backLabel="Angebote"
        title="Neues Angebot"
        subtitle="Kunde, Positionen und „gültig bis“ erfassen."
        actions={
          <>
            <button
              type="button"
              onClick={() => setPreviewOpen(true)}
              disabled={!previewReady}
              title={previewReady ? undefined : "Erst Kunde wählen und eine Position anlegen"}
              className="min-h-[44px] rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-white px-[var(--space-md)] py-[var(--space-xs)] text-[14px] font-semibold text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-container-low)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              PDF-Vorschau
            </button>
            <button
              type="button"
              onClick={() => save.mutate(draft)}
              disabled={!ready || save.isPending}
              aria-describedby={ready ? undefined : hintId}
              className="min-h-[44px] rounded-[var(--radius-lg)] bg-[#001a42] px-[var(--space-md)] py-[var(--space-xs)] text-[14px] font-semibold text-white shadow-sm transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {save.isPending ? "Speichere…" : "Angebot speichern"}
            </button>
          </>
        }
      />

      {!ready && (
        <p id={hintId} role="status" className="-mt-4 mb-[var(--space-md)] text-[13px] text-[var(--color-text-secondary)]">
          Noch nötig: {problems.join(" · ")}
        </p>
      )}

      {save.error && (
        <div role="alert" className="mb-[var(--space-md)] rounded-[var(--radius-lg)] border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-600">
          <strong>Das hat nicht geklappt.</strong>{" "}
          {save.error instanceof Error ? save.error.message : "Unbekannter Fehler."} Deine Eingaben sind noch da, du kannst es noch einmal versuchen.
        </div>
      )}

      <div className="rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white p-[var(--space-xl)] shadow-[0_8px_30px_rgba(0,0,0,0.02)]">
        <InvoiceFormV2 value={draft} onChange={setDraft} />
      </div>

      {/* Am Handy steht der Speichern-Knopf auch am Ende des Formulars (#498). */}
      <div className="mt-[var(--space-lg)] md:hidden">
        <button
          type="button"
          data-testid="quote-save-end"
          onClick={() => save.mutate(draft)}
          disabled={!ready || save.isPending}
          aria-describedby={ready ? undefined : hintId}
          className="min-h-[44px] w-full rounded-[var(--radius-lg)] bg-[#001a42] px-[var(--space-md)] py-[var(--space-xs)] text-[14px] font-semibold text-white shadow-sm transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {save.isPending ? "Speichere…" : "Angebot speichern"}
        </button>
      </div>

      <PdfPreviewModal
        open={previewOpen}
        pdfUrl={previewUrl}
        invoiceNr="Entwurf"
        documentType="QUOTE"
        onClose={() => setPreviewOpen(false)}
      />
    </div>
  );
}
