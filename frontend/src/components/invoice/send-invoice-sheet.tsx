/**
 * @schema SendInvoiceSheet
 * @purpose Modal sheet to send an invoice by email with an optional personal message.
 * iOS idiom: bottom sheet on phones, centred card on larger screens; Cancel left, title centre,
 * primary action right; inset grouped fields; 44pt touch targets; safe-area padding.
 */
import { useEffect, useId, useRef, useState } from "react";

export const MAX_MESSAGE_LENGTH = 2000;

interface SendInvoiceSheetProps {
  open: boolean;
  recipientName: string;
  recipientEmail?: string;
  pending?: boolean;
  onSend: (message: string) => void;
  onCancel: () => void;
}

export function SendInvoiceSheet({
  open,
  recipientName,
  recipientEmail,
  pending = false,
  onSend,
  onCancel,
}: SendInvoiceSheetProps) {
  const [message, setMessage] = useState("");
  const titleId = useId();
  const fieldId = useId();
  const hintId = useId();
  const fieldRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) {
      setMessage("");
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
    if (!pending) onSend(message.trim());
  };

  const nearLimit = message.length > MAX_MESSAGE_LENGTH - 200;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 backdrop-blur-sm sm:items-center sm:px-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !pending) onCancel();
      }}
    >
      <form
        onSubmit={submit}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="w-full max-w-md overflow-hidden rounded-t-[14px] bg-[var(--color-surface-sunken)] shadow-xl sm:rounded-[14px]"
      >
        <header className="grid grid-cols-[1fr_auto_1fr] items-center border-b border-[var(--color-border)] bg-[var(--color-surface-card)] px-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="min-h-[44px] justify-self-start rounded-[8px] px-3 text-[17px] text-[var(--color-brand)] transition-opacity active:opacity-60 disabled:opacity-40"
          >
            Abbrechen
          </button>
          <h2 id={titleId} className="text-[17px] font-semibold text-[var(--color-text-heading)]">
            Rechnung senden
          </h2>
          <button
            type="submit"
            disabled={pending}
            className="min-h-[44px] justify-self-end rounded-[8px] px-3 text-[17px] font-semibold text-[var(--color-brand)] transition-opacity active:opacity-60 disabled:opacity-40"
          >
            {pending ? "Sende…" : "Senden"}
          </button>
        </header>

        <div className="space-y-6 px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-5">
          <div className="overflow-hidden rounded-[10px] bg-[var(--color-surface-card)]">
            <div className="flex min-h-[44px] items-center justify-between gap-4 px-4 py-2">
              <span className="text-[17px] text-[var(--color-text-heading)]">An</span>
              <span className="min-w-0 text-right">
                <span className="block truncate text-[17px] text-[var(--color-text-secondary)]">{recipientName}</span>
                {recipientEmail && (
                  <span className="block truncate text-[13px] text-[var(--color-text-tertiary)]">{recipientEmail}</span>
                )}
              </span>
            </div>
          </div>

          <div>
            <label
              htmlFor={fieldId}
              className="mb-1.5 block px-4 text-[13px] uppercase tracking-wide text-[var(--color-text-secondary)]"
            >
              Persönliche Nachricht
            </label>
            <div className="overflow-hidden rounded-[10px] bg-[var(--color-surface-card)]">
              <textarea
                id={fieldId}
                ref={fieldRef}
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                maxLength={MAX_MESSAGE_LENGTH}
                rows={6}
                aria-describedby={hintId}
                placeholder="Optional, zum Beispiel ein kurzer Dank oder ein Gruß"
                className="block min-h-[132px] w-full resize-none bg-transparent px-4 py-3 text-[17px] leading-[1.35] text-[var(--color-text-heading)] outline-none placeholder:text-[var(--color-text-placeholder)]"
              />
            </div>
            <p
              id={hintId}
              className="mt-1.5 flex justify-between gap-4 px-4 text-[13px] leading-snug text-[var(--color-text-secondary)]"
            >
              <span>Ohne Text geht der Standardtext raus. Die Rechnung hängt immer als PDF an.</span>
              {nearLimit && (
                <span aria-live="polite" className="shrink-0 tabular-nums">
                  {message.length}/{MAX_MESSAGE_LENGTH}
                </span>
              )}
            </p>
          </div>
        </div>
      </form>
    </div>
  );
}
