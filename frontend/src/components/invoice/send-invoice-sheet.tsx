/**
 * @schema SendInvoiceSheet
 * @purpose Modal to send an invoice by email with an optional personal message.
 * Looks like the app's other modals (plain dim backdrop, white card, 12px actions);
 * on phones it sits at the bottom edge as a sheet.
 */
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Loader2, Paperclip, Upload } from "lucide-react";

export const MAX_MESSAGE_LENGTH = 2000;

interface SendInvoiceSheetProps {
  open: boolean;
  recipientName: string;
  recipientEmail?: string;
  attachmentCount?: number;
  uploading?: boolean;
  onAddFile?: (file: File) => void;
  pending?: boolean;
  onSend: (message: string, includeAttachments: boolean) => void;
  onCancel: () => void;
}

export function SendInvoiceSheet({
  open,
  recipientName,
  recipientEmail,
  attachmentCount = 0,
  uploading = false,
  onAddFile,
  pending = false,
  onSend,
  onCancel,
}: SendInvoiceSheetProps) {
  const [message, setMessage] = useState("");
  const [excludeAttachments, setExcludeAttachments] = useState(false);
  const includeAttachments = attachmentCount > 0 && !excludeAttachments;
  const titleId = useId();
  const fieldId = useId();
  const hintId = useId();
  const attachId = useId();
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Reset only when the dialog opens, not when the invoice refetches underneath it.
  useEffect(() => {
    if (open) {
      setMessage("");
      setExcludeAttachments(false);
      fieldRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pending) onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, pending, onCancel]);

  if (!open) return null;

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!pending) onSend(message.trim(), includeAttachments);
  };

  const nearLimit = message.length > MAX_MESSAGE_LENGTH - 200;

  // Portaled to <body>: inside the page layout a transformed ancestor would anchor `fixed` to itself.
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:px-4">
      <div className="absolute inset-0 bg-black/40" onClick={() => !pending && onCancel()} />
      <form
        onSubmit={submit}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="animate-fade-in relative w-full max-w-md rounded-t-[var(--radius-xl)] border border-[var(--color-border)] bg-white p-[var(--space-xl)] pb-[max(var(--space-xl),env(safe-area-inset-bottom))] shadow-xl sm:rounded-[var(--radius-xl)]"
      >
        <h3 id={titleId} className="mb-1 text-[20px] font-semibold text-[var(--color-text-heading)]">
          Rechnung senden
        </h3>
        <p className="mb-5 break-words text-[14px] text-[var(--color-text-secondary)]">
          An {recipientName}
          {recipientEmail && <span className="text-[var(--color-text-tertiary)]"> · {recipientEmail}</span>}
        </p>

        <label
          htmlFor={fieldId}
          className="block text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]"
        >
          Persönliche Nachricht (optional)
        </label>
        <textarea
          id={fieldId}
          ref={fieldRef}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          maxLength={MAX_MESSAGE_LENGTH}
          rows={6}
          aria-describedby={hintId}
          placeholder="z. B. ein kurzer Dank oder ein Gruß"
          className="mt-1.5 block w-full resize-none rounded-[var(--radius)] border border-[var(--color-surface-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm leading-relaxed text-[var(--color-text-primary)] outline-none transition-colors placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-brand)] focus:ring-1 focus:ring-[var(--color-brand)]/20"
        />
        <p id={hintId} className="mt-1.5 flex justify-between gap-4 text-[12px] text-[var(--color-text-muted)]">
          <span>Ohne Text geht der Standardtext raus. Die Rechnung hängt immer als PDF an.</span>
          {nearLimit && (
            <span aria-live="polite" className="shrink-0 tabular-nums">
              {message.length}/{MAX_MESSAGE_LENGTH}
            </span>
          )}
        </p>

        {attachmentCount > 0 && (
          <label
            htmlFor={attachId}
            className="mt-4 flex cursor-pointer items-start gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface-bright)] p-3"
          >
            <input
              id={attachId}
              type="checkbox"
              checked={includeAttachments}
              onChange={(event) => setExcludeAttachments(!event.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--color-brand-text)]"
            />
            <span>
              <span className="flex items-center gap-1.5 text-[13px] font-semibold text-[var(--color-text-primary)]">
                <Paperclip size={14} />
                Belege mitschicken ({attachmentCount})
              </span>
              <span className="mt-0.5 block text-[12px] text-[var(--color-text-muted)]">
                Die Belege werden als separate PDFs an die E-Mail angehängt.
              </span>
            </span>
          </label>
        )}

        {onAddFile && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-[12px] text-[var(--color-text-muted)]">
              {attachmentCount === 0 ? "Noch keine Anlagen. PDF, JPG oder PNG." : "Weitere Anlage hinzufügen:"}
            </p>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
              className="hidden"
              aria-label="Anlage auswählen"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) onAddFile(file);
              }}
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploading || pending}
              className="inline-flex min-h-[44px] items-center gap-1.5 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-3 text-[12px] font-semibold text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-container-high)] disabled:opacity-50"
            >
              {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
              Anlage hinzufügen
            </button>
          </div>
        )}

        <div className="mt-6 flex justify-end gap-[var(--space-sm)]">
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="min-h-[44px] rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-[var(--space-md)] text-[12px] font-semibold text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-container-high)] disabled:opacity-50 sm:min-h-0 sm:py-[var(--space-xs)]"
          >
            Abbrechen
          </button>
          <button
            type="submit"
            disabled={pending}
            className="min-h-[44px] rounded-[var(--radius-lg)] bg-[#001a42] px-[var(--space-md)] text-[12px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50 sm:min-h-0 sm:py-[var(--space-xs)]"
          >
            {pending ? "Sende…" : "Senden"}
          </button>
        </div>
      </form>
    </div>,
    document.body,
  );
}
