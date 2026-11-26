/**
 * @schema QuoteDetailPage
 * @purpose One quote: change subject, dates and positions, mark it accepted or rejected, send it,
 *   turn it into an invoice draft, or delete it
 * @output Header with "PDF herunterladen", "Vorschau", "Angebot senden" (mail dialog with attachments),
 *   "In Rechnung umwandeln" and "Löschen" (no invoice actions), a details card
 *   with status actions and inline editing, the positions with add/edit/remove. An accepted quote is
 *   locked (no editing).
 */
import { useEffect, useMemo, useState } from "react";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Download, ExternalLink, FileText, Lock, Pencil, Send, Trash2, X } from "lucide-react";
import { LineItemDialog } from "@/components/forms/line-item-dialog";
import { SendInvoiceSheet } from "@/components/invoice/send-invoice-sheet";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PageHeader } from "@/components/ui/page-header";
import { PdfPreviewModal } from "@/components/ui/pdf-preview-modal";
import { StatusBadge } from "@/components/ui/status-badge";
import { germanDate } from "@/components/quote/quote-list";
import { QuotePaymentPlanCard } from "@/components/quote/quote-payment-plan-card";
import { ICON_BUTTON, INPUT, SECONDARY_BUTTON, eur } from "@/components/quote/quote-ui";
import { useCustomer } from "@/lib/use-customers";
import { useUploadDocument } from "@/lib/use-documents";
import {
  useAddInvoiceAttachment,
  useAddInvoiceItem,
  useConvertQuote,
  useCreateFinalInvoice,
  useDeleteInvoiceItem,
  useInvoice,
  useUpdateInvoiceItem,
} from "@/lib/use-invoices";
import { useInvoicePreviewPdf } from "@/lib/use-invoice-preview-pdf";
import { useNotification } from "@/lib/use-notifications";
import { isIssuedStatus, isQuoteLocked, quoteDisplayStatus } from "@/lib/quote-status";
import type { InvoiceItem, InvoiceStatus } from "@/lib/schemas/invoice";
import { api } from "@/lib/api";

export const Route = createFileRoute("/_app/quotes/$id")({
  component: QuoteDetailPage,
});

function linkedInvoiceLabel(linked: { is_final_invoice?: boolean; is_down_payment?: boolean }): string {
  if (linked.is_final_invoice) return "Schlussrechnung";
  if (linked.is_down_payment) return "Abschlagsrechnung";
  return "Rechnung";
}

type HeaderDraft = { subject: string; date: string; valid_until: string };

