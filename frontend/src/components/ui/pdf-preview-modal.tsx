import { createPortal } from "react-dom";
import { Download, Printer, X } from "lucide-react";
import type { InvoiceItem } from "@/lib/schemas/invoice";

export interface PreviewInvoice {
  nr?: string | null;
  title: string;
  date: string;
  delivery_date?: string;
  recipient_name?: string;
  recipient_street?: string;
  recipient_postal_code?: string;
  recipient_city?: string;
  items: InvoiceItem[];
  vat_rate?: number;
  ust_enabled?: boolean;
  notes?: string;
  total_brutto?: number;
}

export interface PreviewCustomer {
  name: string;
  email?: string;
  street?: string;
  postal_code?: string;
  city?: string;
}

export interface PreviewCompany {
  name: string;
  street?: string;
  postal_code?: string;
  city?: string;
  email?: string;
  phone?: string;
  bank_name?: string;
  iban?: string;
}

interface PdfPreviewModalProps {
  open: boolean;
  pdfUrl: string | null;
  invoice: PreviewInvoice;
  customer?: PreviewCustomer;
  company?: PreviewCompany;
  invoiceNr?: string;
  onClose: () => void;
}

const eur = (n: number) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

const formatDate = (iso: string) => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  return `${d}.${m}.${y}`;
};

