/**
 * @schema InvoiceDetailPage
 * @purpose Full invoice detail matching Lumina Ledger HTML: status timeline, bento cards, client, items, summary
 */
import { useEffect, useState } from "react";
import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  useInvoice,
  useUpdateInvoiceStatus,
  useAddInvoiceItem,
  useUpdateInvoiceItem,
  useDeleteInvoiceItem,
} from "@/lib/use-invoices";
import { useInvoicePreviewPdf } from "@/lib/use-invoice-preview-pdf";
import { useCustomer } from "@/lib/use-customers";
import { useCompany } from "@/lib/use-company";
import { useNotification } from "@/lib/use-notifications";
import { api } from "@/lib/api";
import type { InvoiceStatus, InvoiceItem } from "@/lib/schemas/invoice";
import {
  Download,
  ExternalLink,
  Pencil,
  Send,
  Info,
  FileText,
  Loader2,
} from "lucide-react";
import { StatusTimeline } from "@/components/ui/status-timeline";
import { ClientInfoCard } from "@/components/invoice/client-info-card";
import { SummaryCard } from "@/components/invoice/summary-card";
import { PageHeader } from "@/components/ui/page-header";
import { LineItemDialog } from "@/components/forms/line-item-dialog";
import { PdfPreviewModal } from "@/components/ui/pdf-preview-modal";

export const Route = createFileRoute("/_app/invoices/$id")({
  component: InvoiceDetailPage,
});

const eur = (n: number) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: 2 }) + " €";

