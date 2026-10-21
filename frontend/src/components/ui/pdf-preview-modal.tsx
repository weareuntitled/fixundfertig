import { createPortal } from "react-dom";
import { Download, Printer, X } from "lucide-react";

interface PdfPreviewModalProps {
  open: boolean;
  pdfUrl: string | null;
  invoiceNr?: string;
  onClose: () => void;
}

export function PdfPreviewModal({ open, pdfUrl, invoiceNr, onClose }: PdfPreviewModalProps) {
  if (!open) return null;

  const title = `Rechnung ${invoiceNr || "Vorschau"}`;
  const content = (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4">
      <button
        type="button"
        aria-label="Vorschau schließen"
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="pdf-preview-title"
        className="relative flex max-h-[calc(100vh-2rem)] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-[var(--color-border)] bg-white shadow-2xl"
      >
        <header className="flex shrink-0 items-center justify-between border-b border-[var(--color-border)] px-4 py-3 sm:px-6">
          <h2 id="pdf-preview-title" className="text-sm font-bold text-[var(--color-text-primary)] sm:text-base">
            PDF-Vorschau · {title}
          </h2>
          <div className="flex items-center gap-2">
            {pdfUrl && (
              <>
                <a
                  href={pdfUrl}
                  download={`rechnung-${invoiceNr || "entwurf"}.pdf`}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-brand)] px-3 py-1.5 text-xs font-semibold text-white"
                >
                  <Download size={14} /> PDF herunterladen
                </a>
                <a
                  href={pdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hidden items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold sm:inline-flex"
                >
                  <Printer size={14} /> Drucken
                </a>
              </>
            )}
            <button type="button" onClick={onClose} aria-label="Schließen" className="rounded-full p-2 hover:bg-gray-100">
              <X size={16} />
            </button>
          </div>
        </header>
        {pdfUrl ? (
          <iframe title={`PDF-${title}`} src={pdfUrl} className="min-h-[70vh] w-full flex-1 bg-white" />
        ) : (
          <div className="flex min-h-[70vh] items-center justify-center text-sm text-[var(--color-text-muted)]">
            PDF wird erstellt…
          </div>
        )}
      </section>
    </div>
  );

  const portalRoot = typeof document !== "undefined" ? document.getElementById("portal-root") : null;
  return portalRoot ? createPortal(content, portalRoot) : content;
}
