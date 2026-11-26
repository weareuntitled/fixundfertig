import { useEffect, useState } from "react";
import type { InvoiceItem } from "@/lib/schemas/invoice";
import { useDialogFocus } from "@/components/ui/use-dialog-focus";

interface LineItemDialogProps {
  open: boolean;
  initial?: InvoiceItem;
  onSave: (item: InvoiceItem) => void;
  onCancel: () => void;
}

export function LineItemDialog({ open, initial, onSave, onCancel }: LineItemDialogProps) {
  const [description, setDescription] = useState(initial?.description ?? "");
  const [quantity, setQuantity] = useState<number>(initial?.quantity ?? 1);
  const [unitPrice, setUnitPrice] = useState<number>(initial?.unit_price ?? 0);

  useEffect(() => {
    if (open) {
      setDescription(initial?.description ?? "");
      setQuantity(initial?.quantity ?? 1);
      setUnitPrice(initial?.unit_price ?? 0);
    }
  }, [open, initial]);

  const dialogRef = useDialogFocus<HTMLFormElement>(open, { onEscape: onCancel });

  if (!open) return null;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({ description, quantity, unit_price: unitPrice });
  };

  const isValid = description.trim().length > 0 && quantity > 0 && unitPrice >= 0;

  return (
    // Am Handy liegt der Dialog als Blatt am unteren Rand, damit er vollständig
    // sichtbar bleibt und der Toast oben ihn nicht verdeckt (#498).
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 px-4 backdrop-blur-sm sm:items-center">
      <form
        ref={dialogRef}
        onSubmit={submit}
        className="max-h-[85dvh] w-full max-w-md overflow-y-auto rounded-t-[var(--radius-lg)] border border-[var(--color-surface-border)] bg-[var(--color-surface-card)] p-6 shadow-xl sm:rounded-[var(--radius-lg)]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="line-item-dialog-title"
      >
        <h2 id="line-item-dialog-title" className="mb-4 text-sm font-bold uppercase tracking-[0.15em] text-[var(--color-text-primary)]">
          {initial ? "Position bearbeiten" : "Neue Position"}
        </h2>

        <label className="mb-3 block text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          Beschreibung
          <input
            type="text"
            required
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="mt-1.5 block w-full rounded-[var(--radius)] border border-[var(--color-surface-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] outline-none transition-colors focus:border-[var(--color-brand)] focus:ring-1 focus:ring-[var(--color-brand)]/20"
            placeholder="z.B. Webdesign Leistung"
          />
        </label>

        <div className="mb-4 grid grid-cols-2 gap-3">
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
            Menge
            <input
              type="number"
              step="0.01"
              min="0.01"
              required
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              className="mt-1.5 block w-full rounded-[var(--radius)] border border-[var(--color-surface-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none transition-colors focus:border-[var(--color-brand)] focus:ring-1 focus:ring-[var(--color-brand)]/20"
            />
          </label>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
            Einzelpreis (€)
            <input
              type="number"
              step="0.01"
              min="0"
              required
              value={unitPrice}
              onChange={(e) => setUnitPrice(Number(e.target.value))}
              className="mt-1.5 block w-full rounded-[var(--radius)] border border-[var(--color-surface-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none transition-colors focus:border-[var(--color-brand)] focus:ring-1 focus:ring-[var(--color-brand)]/20"
            />
          </label>
        </div>

        {/* Preview */}
        {isValid && (
          <div className="mb-4 rounded-[var(--radius)] border border-[var(--color-surface-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-xs text-[var(--color-text-muted)]">
            Gesamt:{" "}
            <span className="font-mono font-semibold text-[var(--color-text-primary)]">
              {(quantity * unitPrice).toLocaleString("de-DE", { minimumFractionDigits: 2 })} €
            </span>
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="min-h-[44px] rounded-[var(--radius)] px-3 py-2 text-xs font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text-secondary)]"
          >
            Abbrechen
          </button>
          <button
            type="submit"
            disabled={!isValid}
            className="min-h-[44px] rounded-[var(--radius)] bg-[var(--color-brand)] px-4 py-2 text-xs font-semibold text-[var(--color-text-on-brand)] transition-all hover:bg-[var(--color-brand-hover)] disabled:opacity-50"
          >
            Übernehmen
          </button>
        </div>
      </form>
    </div>
  );
}