function PdfPreviewContent({
  pdfUrl,
  invoice,
  customer,
  company,
  invoiceNr,
  onClose,
}: PdfPreviewModalProps) {
  if (!invoice) return null;

  const subtotal = invoice.items.reduce((sum, it) => sum + it.quantity * it.unit_price, 0);
  const vatRate = invoice.vat_rate ?? 19;
  const ustEnabled = invoice.ust_enabled ?? true;
  const total =
    invoice.total_brutto && invoice.total_brutto > 0
      ? invoice.total_brutto
      : subtotal + (ustEnabled ? subtotal * (vatRate / 100) : 0);
  const tax = ustEnabled ? total - subtotal : 0;

  const billTo = customer
    ? {
        name: customer.name,
        address: [customer.street, [customer.postal_code, customer.city].filter(Boolean).join(" ")]
          .filter(Boolean)
          .join("\n"),
        email: customer.email,
      }
    : {
        name: invoice.recipient_name || "—",
        address: [
          invoice.recipient_street,
          [invoice.recipient_postal_code, invoice.recipient_city].filter(Boolean).join(" "),
        ]
          .filter(Boolean)
          .join("\n"),
        email: "",
      };

  const filename = `rechnung-${invoiceNr || invoice.nr || "entwurf"}.pdf`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4">
      <div
        className="absolute inset-0"
        style={{
          backgroundColor: "var(--modal-backdrop)",
          backdropFilter: "blur(var(--modal-backdrop-blur))",
        }}
        onClick={onClose}
      />

      <div className="relative w-full max-w-6xl max-h-[calc(100vh-1rem)] sm:max-h-[calc(100vh-2rem)] rounded-[var(--modal-radius)] shadow-[var(--modal-shadow)] flex flex-col overflow-hidden border border-[var(--color-border)]"
        style={{ backgroundColor: "var(--color-surface-dim)" }}
      >
        <div className="bg-white border-b border-[var(--color-border)] px-4 sm:px-6 py-2 sm:py-3 flex justify-between items-center shrink-0">
          <div className="flex items-center gap-2 sm:gap-3">
            <span className="material-symbols-outlined text-[var(--color-text-primary)] text-lg sm:text-xl">
              picture_as_pdf
            </span>
            <h3 className="text-sm sm:text-base font-bold text-[var(--color-text-primary)]">
              Rechnungsvorschau
            </h3>
          </div>
          <div className="flex items-center gap-1 sm:gap-2">
            {pdfUrl && (
              <a
                href={pdfUrl}
                download={filename}
                className="inline-flex items-center gap-1 sm:gap-1.5 rounded-[var(--radius-lg)] bg-[var(--color-brand)] px-2 sm:px-3 py-1 sm:py-1.5 text-[11px] sm:text-xs font-semibold text-[var(--color-text-on-brand)] transition-colors hover:bg-[var(--color-brand-hover)]"
              >
                <Download size={13} />
                <span className="hidden sm:inline">PDF herunterladen</span>
              </a>
            )}
            {pdfUrl && (
              <a
                href={pdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 sm:gap-1.5 rounded-[var(--radius-lg)] bg-white border border-[var(--color-border)] px-2 sm:px-3 py-1 sm:py-1.5 text-[11px] sm:text-xs font-semibold text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-container-low)]"
              >
                <Printer size={13} />
                <span className="hidden sm:inline">Drucken</span>
              </a>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-full p-1 sm:p-1.5 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-container-low)] ml-1"
              aria-label="Schließen"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-3 sm:p-6 flex justify-center" style={{ backgroundColor: "#f0f2f5" }}>
          <div
            className="bg-white shadow-[0_20px_50px_rgba(0,0,0,0.1)] flex flex-col border border-[var(--color-border)] w-full max-w-[210mm]"
            style={{ minWidth: 0 }}
          >
            <div className="flex flex-col sm:flex-row justify-between items-start gap-3 sm:gap-0 mb-4 sm:mb-6 pb-4 sm:pb-5 border-b-2 border-[var(--color-border)]">
              <div>
                <h2 className="text-xl sm:text-[28px] font-bold text-[var(--color-text-primary)] leading-tight">
                  {company?.name || "FixundFertig"}
                </h2>
                <p className="text-[11px] sm:text-[12px] text-[var(--color-text-secondary)]">
                  {company?.street && (
                    <>{company.street}<br /></>
                  )}
                  {[company?.postal_code, company?.city].filter(Boolean).join(" ")}
                </p>
              </div>
              <div className="text-left sm:text-right">
                <h1 className="text-2xl sm:text-[32px] font-black uppercase text-[var(--color-text-primary)] tracking-widest">
                  Rechnung
                </h1>
                <p className="text-sm sm:text-base font-bold text-[var(--color-text-secondary)] font-mono">
                  #{invoice.nr || invoiceNr || "ENTWURF"}
                </p>
              </div>
            </div>

            <div className="flex flex-col sm:grid sm:grid-cols-2 gap-4 sm:gap-6 mb-4 sm:mb-6">
              <div className="space-y-1">
                <p className="text-[10px] sm:text-[11px] text-[var(--color-text-secondary)] uppercase font-bold tracking-wider">
                  Rechnungsempfänger
                </p>
                <h4 className="text-sm sm:text-base font-bold text-[var(--color-text-primary)]">
                  {billTo.name}
                </h4>
                {billTo.address && (
                  <p className="text-[11px] sm:text-xs text-[var(--color-text-secondary)] leading-relaxed whitespace-pre-line">
                    {billTo.address}
                  </p>
                )}
                {billTo.email && (
                  <p className="text-[11px] sm:text-xs text-[var(--color-text-secondary)]">{billTo.email}</p>
                )}
              </div>
              <div className="flex flex-col items-start sm:items-end gap-1">
                <div className="flex flex-col sm:flex-row gap-2 sm:gap-4">
                  <div className="text-left sm:text-right">
                    <p className="text-[10px] sm:text-[11px] text-[var(--color-text-secondary)] uppercase font-bold tracking-wider">
                      Rechnungsdatum
                    </p>
                    <p className="text-xs font-bold">{formatDate(invoice.date)}</p>
                  </div>
                  {invoice.delivery_date && (
                    <div className="text-left sm:text-right">
                      <p className="text-[10px] sm:text-[11px] text-[var(--color-text-secondary)] uppercase font-bold tracking-wider">
                        Leistungsdatum
                      </p>
                      <p className="text-xs font-bold">{formatDate(invoice.delivery_date)}</p>
                    </div>
                  )}
                </div>
                <div className="mt-2 sm:mt-3 px-3 sm:px-4 py-1.5 sm:py-2 bg-[var(--color-surface-container-low)] rounded border border-[var(--color-border)] w-full sm:w-auto">
                  <p className="text-[10px] sm:text-[11px] text-[var(--color-text-secondary)] uppercase font-bold tracking-wider">
                    Gesamtbetrag
                  </p>
                  <p className="text-lg sm:text-2xl font-bold text-[var(--color-text-primary)] font-mono">
                    {eur(total)}
                  </p>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-x-auto">
              {invoice.items.length === 0 ? (
                <div className="rounded border border-dashed border-[var(--color-border)] px-4 py-8 text-center text-sm text-[var(--color-text-muted)]">
                  Noch keine Positionen erfasst.
                </div>
              ) : (
                <table className="w-full text-left border-collapse min-w-[280px]">
                  <thead>
                    <tr className="bg-[var(--color-text-heading)] text-white">
                      <th className="py-1.5 sm:py-2 px-2 sm:px-3 text-[10px] sm:text-[11px] uppercase tracking-wider font-bold rounded-tl">
                        Beschreibung
                      </th>
                      <th className="py-1.5 sm:py-2 px-2 sm:px-3 text-[10px] sm:text-[11px] uppercase tracking-wider font-bold text-center w-12 sm:w-16">
                        Menge
                      </th>
                      <th className="py-1.5 sm:py-2 px-2 sm:px-3 text-[10px] sm:text-[11px] uppercase tracking-wider font-bold text-right w-20 sm:w-24">
                        Einzelpreis
                      </th>
                      <th className="py-1.5 sm:py-2 px-2 sm:px-3 text-[10px] sm:text-[11px] uppercase tracking-wider font-bold text-right w-24 sm:w-28 rounded-tr">
                        Gesamt
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border)]">
                    {invoice.items.map((it, idx) => (
                      <tr key={idx} className="bg-white">
                        <td className="py-2 sm:py-3 px-2 sm:px-3 text-xs font-bold text-[var(--color-text-primary)] break-words">
                          {it.description}
                        </td>
                        <td className="py-2 sm:py-3 px-2 sm:px-3 text-xs text-center font-mono">
                          {it.quantity}
                        </td>
                        <td className="py-2 sm:py-3 px-2 sm:px-3 text-xs text-right font-mono">
                          {eur(it.unit_price)}
                        </td>
                        <td className="py-2 sm:py-3 px-2 sm:px-3 text-xs text-right font-bold font-mono">
                          {eur(it.quantity * it.unit_price)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="mt-4 sm:mt-6 flex justify-end">
              <div className="w-full sm:w-64 space-y-1.5 sm:space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-[var(--color-text-secondary)]">Nettobetrag:</span>
                  <span className="font-bold text-[var(--color-text-primary)] font-mono">
                    {eur(subtotal)}
                  </span>
                </div>
                {ustEnabled && (
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--color-text-secondary)]">
                      USt ({vatRate}%):
                    </span>
                    <span className="font-bold text-[var(--color-text-primary)] font-mono">
                      {eur(tax)}
                    </span>
                  </div>
                )}
                <div className="pt-1.5 sm:pt-2 border-t-2 border-[var(--color-text-heading)] flex justify-between items-center">
                  <span className="text-sm sm:text-base font-bold text-[var(--color-text-primary)] uppercase tracking-tight">
                    Gesamt:
                  </span>
                  <span className="text-sm sm:text-base font-black text-[var(--color-text-primary)] font-mono">
                    {eur(total)}
                  </span>
                </div>
              </div>
            </div>

            {invoice.notes && (
              <div className="mt-4 sm:mt-auto pt-4 sm:pt-6">
                <div className="p-2 sm:p-3 bg-[var(--color-surface-container-lowest)] rounded-lg border border-[var(--color-border)]">
                  <h5 className="text-[10px] sm:text-[11px] text-[var(--color-text-secondary)] uppercase font-bold tracking-wider mb-1">
                    Notizen / Zahlungsbedingungen
                  </h5>
                  <p className="text-xs text-[var(--color-text-primary)] leading-relaxed italic whitespace-pre-line">
                    {invoice.notes}
                  </p>
                </div>
              </div>
            )}

            <div className="mt-4 sm:mt-6 pt-2 sm:pt-3 border-t border-[var(--color-border)] text-center">
              <p className="text-[9px] sm:text-[10px] text-[var(--color-text-secondary)] uppercase tracking-[3px] font-mono">
                {window.location.host}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function PdfPreviewModal(props: PdfPreviewModalProps) {
  if (!props.open) return null;

  const portalRoot = typeof document !== "undefined" ? document.getElementById("portal-root") : null;
  if (portalRoot) {
    return createPortal(<PdfPreviewContent {...props} />, portalRoot);
  }

  return <PdfPreviewContent {...props} />;
}
