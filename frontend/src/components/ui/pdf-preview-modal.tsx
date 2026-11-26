import { createPortal } from "react-dom";
import { Download, Printer, X } from "lucide-react";
import { useDialogFocus } from "./use-dialog-focus";

interface PdfPreviewModalProps {
  open: boolean;
  pdfUrl: string | null;
  invoiceNr?: string;
  /** "QUOTE" names the document "Angebot" and its file "angebot_{nr}.pdf". */
  documentType?: "INVOICE" | "QUOTE";
  error?: boolean;
  refreshing?: boolean;
  onRetry?: () => void;
  onClose: () => void;
}

export function PdfPreviewModal({ open, pdfUrl, invoiceNr, documentType = "INVOICE", error, refreshing, onRetry, onClose }: PdfPreviewModalProps) {
  const dialogRef = useDialogFocus<HTMLElement>(open, { onEscape: onClose });
  if (!open) return null;

  const quote = documentType === "QUOTE";
  const title = `${quote ? "Angebot" : "Rechnung"} ${invoiceNr || "Vorschau"}`;
  const fileName = quote ? `angebot_${invoiceNr || "entwurf"}.pdf` : `rechnung_${invoiceNr || "entwurf"}.pdf`;
  const content = (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4">
      <div aria-hidden="true" className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="pdf-preview-title"
        className="relative flex max-h-[calc(100vh-2rem)] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-[var(--color-border)] bg-white shadow-2xl"
      >
        <header className="flex shrink-0 items-center justify-between border-b border-[var(--color-border)] px-4 py-3 sm:px-6">
          <h2 id="pdf-preview-title" className="text-sm font-bold text-[var(--color-text-primary)] sm:text-base">
            PDF-Vorschau · {title}
            {refreshing && pdfUrl && <span className="ml-2 font-normal">Wird aktualisiert…</span>}
          </h2>
          <div className="flex items-center gap-2">
            {pdfUrl && (
              <>
                <a
                  href={pdfUrl}
                  download={fileName}
                  className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-[var(--color-brand)] px-3 py-1.5 text-xs font-semibold text-white"
                >
                  <Download size={14} /> PDF herunterladen
                </a>
                <a
                  href={pdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hidden min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold sm:inline-flex"
                >
                  <Printer size={14} /> Drucken
                </a>
              </>
            )}
            <button type="button" onClick={onClose} aria-label="Schließen" className="inline-flex h-11 w-11 items-center justify-center rounded-full hover:bg-gray-100">
              <X size={16} />
            </button>
          </div>
        </header>
        {error ? (
          <div role="alert" className="flex min-h-[70vh] flex-col items-center justify-center gap-3 text-sm">
            <p>Die PDF-Vorschau konnte nicht geladen werden.</p>
            {onRetry && <button type="button" onClick={onRetry} className="rounded-lg border px-4 py-2">Erneut versuchen</button>}
          </div>
        ) : pdfUrl ? (
          <iframe title={`PDF-${title}`} src={pdfUrl} className="min-h-[70vh] w-full flex-1 bg-white" />
        ) : (
          <div className="flex min-h-[70vh] items-center justify-center text-sm text-[var(--color-text-secondary)]">
            PDF wird erstellt…
          </div>
        )}
      </section>
    </div>
  );

  const portalRoot = typeof document !== "undefined" ? document.getElementById("portal-root") : null;
  return portalRoot ? createPortal(content, portalRoot) : content;
}