function InvoiceDetailPage() {
  const { id } = useParams({ from: "/_app/invoices/$id" });
  const invoiceId = Number(id);
  const { data: invoice, isLoading, isError } = useInvoice(invoiceId);
  const updateStatus = useUpdateInvoiceStatus();
  const addItem = useAddInvoiceItem();
  const updateItem = useUpdateInvoiceItem();
  const deleteItem = useDeleteInvoiceItem();
  const preview = useInvoicePreviewPdf(invoiceId);
  const previewUrl = preview.data ? URL.createObjectURL(preview.data) : null;
  const { data: customer } = useCustomer(invoice?.customer_id ?? 0);
  const { data: company } = useCompany();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<InvoiceItem | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const { notify } = useNotification();
  const qc = useQueryClient();

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleAddItem = () => { setEditingItem(null); setDialogOpen(true); };
  const handleEditItem = (item: InvoiceItem) => { setEditingItem(item); setDialogOpen(true); };

  const handleDeleteItem = (itemId: number) => {
    if (confirm("Position wirklich löschen?")) deleteItem.mutate({ invoiceId, itemId });
  };

  const handleSaveItem = (item: InvoiceItem) => {
    if (editingItem?.id) {
      updateItem.mutate({ invoiceId, itemId: editingItem.id, item: { description: item.description, quantity: item.quantity, unit_price: item.unit_price } });
    } else {
      addItem.mutate({ invoiceId, item: { description: item.description, quantity: item.quantity, unit_price: item.unit_price } });
    }
    setDialogOpen(false);
  };

  const sendEmail = useMutation({
    mutationFn: () => api.post(`/api/invoices/${invoiceId}/send`),
    onSuccess: (data: unknown) => {
      const msg = (data as { message?: string })?.message || "Rechnung gesendet";
      notify("success", msg);
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["invoices", invoiceId] });
    },
    onError: (err: Error) => {
      notify("error", err.message);
    },
  });

  const paymentLink = useMutation({
    mutationFn: () => api.post<{ payment_link_url?: string }>(`/api/invoices/${invoiceId}/payment-link`),
    onSuccess: (data) => {
      const url = data?.payment_link_url;
      if (url) {
        window.open(url, "_blank", "noopener");
        notify("success", "Zahlungslink geöffnet");
      } else {
        notify("error", "Stripe nicht konfiguriert");
      }
    },
    onError: (err: Error) => {
      notify("error", err.message);
    },
  });

  const handleSend = () => {
    if (invoice?.recipient_name && confirm(`Rechnung per E-Mail an ${invoice.recipient_name} senden?`)) {
      sendEmail.mutate();
    }
  };

  if (isLoading) return (
    <div className="flex items-center justify-center py-16">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-brand-text)]" />
    </div>
  );

  if (isError || !invoice) return (
    <div className="flex flex-col items-center justify-center py-16">
      <p className="text-sm text-red-500">Rechnung nicht gefunden.</p>
      <Link to="/invoices" className="mt-2 text-xs text-[var(--color-brand-text)] hover:underline">Zurück zur Liste</Link>
    </div>
  );

  const validTransitions = getValidTransitions(invoice.status);
  const isDraft = invoice.status === "DRAFT";
  const items = invoice.items || [];
  const banner = getStatusBanner(invoice.status);

  return (
    <div className="animate-fade-in">
      {/* ── Header ── */}
      <PageHeader
        backTo="/invoices"
        backLabel="Rechnungen"
        title={<>Rechnung #{invoice.nr || invoice.id}</>}
        subtitle={<>Erstellt am {invoice.date || "Kein Datum"}</>}
        actions={
          <>
            <a
              href={`/api/invoices/${invoice.id}/download`}
              className="inline-flex items-center gap-2 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-[var(--space-md)] py-[var(--space-xs)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-heading)] hover:bg-[var(--color-surface-container-low)] transition-colors"
            >
              <Download size={16} />
              PDF herunterladen
            </a>
            <button
              type="button"
              onClick={() => setPreviewOpen(true)}
              className="inline-flex items-center gap-2 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-[var(--space-md)] py-[var(--space-xs)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-heading)] hover:bg-[var(--color-surface-container-low)] transition-colors"
            >
              <ExternalLink size={16} /> Vorschau
            </button>
            {!isDraft && invoice.status !== "PAID" && (
              <button
                type="button"
                onClick={() => paymentLink.mutate()}
                disabled={paymentLink.isPending}
                className="inline-flex items-center gap-2 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-[var(--space-md)] py-[var(--space-xs)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-heading)] hover:bg-[var(--color-surface-container-low)] transition-colors disabled:opacity-50"
              >
                {paymentLink.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <ExternalLink size={16} />
                )}
                {paymentLink.isPending ? "Erstelle…" : "Zahlungslink"}
              </button>
            )}
            {isDraft && (
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-[var(--space-md)] py-[var(--space-xs)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-heading)] hover:bg-[var(--color-surface-container-low)] transition-colors"
              >
                <Pencil size={16} /> Bearbeiten
              </button>
            )}
            {validTransitions.includes("SENT" as InvoiceStatus) && (
              <button
                type="button"
                onClick={handleSend}
                disabled={sendEmail.isPending}
                className="inline-flex items-center gap-2 rounded-[var(--radius-lg)] bg-[#001a42] px-[var(--space-md)] py-[var(--space-xs)] text-[12px] font-semibold uppercase tracking-[0.05em] text-white hover:opacity-90 transition-opacity shadow-sm disabled:opacity-50"
              >
                {sendEmail.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Send size={16} />
                )}
                {sendEmail.isPending ? "Sende…" : "An Kunde senden"}
              </button>
            )}
          </>
        }
      />

      {/* ── Status Timeline Card ── */}
      <div className="bg-white rounded-[var(--radius-xl)] border border-[var(--color-border)] p-[var(--space-lg)] mb-[var(--space-xl)] shadow-sm">
        <h3 className="text-[20px] font-semibold text-[var(--color-text-heading)] mb-[var(--space-md)]">Statusverfolgung</h3>
        <StatusTimeline currentStatus={invoice.status} />

        {banner && (
          <div className="mt-[var(--space-lg)] p-[var(--space-sm)] bg-[var(--color-surface-container-low)] rounded-[var(--radius-lg)] border border-[var(--color-border)] flex items-start gap-3">
            <Info size={18} className="text-[var(--color-brand-text)] mt-0.5 shrink-0" />
            <div>
              <p className="text-[14px] font-semibold text-[var(--color-text-heading)]">{banner.title}</p>
              <p className="text-[14px] text-[var(--color-text-secondary)]">{banner.message}</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Bento Grid: 3 cols ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-[var(--space-gutter)]">
        {/* Left 2/3 */}
        <div className="lg:col-span-2 space-y-[var(--space-xl)]">
          <ClientInfoCard
            client={{
              name: invoice.recipient_name,
              email: customer?.email,
              strasse: invoice.recipient_street,
              plz: invoice.recipient_postal_code,
              ort: invoice.recipient_city,
            }}
            dueDate={invoice.delivery_date}
          />

          {/* Line Items */}
          <div className="bg-white rounded-[var(--radius-xl)] border border-[var(--color-border)] shadow-sm overflow-hidden">
            <div className="px-[var(--space-lg)] py-[var(--space-md)] border-b border-[var(--color-border)] flex justify-between items-center">
              <h3 className="text-[20px] font-semibold text-[var(--color-text-heading)]">Positionen</h3>
              {isDraft && (
                <button
                  type="button"
                  onClick={handleAddItem}
                  className="inline-flex items-center gap-1.5 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-3 py-1.5 text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-heading)] hover:bg-[var(--color-surface-container-low)] transition-colors"
                >
                  + Position
                </button>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[var(--color-surface-container-low)] border-b border-[var(--color-border)]">
                    <th className="py-[var(--space-sm)] px-[var(--space-lg)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)]">Beschreibung</th>
                    <th className="py-[var(--space-sm)] px-[var(--space-md)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)] text-right">Menge</th>
                    <th className="py-[var(--space-sm)] px-[var(--space-md)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)] text-right">Preis</th>
                    <th className="py-[var(--space-sm)] px-[var(--space-lg)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)] text-right">Betrag</th>
                    {isDraft && <th className="w-16 py-[var(--space-sm)]" />}
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 && (
                    <tr><td colSpan={isDraft ? 5 : 4} className="px-[var(--space-lg)] py-8 text-center text-[14px] text-[var(--color-text-secondary)]">Keine Positionen</td></tr>
                  )}
                  {items.map((it) => (
                    <tr key={it.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-bright)] transition-colors group">
                      <td className="py-[var(--space-md)] px-[var(--space-lg)]">
                        <p className="font-semibold text-[var(--color-text-heading)]">{it.description}</p>
                      </td>
                      <td className="py-[var(--space-md)] px-[var(--space-md)] text-right font-mono text-[14px] text-[var(--color-text-primary)]">{it.quantity}</td>
                      <td className="py-[var(--space-md)] px-[var(--space-md)] text-right font-mono text-[14px] text-[var(--color-text-primary)]">{eur(it.unit_price)}</td>
                      <td className="py-[var(--space-md)] px-[var(--space-lg)] text-right font-mono text-[14px] font-bold text-[var(--color-text-primary)]">{eur(it.quantity * it.unit_price)}</td>
                      {isDraft && (
                        <td className="py-[var(--space-md)] px-2 text-right">
                          <div className="flex items-center justify-end gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                            <button type="button" onClick={() => handleEditItem(it)} className="rounded p-1 text-[var(--color-text-muted)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-brand-text)] transition-colors" title="Bearbeiten"><Pencil size={14} /></button>
                            <button type="button" onClick={() => handleDeleteItem(it.id!)} disabled={deleteItem.isPending} className="rounded p-1 text-[var(--color-text-muted)] hover:bg-red-500/10 hover:text-red-500 transition-colors" title="Löschen"><FileText size={14} className="rotate-45" /></button>
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right 1/3 */}
        <div className="space-y-[var(--space-gutter)]">
          <SummaryCard subtotal={invoice.total_brutto} taxRate={19} ustEnabled />

          {/* Status Actions */}
          {validTransitions.length > 0 && (
            <div className="bg-white rounded-[var(--radius-xl)] border border-[var(--color-border)] p-[var(--space-md)] shadow-sm">
              <h3 className="text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)] mb-3">Status ändern</h3>
              <div className="space-y-1.5">
                {validTransitions.map((status) => (
                  <button key={status} type="button" onClick={() => updateStatus.mutate({ id: invoice.id, status })} disabled={updateStatus.isPending}
                    className="flex w-full items-center gap-2 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-3 py-2 text-[12px] font-medium text-[var(--color-text-secondary)] transition-all hover:border-[var(--color-brand-text)]/30 hover:bg-[var(--color-brand-text)]/[0.05] hover:text-[var(--color-brand-text)] disabled:opacity-50">
                    {STATUS_LABELS_FULL[status as InvoiceStatus] || status}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Payment Link */}
          {invoice.payment_link_url && (
            <div className="bg-white rounded-[var(--radius-xl)] border border-[var(--color-border)] p-[var(--space-md)] shadow-sm">
              <h3 className="text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)] mb-3">Zahlungslink</h3>
              <a href={invoice.payment_link_url} target="_blank" rel="noopener"
                className="flex items-center gap-2 text-[13px] text-[var(--color-brand-text)] hover:underline break-all">
                <ExternalLink size={14} />
                {invoice.payment_link_url}
              </a>
            </div>
          )}

          {/* Internal Notes */}
          <div className="bg-[var(--color-surface-bright)] rounded-[var(--radius-xl)] border border-[var(--color-border)] p-[var(--space-md)] shadow-sm">
            <h3 className="text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)] mb-[var(--space-xs)]">Interne Notizen</h3>
            <p className="text-[14px] text-[var(--color-text-primary)]">{"notes" in invoice && typeof invoice.notes === "string" ? (invoice.notes as string) || "Keine Notizen." : "Keine Notizen."}</p>
          </div>
        </div>
      </div>

      <LineItemDialog open={dialogOpen} initial={editingItem ?? undefined} onSave={handleSaveItem} onCancel={() => setDialogOpen(false)} />
      <PdfPreviewModal open={previewOpen} pdfUrl={previewUrl} invoice={invoice} customer={customer ? { name: customer.name || `${customer.vorname} ${customer.nachname}`.trim() || `Kunde #${customer.id}`, email: customer.email || undefined, street: customer.recipient_street || customer.strasse || undefined, postal_code: customer.recipient_postal_code || customer.plz || undefined, city: customer.recipient_city || customer.ort || undefined } : undefined} company={company ? { name: company.name, street: company.street, postal_code: company.postal_code, city: company.city, email: company.email, phone: company.phone, bank_name: company.bank_name, iban: company.iban } : undefined} invoiceNr={invoice.nr || undefined} onClose={() => setPreviewOpen(false)} />
    </div>
  );
}

const STATUS_LABELS_FULL: Record<string, string> = {
  DRAFT: "Entwurf", OPEN: "Offen", SENT: "Gesendet", PAID: "Bezahlt", FINALIZED: "Finalisiert", CANCELLED: "Storniert",
};

function getValidTransitions(current: InvoiceStatus): InvoiceStatus[] {
  const t: Record<InvoiceStatus, InvoiceStatus[]> = { DRAFT: ["OPEN","CANCELLED"], OPEN: ["SENT","PAID","CANCELLED"], SENT: ["PAID","CANCELLED"], PAID: [], FINALIZED: [], CANCELLED: [] };
  return t[current] || [];
}

function getStatusBanner(status: string): { title: string; message: string } | null {
  const banners: Record<string, { title: string; message: string }> = {
    DRAFT: { title: "Entwurf", message: "Diese Rechnung ist ein Entwurf. Bearbeiten und finalisieren, um sie an den Kunden zu senden." },
    OPEN: { title: "Aktion erforderlich", message: "Diese Rechnung ist finalisiert und bereit, an den Kunden gesendet zu werden." },
    FINALIZED: { title: "Aktion erforderlich", message: "Diese Rechnung ist finalisiert und bereit, an den Kunden gesendet zu werden." },
    SENT: { title: "Warten auf Zahlung", message: "Die Rechnung wurde an den Kunden gesendet. Zahlung steht aus." },
    PAID: { title: "Bezahlt", message: "Diese Rechnung wurde vollständig beglichen." },
    CANCELLED: { title: "Storniert", message: "Diese Rechnung wurde storniert und ist nicht mehr aktiv." },
  };
  return banners[status] || null;
}
