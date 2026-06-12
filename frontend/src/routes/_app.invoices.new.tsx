/**
 * @schema NewInvoicePage
 * @purpose Invoice creation page matching Lumina Ledger HTML spec
 * @input None (creates new InvoiceDraft from empty state)
 * @output Renders page with header (3 buttons) and single white card with form
 * @tokens Uses: color-background, color-surface-card, color-border, color-text-*
 */
import { useEffect, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { InvoiceFormV2 } from "@/components/forms/invoice-form-v2";
import { PdfPreviewModal } from "@/components/ui/pdf-preview-modal";
import { useInvoicePreview } from "@/lib/use-invoice-preview";
import { emptyInvoiceDraft, type InvoiceDraft } from "@/lib/schemas/invoice";
import { useCustomer } from "@/lib/use-customers";
import { useCompany } from "@/lib/use-company";
import { api } from "@/lib/api";

export const Route = createFileRoute("/_app/invoices/new")({
  component: NewInvoicePage,
});

function NewInvoicePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [draft, setDraft] = useState<InvoiceDraft | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  useEffect(() => {
    setDraft(emptyInvoiceDraft(1));
  }, []);

  const customerId = draft?.customer_id ?? 0;
  const { data: customer } = useCustomer(customerId);
  const { data: company } = useCompany();

  const preview = useInvoicePreview(draft ?? emptyInvoiceDraft(1), 800);
  const previewUrl = preview.data ? URL.createObjectURL(preview.data) : null;

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const submit = useMutation({
    mutationFn: (payload: InvoiceDraft) =>
      api.post<unknown>("/api/invoices", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      void navigate({ to: "/invoices" });
    },
  });

  const saveDraft = useMutation({
    mutationFn: (payload: InvoiceDraft) =>
      api.post<unknown>("/api/invoices", { ...payload, status: "DRAFT" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      void navigate({ to: "/invoices" });
    },
  });

  if (!draft) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-brand-text)]" />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      {/* Page Header */}
      <div className="flex justify-between items-center mb-[var(--space-xl)]">
        <div>
          <h2 className="text-[32px] font-semibold text-[var(--color-text-heading)]">
            Rechnung erstellen
          </h2>
          <p className="text-[14px] text-[var(--color-text-secondary)] mt-1">
            Kunde, Zeitraum und Positionen erfassen.
          </p>
        </div>
        <div className="flex gap-[var(--space-sm)]">
          <button
            type="button"
            onClick={() => setPreviewOpen(true)}
            className="px-[var(--space-md)] py-[var(--space-xs)] border border-[var(--color-border-strong)] bg-white text-[var(--color-text-primary)] rounded-[var(--radius-lg)] text-[14px] font-semibold hover:bg-[var(--color-surface-container-low)] transition-colors flex items-center gap-2"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-[18px] h-[18px]">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
            PDF Vorschau
          </button>
          <button
            type="button"
            onClick={() => saveDraft.mutate(draft)}
            disabled={saveDraft.isPending}
            className="px-[var(--space-md)] py-[var(--space-xs)] border border-[var(--color-border-strong)] bg-white text-[var(--color-text-primary)] rounded-[var(--radius-lg)] text-[14px] font-semibold hover:bg-[var(--color-surface-container-lowest)] transition-colors disabled:opacity-50"
          >
            {saveDraft.isPending ? "Speichere..." : "Als Entwurf speichern"}
          </button>
          <button
            type="button"
            onClick={() => submit.mutate(draft)}
            disabled={submit.isPending || draft.items.length === 0}
            className="px-[var(--space-md)] py-[var(--space-xs)] bg-black text-white rounded-[var(--radius-lg)] text-[14px] font-semibold hover:bg-[var(--color-blue-990)] transition-colors shadow-sm disabled:opacity-50"
          >
            {submit.isPending ? "Speichere..." : "Finalisieren & Vorschau"}
          </button>
        </div>
      </div>

      {/* Error */}
      {(submit.isError || saveDraft.isError) && (
        <div className="mb-[var(--space-md)] rounded-[var(--radius-lg)] border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-600">
          <strong>Fehler:</strong>{" "}
          {submit.error instanceof Error
            ? submit.error.message
            : saveDraft.error instanceof Error
              ? saveDraft.error.message
              : "Unbekannter Fehler"}
        </div>
      )}

      {/* Form Card */}
      <div className="bg-white border border-[var(--color-border)] rounded-[var(--radius-xl)] p-[var(--space-xl)] shadow-[0_8px_30px_rgba(0,0,0,0.02)]">
        <InvoiceFormV2 value={draft} onChange={setDraft} />
      </div>

      {/* PDF Preview Modal */}
      <PdfPreviewModal
        open={previewOpen}
        pdfUrl={previewUrl}
        invoice={draft}
        customer={customer ? {
          name: customer.name || `${customer.vorname} ${customer.nachname}`.trim() || `Kunde #${customer.id}`,
          email: customer.email || undefined,
          street: customer.recipient_street || customer.strasse || undefined,
          postal_code: customer.recipient_postal_code || customer.plz || undefined,
          city: customer.recipient_city || customer.ort || undefined,
        } : undefined}
        company={company ? {
          name: company.name,
          street: company.street,
          postal_code: company.postal_code,
          city: company.city,
          email: company.email,
          phone: company.phone,
          bank_name: company.bank_name,
          iban: company.iban,
        } : undefined}
        invoiceNr="entwurf"
        onClose={() => setPreviewOpen(false)}
      />
    </div>
  );
}