function QuoteDetailPage() {
  const { id } = Route.useParams();
  const quoteId = Number(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { notify } = useNotification();
  const { data: quote, isLoading, isError } = useInvoice(quoteId);
  const addItem = useAddInvoiceItem();
  const updateItem = useUpdateInvoiceItem();
  const deleteItem = useDeleteInvoiceItem();
  const convert = useConvertQuote();
  const finalInvoice = useCreateFinalInvoice();
  const [header, setHeader] = useState<HeaderDraft | null>(null);
  const [itemDialog, setItemDialog] = useState<{ open: boolean; item?: InvoiceItem }>({ open: false });
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [acceptOpen, setAcceptOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [sendOpen, setSendOpen] = useState(false);
  const { data: customer } = useCustomer(quote?.customer_id ?? 0);
  const uploadDocument = useUploadDocument();
  const addAttachment = useAddInvoiceAttachment();
  const preview = useInvoicePreviewPdf(quoteId);
  const previewUrl = useMemo(() => (preview.data ? URL.createObjectURL(preview.data) : null), [preview.data]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["invoices"] });
    qc.invalidateQueries({ queryKey: ["invoice-preview-pdf", quoteId] });
  };

  const saveHeader = useMutation({
    mutationFn: (changes: Partial<HeaderDraft>) =>
      api.put(`/api/invoices/${quoteId}`, { ...changes, reason: "Angebot bearbeitet" }),
    onSuccess: () => {
      notify("success", "Angebot aktualisiert");
      setHeader(null);
      refresh();
    },
    onError: (err: Error) => notify("error", err.message),
  });

  const setStatus = useMutation({
    mutationFn: (status: InvoiceStatus) => api.put(`/api/invoices/${quoteId}/status`, { status }),
    onSuccess: (_data, status) => {
      notify("success", status === "ACCEPTED" ? "Angebot angenommen" : "Angebot abgelehnt");
      setAcceptOpen(false);
      setHeader(null);
      refresh();
    },
    onError: (err: Error) => notify("error", err.message),
  });

  const addFileAsAttachment = (file: File) =>
    uploadDocument.mutate(file, {
      onSuccess: (document) =>
        addAttachment.mutate(
          { invoiceId: quoteId, documentId: document.id },
          {
            onSuccess: () => notify("success", "Anlage hochgeladen und angehängt"),
            onError: (err: Error) => notify("error", err.message),
          },
        ),
      onError: (err: Error) => notify("error", err.message),
    });

  const sendQuote = useMutation({
    mutationFn: (payload: { message: string; includeAttachments: boolean }) =>
      api.post<{ message?: string }>(`/api/invoices/${quoteId}/send`, {
        message: payload.message,
        include_attachments: payload.includeAttachments,
      }),
    onSuccess: (data) => {
      setSendOpen(false);
      notify("success", data?.message || "Angebot gesendet");
      refresh();
    },
    onError: (err: Error) => notify("error", err.message),
  });

  const openSend = () => {
    if (!customer?.email) notify("error", "Der Kunde hat keine E-Mail-Adresse.");
    else setSendOpen(true);
  };

  const deleteQuote = useMutation({
    mutationFn: () => api.delete(`/api/invoices/${quoteId}`),
    onSuccess: () => {
      notify("success", "Angebot gelöscht");
      refresh();
      void navigate({ to: "/quotes" });
    },
    onError: (err: Error) => notify("error", err.message),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-brand-text)]" />
      </div>
    );
  }

  if (isError || !quote || quote.document_type !== "QUOTE") {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <p className="text-sm text-red-600">Angebot nicht gefunden.</p>
        <Link to="/quotes" className="mt-2 text-xs text-[var(--color-brand-text)] hover:underline">Zurück zur Liste</Link>
      </div>
    );
  }

  const items = quote.items ?? [];
  const linkedInvoices = quote.linked_invoices ?? [];
  const locked = isQuoteLocked(quote);
  const decided = quote.status === "ACCEPTED" || quote.status === "REJECTED";
  const hasFinalInvoice = linkedInvoices.some(
    (linked) => linked.is_final_invoice && linked.status !== "CANCELLED",
  );
  // Eine Schlussrechnung braucht eine gestellte Abschlagsrechnung: ein Entwurf genügt nicht.
  const hasIssuedDownPayment = linkedInvoices.some(
    (linked) => linked.is_down_payment && isIssuedStatus(linked.status),
  );
  const finalInvoiceHint = hasFinalInvoice
    ? "Zu diesem Angebot gibt es bereits eine Schlussrechnung"
    : hasIssuedDownPayment
      ? undefined
      : "Abschlagsrechnung zuerst senden";

  const startEdit = () =>
    setHeader({ subject: quote.subject, date: quote.date, valid_until: quote.valid_until });

  const submitHeader = () => {
    if (!header) return;
    const changes: Partial<HeaderDraft> = {};
    (Object.keys(header) as (keyof HeaderDraft)[]).forEach((key) => {
      if (header[key] !== quote[key]) changes[key] = header[key];
    });
    if (Object.keys(changes).length === 0) setHeader(null);
    else saveHeader.mutate(changes);
  };

  const saveItem = (item: InvoiceItem) => {
    const body = { description: item.description, quantity: item.quantity, unit_price: item.unit_price };
    const done = { onSuccess: () => setItemDialog({ open: false }), onError: (err: Error) => notify("error", err.message) };
    if (itemDialog.item?.id) updateItem.mutate({ invoiceId: quoteId, itemId: itemDialog.item.id, item: body }, done);
    else addItem.mutate({ invoiceId: quoteId, item: body }, done);
  };

  return (
    <div className="animate-fade-in space-y-[var(--space-lg)]">
      <PageHeader
        backTo="/quotes"
        backLabel="Angebote"
        title={<span>Angebot {quote.nr || `#${quote.id}`}</span>}
        documentTitle={`Angebot ${quote.nr || `#${quote.id}`}`}
        subtitle={quote.recipient_name || `Kunde #${quote.customer_id}`}
        actions={
          <>
            <a href={`/api/invoices/${quoteId}/download`} className={SECONDARY_BUTTON}>
              <Download size={16} /> PDF herunterladen
            </a>
            <button type="button" onClick={() => setPreviewOpen(true)} className={SECONDARY_BUTTON}>
              <ExternalLink size={16} /> Vorschau
            </button>
            <button type="button" onClick={openSend} disabled={sendQuote.isPending} className={SECONDARY_BUTTON}>
              <Send size={16} /> Angebot senden
            </button>
            <button
              type="button"
              onClick={() =>
                convert.mutate(quoteId, {
                  onSuccess: (invoice) => {
                    notify("success", invoice.nr ? `Rechnungsentwurf ${invoice.nr} angelegt` : "Rechnungsentwurf angelegt");
                    void navigate({ to: "/invoices/$id", params: { id: String(invoice.id) } });
                  },
                  onError: (err: Error) => notify("error", err.message),
                })
              }
              disabled={convert.isPending}
              className={SECONDARY_BUTTON}
            >
              <FileText size={16} /> {convert.isPending ? "Wandle um…" : "In Rechnung umwandeln"}
            </button>
            <button
              type="button"
              onClick={() =>
                finalInvoice.mutate(quoteId, {
                  onSuccess: (invoice) => {
                    notify(
                      "success",
                      invoice.nr ? `Schlussrechnung ${invoice.nr} angelegt` : "Schlussrechnung angelegt",
                    );
                    void navigate({ to: "/invoices/$id", params: { id: String(invoice.id) } });
                  },
                  onError: (err: Error) => notify("error", err.message),
                })
              }
              disabled={finalInvoice.isPending || hasFinalInvoice || !hasIssuedDownPayment}
              title={finalInvoiceHint}
              className={SECONDARY_BUTTON}
            >
              <FileText size={16} /> {finalInvoice.isPending ? "Erzeuge…" : "Schlussrechnung"}
            </button>
            <button
              type="button"
              onClick={() => setDeleteOpen(true)}
              disabled={linkedInvoices.length > 0}
              title={linkedInvoices.length > 0 ? "Ein Angebot mit Rechnungen lässt sich nicht löschen" : undefined}
              className={SECONDARY_BUTTON}
            >
              <Trash2 size={16} /> Löschen
            </button>
          </>
        }
      />

      {finalInvoiceHint === "Abschlagsrechnung zuerst senden" && (
        <p role="status" className="-mt-[var(--space-md)] text-[13px] text-[var(--color-text-secondary)]">
          Abschlagsrechnung zuerst senden: eine Schlussrechnung gibt es nur mit einer gestellten Abschlagsrechnung.
        </p>
      )}

      <div className="rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white p-[var(--space-lg)] shadow-sm">
        <div className="mb-[var(--space-md)] flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-[20px] font-semibold text-[var(--color-text-heading)]">Angaben</h2>
            <StatusBadge status={quoteDisplayStatus(quote)} />
          </div>
          {!header && !locked && (
            <button type="button" onClick={startEdit} className={SECONDARY_BUTTON}>
              <Pencil size={16} /> Bearbeiten
            </button>
          )}
        </div>

        {!decided && (
          <div className="mb-[var(--space-md)] flex flex-wrap gap-2">
            <button type="button" onClick={() => setAcceptOpen(true)} disabled={setStatus.isPending} className={SECONDARY_BUTTON}>
              <Check size={16} /> Angenommen
            </button>
            <button type="button" onClick={() => setStatus.mutate("REJECTED")} disabled={setStatus.isPending} className={SECONDARY_BUTTON}>
              <X size={16} /> Abgelehnt
            </button>
          </div>
        )}

        {locked && (
          <p className="mb-[var(--space-md)] flex items-center gap-2 text-[14px] text-[var(--color-text-secondary)]">
            <Lock size={14} /> Angenommen – das Angebot ist nicht mehr änderbar.
          </p>
        )}

        {header && !locked ? (
          <div className="grid gap-[var(--space-sm)] md:grid-cols-3">
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)]">
              Betreff
              <input className={INPUT} value={header.subject} onChange={(e) => setHeader({ ...header, subject: e.target.value })} />
            </label>
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)]">
              Angebotsdatum
              <input type="date" className={INPUT} value={header.date} onChange={(e) => setHeader({ ...header, date: e.target.value })} />
            </label>
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)]">
              Gültig bis
              <input type="date" className={INPUT} value={header.valid_until} onChange={(e) => setHeader({ ...header, valid_until: e.target.value })} />
            </label>
            <div className="flex gap-2 md:col-span-3">
              <button type="button" onClick={submitHeader} disabled={saveHeader.isPending} className={SECONDARY_BUTTON}>
                {saveHeader.isPending ? "Speichere…" : "Speichern"}
              </button>
              <button type="button" onClick={() => setHeader(null)} className={SECONDARY_BUTTON}>
                Abbrechen
              </button>
            </div>
          </div>
        ) : (
          <dl className="grid gap-[var(--space-sm)] text-[14px] md:grid-cols-3">
            <div>
              <dt className="text-[var(--color-text-secondary)]">Betreff</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{quote.subject || "—"}</dd>
            </div>
            <div>
              <dt className="text-[var(--color-text-secondary)]">Angebotsdatum</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{germanDate(quote.date) || "—"}</dd>
            </div>
            <div>
              <dt className="text-[var(--color-text-secondary)]">Gültig bis</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{germanDate(quote.valid_until) || "—"}</dd>
            </div>
          </dl>
        )}
      </div>

      <div className="overflow-hidden rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-[var(--space-lg)] py-[var(--space-sm)]">
          <h2 className="text-[20px] font-semibold text-[var(--color-text-heading)]">Positionen</h2>
          {!locked && (
            <button type="button" onClick={() => setItemDialog({ open: true })} className={SECONDARY_BUTTON}>
              + Position
            </button>
          )}
        </div>
        <ul>
          {items.length === 0 && (
            <li className="px-[var(--space-lg)] py-8 text-center text-[14px] text-[var(--color-text-secondary)]">Keine Positionen</li>
          )}
          {items.map((it, index) => (
            <li key={it.id ?? index} className="flex items-center gap-3 border-b border-[var(--color-border)] px-[var(--space-lg)] py-2">
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-[var(--color-text-heading)]">{it.description}</p>
                <p className="text-[13px] text-[var(--color-text-secondary)]">
                  {it.quantity} × {eur(it.unit_price)}
                </p>
              </div>
              <span className="font-mono text-[14px] font-bold">{eur(it.quantity * it.unit_price)}</span>
              {!locked && (
                <>
                  <button type="button" aria-label={`Position ${index + 1} bearbeiten`} onClick={() => setItemDialog({ open: true, item: it })} className={ICON_BUTTON}>
                    <Pencil size={16} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Position ${index + 1} entfernen`}
                    disabled={deleteItem.isPending}
                    onClick={() => it.id && deleteItem.mutate({ invoiceId: quoteId, itemId: it.id })}
                    className={ICON_BUTTON}
                  >
                    <Trash2 size={16} />
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
        <div className="flex justify-end px-[var(--space-lg)] py-[var(--space-md)] text-[16px] font-semibold">
          Summe <span className="ml-3 font-mono">{eur(quote.total_brutto)}</span>
        </div>
      </div>

      <QuotePaymentPlanCard
        quoteId={quoteId}
        gross={quote.total_brutto}
        plan={quote.payment_plan ?? []}
        locked={locked}
        invoices={linkedInvoices}
      />

      <div className="rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white p-[var(--space-lg)] shadow-sm">
        <h2 className="mb-[var(--space-sm)] text-[20px] font-semibold text-[var(--color-text-heading)]">Rechnungen</h2>
        {linkedInvoices.length === 0 ? (
          <p className="text-[14px] text-[var(--color-text-secondary)]">Noch keine Rechnung zu diesem Angebot.</p>
        ) : (
          <>
            <ul>
              {linkedInvoices.map((linked) => (
                <li key={linked.id} className="flex min-h-[44px] items-center justify-between gap-3 border-b border-[var(--color-border)] last:border-b-0">
                  <Link
                    to="/invoices/$id"
                    params={{ id: String(linked.id) }}
                    className="font-semibold text-[var(--color-brand-text)] hover:underline"
                  >
                    {linkedInvoiceLabel(linked)} {linked.nr || `#${linked.id}`}
                  </Link>
                  <span className="flex items-center gap-3">
                    <StatusBadge status={linked.status} />
                    <span className="font-mono text-[14px] font-bold">{eur(linked.total_brutto)}</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-[var(--space-sm)] text-[13px] text-[var(--color-text-secondary)]">
              Ein Angebot mit Rechnungen lässt sich nicht löschen.
            </p>
          </>
        )}
      </div>

      <LineItemDialog
        open={itemDialog.open}
        initial={itemDialog.item}
        onSave={saveItem}
        onCancel={() => setItemDialog({ open: false })}
      />

      <PdfPreviewModal
        open={previewOpen}
        pdfUrl={previewUrl}
        invoiceNr={quote.nr || undefined}
        documentType="QUOTE"
        onClose={() => setPreviewOpen(false)}
      />

      <SendInvoiceSheet
        open={sendOpen}
        documentType="QUOTE"
        recipientName={quote.recipient_name || customer?.name || ""}
        recipientEmail={customer?.email}
        attachmentCount={quote.attachments?.length ?? 0}
        uploading={uploadDocument.isPending || addAttachment.isPending}
        onAddFile={addFileAsAttachment}
        pending={sendQuote.isPending}
        onSend={(message, includeAttachments) => sendQuote.mutate({ message, includeAttachments })}
        onCancel={() => setSendOpen(false)}
      />

      <ConfirmDialog
        open={acceptOpen}
        title="Angebot annehmen?"
        message="Ein angenommenes Angebot lässt sich danach nicht mehr ändern."
        confirmLabel={setStatus.isPending ? "Speichere…" : "Annehmen"}
        pending={setStatus.isPending}
        onConfirm={() => setStatus.mutate("ACCEPTED")}
        onCancel={() => setAcceptOpen(false)}
      />

      <ConfirmDialog
        open={deleteOpen}
        title="Angebot löschen?"
        message="Das Angebot und seine Positionen werden entfernt."
        confirmLabel={deleteQuote.isPending ? "Lösche…" : "Löschen"}
        destructive
        pending={deleteQuote.isPending}
        onConfirm={() => {
          setDeleteOpen(false);
          deleteQuote.mutate();
        }}
        onCancel={() => setDeleteOpen(false)}
      />
    </div>
  );
}
