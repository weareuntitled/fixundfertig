/**
 * @schema QuoteDetailPage
 * @purpose One quote: the next sensible step as the only primary action, how much of the quote is
 *   billed already, net, VAT and gross, the positions, the payment plan and the invoices
 * @output Header with one primary action per status (draft: send, sent: accept, accepted: bill or
 *   final invoice) and a "Mehr" menu with the remaining actions, a details card with status and
 *   decision, a card with the billing progress and the reasons for blocked actions, the positions
 *   with net, VAT and gross, the payment plan and the invoices of the quote.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, createFileRoute, useBlocker, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CalendarPlus,
  Check,
  CheckCheck,
  Download,
  ExternalLink,
  FileText,
  Lock,
  Pencil,
  Send,
  Trash2,
  Undo2,
  X,
} from "lucide-react";
import { LineItemDialog } from "@/components/forms/line-item-dialog";
import { CustomerSelector } from "@/components/forms/customer-selector";
import { SendInvoiceSheet } from "@/components/invoice/send-invoice-sheet";
import { ActionMenu, type ActionMenuItem } from "@/components/ui/action-menu";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PageHeader } from "@/components/ui/page-header";
import { PdfPreviewModal } from "@/components/ui/pdf-preview-modal";
import { StatusBadge } from "@/components/ui/status-badge";
import { germanDate } from "@/components/quote/quote-list";
import { QuotePaymentPlanCard } from "@/components/quote/quote-payment-plan-card";
import { ICON_BUTTON, INPUT, PRIMARY_BUTTON, SECONDARY_BUTTON, eur, settlementLabel } from "@/components/quote/quote-ui";
import { useMediaQuery, WIDE_SCREEN } from "@/hooks/use-media-query";
import { useCustomer } from "@/lib/use-customers";
import { useUploadDocument } from "@/lib/use-documents";
import {
  useAddInvoiceAttachment,
  useAddInvoiceItem,
  useConvertQuote,
  useCreateFinalInvoice,
  useDeleteInvoiceItem,
  useExtendQuoteValidity,
  useInvoice,
  useMarkQuoteSent,
  useUpdateInvoiceItem,
} from "@/lib/use-invoices";
import { useInvoicePreviewPdf } from "@/lib/use-invoice-preview-pdf";
import { useBillDownPayment } from "@/lib/use-quote-billing";
import { useNotification } from "@/lib/use-notifications";
import { isQuoteLocked, quoteDisplayStatus } from "@/lib/quote-status";
import { addDaysIso, QUOTE_VALIDITY_DAYS, type BillingAction, type InvoiceItem, type InvoiceStatus } from "@/lib/schemas/invoice";
import { api } from "@/lib/api";

export const Route = createFileRoute("/_app/quotes/$id")({
  component: QuoteDetailPage,
});

function linkedInvoiceLabel(linked: { is_final_invoice?: boolean; is_down_payment?: boolean }): string {
  if (linked.is_final_invoice) return "Schlussrechnung";
  if (linked.is_down_payment) return "Abschlagsrechnung";
  return "Rechnung";
}

type HeaderDraft = { subject: string; date: string; valid_until: string; customer_id: number; intro_text: string; vat_rate: number };

/** Welche Abrechnung soll laufen? „down_payment“ nennt zusätzlich die Rate. */
type BillingRequest = { kind: "convert" | "final" | "down_payment"; index?: number };

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
  const markSent = useMarkQuoteSent();
  const extendValidity = useExtendQuoteValidity();
  const { billRate, isPending: billingPending } = useBillDownPayment(quoteId);
  // Am Handy stehen die Kopfaktionen im „Mehr"-Menü, am Desktop nebeneinander (#498).
  const isWide = useMediaQuery(WIDE_SCREEN, true);
  const [header, setHeader] = useState<HeaderDraft | null>(null);
  const [validityTouched, setValidityTouched] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<InvoiceItem | null>(null);
  const [itemDirty, setItemDirty] = useState(false);
  const [planDirty, setPlanDirty] = useState(false);
  const headerDirty = Boolean(header && quote && Object.entries(header).some(([key, value]) => value !== quote[key as keyof HeaderDraft]));
  const dirty = headerDirty || itemDirty || planDirty;
  const leaving = useBlocker({
    shouldBlockFn: () => dirty,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const [itemDialog, setItemDialog] = useState<{ open: boolean; item?: InvoiceItem }>({ open: false });
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [acceptOpen, setAcceptOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [sendOpen, setSendOpen] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [billingRequest, setBillingRequest] = useState<BillingRequest | null>(null);
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
      setRejectOpen(false);
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
      setSendError(null);
      notify("success", data?.message || "Angebot gesendet");
      refresh();
    },
    // Der Fehler bleibt im Dialog: er steht dort, solange er gelesen werden muss,
    // und der Dialog bleibt offen (mit dem Ausweg „als gesendet markieren“).
    onError: (err: Error) => setSendError(err.message),
  });

  const markAsSent = () =>
    markSent.mutate(quoteId, {
      onSuccess: () => {
        setSendOpen(false);
        setSendError(null);
        notify("success", "Angebot als gesendet markiert");
        refresh();
      },
      onError: (err: Error) => notify("error", err.message),
    });

  const extendQuoteValidity = () =>
    extendValidity.mutate(quoteId, {
      onSuccess: (data) => {
        notify("success", `Gültigkeit verlängert bis ${germanDate(data?.valid_until ?? "")}`);
        refresh();
      },
      onError: (err: Error) => notify("error", err.message),
    });

  const openSend = () => {
    if (!customer?.email) notify("error", "Der Kunde hat keine E-Mail-Adresse.");
    else {
      setSendError(null);
      setSendOpen(true);
    }
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
  const rejected = quote.status === "REJECTED";
  // Ein abgelehntes Angebot ist nur noch lesbar: kein Bearbeiten, kein Abrechnen, kein Senden.
  const readOnly = locked || rejected;
  const decided = quote.status === "ACCEPTED" || quote.status === "REJECTED";
  const expired = quoteDisplayStatus(quote) === "EXPIRED";
  // Eine Rechnung macht die Entscheidung endgültig: dann gibt es keinen Rückweg mehr.
  const hasInvoice = linkedInvoices.some((linked) => linked.status !== "CANCELLED");
  const canTakeDecisionBack = decided && !hasInvoice;
  // Die Serverregeln (#495): was darf abgerechnet werden, und warum nicht.
  const billing = quote.billing ?? null;
  const settlement = quote.settlement ?? null;
  // Ohne Serverregeln (älteres Backend) bleibt alles erlaubt; der Server prüft ohnehin.
  const isAllowed = (action: BillingAction | undefined) => (action ? action.allowed : true);
  const canConvert = isAllowed(billing?.convert);
  const canDownPayment = isAllowed(billing?.down_payment);
  const canFinalInvoice = isAllowed(billing?.final_invoice);
  const vatAmount = Math.max(0, Math.round((quote.total_brutto - quote.total_net) * 100) / 100);
  const vatRateLabel =
    quote.vat_rate > 0
      ? `${quote.vat_rate.toLocaleString("de-DE", { maximumFractionDigits: 2 })} %`
      : "";

  // Die Abschlagsrechnung im Entwurf: die Schlussrechnung zieht sie erst ab,
  // wenn sie gestellt ist (#497).
  const draftDownPayment = linkedInvoices.find(
    (linked) => linked.is_down_payment && linked.status === "DRAFT",
  );

  // Raten, die noch nicht abgerechnet sind (eine stornierte Abschlagsrechnung zählt nicht).
  const billedRateIndexes = new Set(
    linkedInvoices
      .filter((linked) => linked.installment_index != null && linked.status !== "CANCELLED")
      .map((linked) => linked.installment_index as number),
  );
  const openRates = (quote.payment_plan ?? [])
    .map((rate, index) => ({ rate, index }))
    .filter(({ index }) => !billedRateIndexes.has(index));

  const convertQuote = () =>
    convert.mutate(quoteId, {
      onSuccess: (invoice) => {
        notify("success", invoice.nr ? `Rechnungsentwurf ${invoice.nr} angelegt` : "Rechnungsentwurf angelegt");
        void navigate({ to: "/invoices/$id", params: { id: String(invoice.id) } });
      },
      onError: (err: Error) => notify("error", err.message),
    });

  const createFinalInvoice = () =>
    finalInvoice.mutate(quoteId, {
      onSuccess: (invoice) => {
        notify(
          "success",
          invoice.nr ? `Schlussrechnung ${invoice.nr} angelegt` : "Schlussrechnung angelegt",
        );
        void navigate({ to: "/invoices/$id", params: { id: String(invoice.id) } });
      },
      onError: (err: Error) => notify("error", err.message),
    });

  // Abrechnen nimmt ein gesendetes Angebot an: vorher fragen (#495, `requires_acceptance`).
  const requestBilling = (request: BillingRequest) => {
    if (billing?.requires_acceptance) {
      setBillingRequest(request);
      return;
    }
    runBilling(request);
  };

  const runBilling = (request: BillingRequest) => {
    if (request.kind === "convert") convertQuote();
    else if (request.kind === "final") createFinalInvoice();
    else if (request.index != null) billRate(request.index);
  };

  // Die Wege, mit denen abgerechnet werden kann (nur die erlaubten).
  const billItems: ActionMenuItem[] = [];
  if (canDownPayment) {
    for (const { rate, index } of openRates) {
      billItems.push({
        label: `Abschlag ${eur(rate.amount)} abrechnen`,
        icon: <FileText size={15} />,
        onSelect: () => requestBilling({ kind: "down_payment", index }),
        disabled: billingPending,
      });
    }
  }
  if (canConvert) {
    billItems.push({
      label: "In Rechnung umwandeln",
      icon: <FileText size={15} />,
      onSelect: () => requestBilling({ kind: "convert" }),
      disabled: convert.isPending,
    });
  }

  // Genau eine Primäraktion je Status: der nächste sinnvolle Schritt (#499).
  const primaryKind: "send" | "accept" | "bill" | "final" | null = rejected
    ? null
    : quote.status === "DRAFT"
      ? "send"
      : quote.status === "SENT"
        ? "accept"
        : canFinalInvoice
          ? "final"
          : billItems.length > 0
            ? "bill"
            : null;

  // Gesperrte Aktionen stehen als Text mit Grund, nicht als Knopf (#495).
  const blockedReasons: {
    label: string;
    reason: string;
    invoiceId: number | null;
    invoiceNr: string | null;
    showLink: boolean;
  }[] = [];
  const blockedEntries: [string, BillingAction][] = billing
    ? [
        ["In Rechnung umwandeln", billing.convert],
        ["Abschlag abrechnen", billing.down_payment],
        ["Schlussrechnung", billing.final_invoice],
      ]
    : [];
  const linkedInvoiceIds = new Set<number>();
  for (const [label, action] of blockedEntries) {
    if (action.allowed || !action.reason) continue;
    if (blockedReasons.some((entry) => entry.reason === action.reason)) continue;
    // Jede sperrende Rechnung wird nur einmal verlinkt.
    const showLink = action.invoice_id != null && !linkedInvoiceIds.has(action.invoice_id);
    if (action.invoice_id != null) linkedInvoiceIds.add(action.invoice_id);
    blockedReasons.push({
      label,
      reason: action.reason,
      invoiceId: action.invoice_id,
      invoiceNr: action.invoice_nr,
      showLink,
    });
  }

  const moreItems: ActionMenuItem[] = [
    { label: "Vorschau", icon: <ExternalLink size={15} />, onSelect: () => setPreviewOpen(true) },
    ...(quote.status === "DRAFT"
      ? [
          {
            label: "Als gesendet markieren",
            icon: <CheckCheck size={15} />,
            onSelect: markAsSent,
            disabled: markSent.isPending,
          },
        ]
      : []),
    ...(canTakeDecisionBack
      ? [
          {
            label: "Entscheidung zurücknehmen",
            icon: <Undo2 size={15} />,
            onSelect: markAsSent,
            disabled: markSent.isPending,
          },
        ]
      : []),
    // Die Abrechnung hat ihren eigenen Knopf; nur ohne sie gehört sie ins Menü.
    ...(primaryKind !== "bill" && canConvert
      ? [
          {
            label: "In Rechnung umwandeln",
            icon: <FileText size={15} />,
            onSelect: () => requestBilling({ kind: "convert" }),
            disabled: convert.isPending,
          },
        ]
      : []),
    {
      label: "Löschen",
      icon: <Trash2 size={15} />,
      onSelect: () => setDeleteOpen(true),
      disabled: linkedInvoices.length > 0,
      danger: true,
    },
  ];

  // Am Handy wandert der Download mit ins Menü: die Kopfzeile bleibt schmal (#498).
  const mobileMoreItems: ActionMenuItem[] = [
    {
      label: "PDF herunterladen",
      icon: <Download size={15} />,
      href: `/api/invoices/${quoteId}/download`,
    },
    ...moreItems,
  ];

  const startEdit = () => {
    setValidityTouched(quote.valid_until !== addDaysIso(quote.date, QUOTE_VALIDITY_DAYS));
    setHeader({ subject: quote.subject, date: quote.date, valid_until: quote.valid_until, customer_id: quote.customer_id, intro_text: quote.intro_text, vat_rate: quote.vat_rate });
  };

  const submitHeader = () => {
    if (!header) return;
    const changes = Object.fromEntries(Object.entries(header).filter(([key, value]) => value !== quote[key as keyof HeaderDraft])) as Partial<HeaderDraft>;
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
    <div className="animate-fade-in space-y-[var(--space-lg)] pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
      <PageHeader
        backTo="/quotes"
        backLabel="Angebote"
        title={<span>Angebot {quote.nr || `#${quote.id}`}</span>}
        documentTitle={`Angebot ${quote.nr || `#${quote.id}`}`}
        subtitle={quote.recipient_name || `Kunde #${quote.customer_id}`}
        actions={
          <>
            {primaryKind === "send" && (
              <button
                type="button"
                data-primary="true"
                onClick={openSend}
                disabled={sendQuote.isPending}
                className={PRIMARY_BUTTON}
              >
                <Send size={16} /> Senden
              </button>
            )}
            {primaryKind === "accept" && (
              <button
                type="button"
                data-primary="true"
                onClick={() => setAcceptOpen(true)}
                disabled={setStatus.isPending}
                className={PRIMARY_BUTTON}
              >
                <Check size={16} /> Annehmen
              </button>
            )}
            {primaryKind === "final" && (
              <button
                type="button"
                data-primary="true"
                onClick={() => requestBilling({ kind: "final" })}
                disabled={finalInvoice.isPending}
                className={PRIMARY_BUTTON}
              >
                <FileText size={16} /> {finalInvoice.isPending ? "Erzeuge…" : "Schlussrechnung"}
              </button>
            )}
            {primaryKind === "bill" && (
              <ActionMenu
                label="Abrechnen"
                icon={<FileText size={16} />}
                items={billItems}
                triggerClassName={PRIMARY_BUTTON}
                triggerAttributes={{ "data-primary": "true" }}
              />
            )}
            {isWide && (
              <a href={`/api/invoices/${quoteId}/download`} className={SECONDARY_BUTTON}>
                <Download size={16} /> PDF herunterladen
              </a>
            )}
            <ActionMenu items={isWide ? moreItems : mobileMoreItems} />
          </>
        }
      />

      {draftDownPayment && (
        <p className="-mt-[var(--space-md)] text-[13px] text-[var(--color-text-secondary)]">
          Die Abschlagsrechnung{" "}
          <Link
            to="/invoices/$id"
            params={{ id: String(draftDownPayment.id) }}
            className="font-semibold text-[var(--color-brand-text)] hover:underline"
          >
            {draftDownPayment.nr || `#${draftDownPayment.id}`}
          </Link>{" "}
          ist noch nicht gestellt. Stellen Sie sie, dann zieht die Schlussrechnung die Abschlagsrechnungen ab.
        </p>
      )}

      <div className="rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white p-[var(--space-lg)] shadow-sm">
        <div className="mb-[var(--space-md)] flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-[20px] font-semibold text-[var(--color-text-heading)]">Angaben</h2>
            <StatusBadge status={quoteDisplayStatus(quote)} />
          </div>
          {!header && !readOnly && (
            <button type="button" onClick={startEdit} className={SECONDARY_BUTTON}>
              <Pencil size={16} /> Bearbeiten
            </button>
          )}
        </div>

        {!decided && !rejected && (
          <div className="mb-[var(--space-md)] flex flex-wrap gap-2">
            <button type="button" onClick={() => setRejectOpen(true)} disabled={setStatus.isPending} className={SECONDARY_BUTTON}>
              <X size={16} /> Abgelehnt
            </button>
          </div>
        )}

        {readOnly && (
          <p className="mb-[var(--space-md)] flex items-center gap-2 text-[14px] text-[var(--color-text-secondary)]">
            <Lock size={14} />
            {rejected
              ? "Abgelehnt – das Angebot ist nur noch lesbar."
              : "Angenommen – das Angebot ist nicht mehr änderbar."}
          </p>
        )}

        {expired && (
          <p className="mb-[var(--space-md)] flex flex-wrap items-center gap-2 text-[14px] text-[var(--color-text-secondary)]">
            <CalendarPlus size={14} />
            Gültig bis {germanDate(quote.valid_until)} – abgelaufen.
            <button
              type="button"
              onClick={extendQuoteValidity}
              disabled={extendValidity.isPending}
              className={SECONDARY_BUTTON}
            >
              {extendValidity.isPending ? "Verlängere…" : "Gültigkeit verlängern"}
            </button>
          </p>
        )}

        {header && !readOnly ? (
          <form onSubmit={(e) => { e.preventDefault(); submitHeader(); }} className="grid gap-[var(--space-sm)] md:grid-cols-3">
            <div className="md:col-span-3"><CustomerSelector value={header.customer_id} onChange={(customer_id) => setHeader({ ...header, customer_id })} /></div>
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)]">
              Betreff
              <input className={INPUT} value={header.subject} onChange={(e) => setHeader({ ...header, subject: e.target.value })} />
            </label>
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)] md:col-span-2">
              Einleitung
              <textarea className={INPUT} value={header.intro_text} onChange={(e) => setHeader({ ...header, intro_text: e.target.value })} maxLength={2000} />
            </label>
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)]">
              Umsatzsteuer (%)
              <input type="number" min="0" max="100" step="0.01" className={INPUT} value={header.vat_rate} onChange={(e) => setHeader({ ...header, vat_rate: Number(e.target.value) })} />
            </label>
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)]">
              Angebotsdatum
              <input type="date" required className={INPUT} value={header.date} onChange={(e) => setHeader({ ...header, date: e.target.value, valid_until: validityTouched ? header.valid_until : addDaysIso(e.target.value, QUOTE_VALIDITY_DAYS) })} />
            </label>
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)]">
              Gültig bis
              <input type="date" min={header.date} className={INPUT} value={header.valid_until} onChange={(e) => { setValidityTouched(true); setHeader({ ...header, valid_until: e.target.value }); }} />
              {header.date && header.valid_until && header.valid_until < header.date && <span role="alert" className="text-red-700">Gültig bis darf nicht vor dem Angebotsdatum liegen.</span>}
            </label>
            <div className="flex gap-2 md:col-span-3">
              <button type="submit" disabled={saveHeader.isPending || !header.date || Boolean(header.valid_until && header.valid_until < header.date)} className={SECONDARY_BUTTON}>
                {saveHeader.isPending ? "Speichere…" : "Speichern"}
              </button>
              <button type="button" onClick={() => setHeader(null)} className={SECONDARY_BUTTON}>
                Abbrechen
              </button>
            </div>
          </form>
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

      <div className="rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white p-[var(--space-lg)] shadow-sm">
        <h2 className="mb-[var(--space-sm)] text-[20px] font-semibold text-[var(--color-text-heading)]">Abrechnen</h2>
        <p className="text-[15px] font-semibold text-[var(--color-text-primary)]">{settlementLabel(settlement)}</p>
        {blockedReasons.length > 0 && (
          <ul className="mt-[var(--space-sm)] space-y-1 text-[14px] text-[var(--color-text-secondary)]">
            {blockedReasons.map((entry) => (
              <li key={entry.reason}>
                <span className="font-semibold text-[var(--color-text-primary)]">{entry.label} nicht möglich:</span>{" "}
                {entry.reason}
                {entry.showLink && entry.invoiceId != null && (
                  <>
                    {" "}
                    <Link
                      to="/invoices/$id"
                      params={{ id: String(entry.invoiceId) }}
                      className="font-semibold text-[var(--color-brand-text)] hover:underline"
                    >
                      Rechnung {entry.invoiceNr || `#${entry.invoiceId}`} öffnen
                    </Link>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="overflow-hidden rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] px-[var(--space-lg)] py-[var(--space-sm)]">
          <h2 className="text-[20px] font-semibold text-[var(--color-text-heading)]">Positionen</h2>
          {!readOnly && (
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
            <li
              key={it.id ?? index}
              data-testid="position-row"
              className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-[var(--color-border)] px-[var(--space-lg)] py-2"
            >
              {/* Am Handy zweizeilig: oben die Beschreibung, unten Betrag und Aktionen (#498). */}
              <div className="w-full min-w-0 grow sm:w-auto">
                <p data-testid="position-description" className="font-semibold text-[var(--color-text-heading)]">{it.description}</p>
                <p className="whitespace-nowrap text-[13px] text-[var(--color-text-secondary)]">
                  {it.quantity} × {eur(it.unit_price)}
                </p>
              </div>
              <span data-testid="position-amount" className="whitespace-nowrap font-mono text-[14px] font-bold">
                {eur(it.quantity * it.unit_price)}
              </span>
              {!readOnly && (
                <>
                  <button type="button" aria-label={`Position ${index + 1} bearbeiten`} onClick={() => setItemDialog({ open: true, item: it })} className={ICON_BUTTON}>
                    <Pencil size={16} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Position ${index + 1} entfernen`}
                    disabled={deleteItem.isPending}
                    onClick={() => setItemToDelete(it)}
                    className={ICON_BUTTON}
                  >
                    <Trash2 size={16} />
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
        <div className="border-t border-[var(--color-border)] px-[var(--space-lg)] py-[var(--space-md)]">
          <dl className="ml-auto max-w-sm space-y-1 text-[14px]">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-[var(--color-text-secondary)]">Netto</dt>
              <dd className="whitespace-nowrap font-mono">{eur(quote.total_net)}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-[var(--color-text-secondary)]">USt {vatRateLabel}</dt>
              <dd className="whitespace-nowrap font-mono">{eur(vatAmount)}</dd>
            </div>
            <div className="flex items-center justify-between gap-4 text-[16px] font-semibold">
              <dt>Gesamt (brutto)</dt>
              <dd className="whitespace-nowrap font-mono">{eur(quote.total_brutto)}</dd>
            </div>
          </dl>
        </div>
      </div>

      <QuotePaymentPlanCard
        quoteId={quoteId}
        gross={quote.total_brutto}
        plan={quote.payment_plan ?? []}
        locked={locked}
        readOnly={rejected}
        invoices={linkedInvoices}
        billing={billing}
        onBillRate={(index) => requestBilling({ kind: "down_payment", index })}
        billingPending={billingPending}
        onDirtyChange={setPlanDirty}
      />

      <div className="rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white p-[var(--space-lg)] shadow-sm">
        <h2 className="mb-[var(--space-sm)] text-[20px] font-semibold text-[var(--color-text-heading)]">Rechnungen</h2>
        {linkedInvoices.length === 0 ? (
          <p className="text-[14px] text-[var(--color-text-secondary)]">Noch keine Rechnung zu diesem Angebot.</p>
        ) : (
          <>
            <ul>
              {linkedInvoices.map((linked) => (
                <li key={linked.id} className="flex min-h-[44px] flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] last:border-b-0">
                  <Link
                    to="/invoices/$id"
                    params={{ id: String(linked.id) }}
                    className="font-semibold text-[var(--color-brand-text)] hover:underline"
                  >
                    {linkedInvoiceLabel(linked)} {linked.nr || `#${linked.id}`}
                  </Link>
                  <span className="flex items-center gap-3">
                    <StatusBadge status={linked.status} />
                    <span className="whitespace-nowrap font-mono text-[14px] font-bold">{eur(linked.total_brutto)}</span>
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
        onDirtyChange={setItemDirty}
        suspendFocus={leaving.status === "blocked"}
      />

      <ConfirmDialog
        open={itemToDelete !== null}
        title="Position entfernen?"
        message="Die Position wird aus dem Angebot entfernt."
        confirmLabel="Entfernen"
        destructive
        pending={deleteItem.isPending}
        onConfirm={() => {
          if (itemToDelete?.id) deleteItem.mutate({ invoiceId: quoteId, itemId: itemToDelete.id }, {
            onSuccess: () => { setItemToDelete(null); notify("success", "Position entfernt"); },
            onError: (err: Error) => notify("error", err.message),
          });
        }}
        onCancel={() => setItemToDelete(null)}
      />

      <ConfirmDialog
        open={leaving.status === "blocked"}
        title="Ungespeicherte Eingaben verwerfen?"
        message="Ihre Änderungen gehen verloren."
        confirmLabel="Verwerfen"
        destructive
        onConfirm={() => leaving.status === "blocked" && leaving.proceed()}
        onCancel={() => leaving.status === "blocked" && leaving.reset()}
      />

      <PdfPreviewModal
        open={previewOpen}
        pdfUrl={previewUrl}
        error={preview.isError}
        refreshing={preview.isFetching}
        onRetry={() => void preview.refetch()}
        invoiceNr={quote.nr || undefined}
        downloadUrl={`/api/invoices/${quoteId}/download`}
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
        error={sendError}
        errorFallback={
          <>
            <p>
              Richten Sie den Versand unter{" "}
              <Link to="/settings" className="font-semibold text-[var(--color-brand-text)] hover:underline">
                Einstellungen → E-Mail
              </Link>{" "}
              ein oder verschicken Sie das Angebot selbst:{" "}
              <a
                href={`/api/invoices/${quoteId}/download`}
                className="font-semibold text-[var(--color-brand-text)] hover:underline"
              >
                PDF herunterladen
              </a>{" "}
              und danach das Angebot als gesendet markieren.
            </p>
            <button
              type="button"
              onClick={markAsSent}
              disabled={markSent.isPending}
              className="mt-2 inline-flex min-h-[44px] items-center gap-1.5 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-3 text-[12px] font-semibold text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-container-high)] disabled:opacity-50"
            >
              <CheckCheck size={14} /> {markSent.isPending ? "Markiere…" : "Als gesendet markieren"}
            </button>
          </>
        }
        onSend={(message, includeAttachments) => sendQuote.mutate({ message, includeAttachments })}
        onCancel={() => {
          setSendOpen(false);
          setSendError(null);
        }}
      />

      <ConfirmDialog
        open={acceptOpen}
        title="Angebot annehmen?"
        message={
          expired
            ? `Dieses Angebot war nur bis ${germanDate(quote.valid_until)} gültig. Ein angenommenes Angebot lässt sich danach nicht mehr ändern.`
            : "Ein angenommenes Angebot lässt sich danach nicht mehr ändern."
        }
        confirmLabel={setStatus.isPending ? "Speichere…" : "Annehmen"}
        pending={setStatus.isPending}
        onConfirm={() => setStatus.mutate("ACCEPTED")}
        onCancel={() => setAcceptOpen(false)}
      />

      <ConfirmDialog
        open={rejectOpen}
        title="Angebot als abgelehnt markieren?"
        message="Danach ist das Angebot nur noch lesbar. Sie können die Entscheidung zurücknehmen, solange keine Rechnung existiert."
        confirmLabel={setStatus.isPending ? "Speichere…" : "Abgelehnt"}
        pending={setStatus.isPending}
        onConfirm={() => setStatus.mutate("REJECTED")}
        onCancel={() => setRejectOpen(false)}
      />

      <ConfirmDialog
        open={billingRequest !== null}
        title="Angebot annehmen und abrechnen?"
        message="Beim Abrechnen gilt das Angebot als angenommen. Danach lässt es sich nicht mehr ändern."
        confirmLabel="Abrechnen"
        pending={convert.isPending || finalInvoice.isPending || billingPending}
        onConfirm={() => {
          const request = billingRequest;
          setBillingRequest(null);
          if (request) runBilling(request);
        }}
        onCancel={() => setBillingRequest(null)}
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
