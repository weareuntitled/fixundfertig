/**
 * @schema ConfirmDialog
 * @purpose Confirmation for steps that cannot be taken back. Same look as the delete confirmation:
 * plain dim backdrop, white card, outline cancel, filled confirm (red when destructive).
 */
import { useEffect, useId, type ReactNode } from "react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  pending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel = "Abbrechen",
  destructive = false,
  pending = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId();
  const messageId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pending) onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, pending, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={() => !pending && onCancel()} />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        className="animate-fade-in relative mx-4 w-full max-w-sm rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-white p-[var(--space-xl)] shadow-xl"
      >
        <h3 id={titleId} className="mb-2 text-[20px] font-semibold text-[var(--color-text-heading)]">
          {title}
        </h3>
        <p id={messageId} className="mb-6 text-[14px] text-[var(--color-text-secondary)]">
          {message}
        </p>
        <div className="flex justify-end gap-[var(--space-sm)]">
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            autoFocus={destructive}
            className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white px-[var(--space-md)] py-[var(--space-xs)] text-[12px] font-semibold text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-container-high)] disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={pending}
            autoFocus={!destructive}
            className={`rounded-[var(--radius-lg)] px-[var(--space-md)] py-[var(--space-xs)] text-[12px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50 ${
              destructive ? "bg-red-600" : "bg-[#001a42]"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
