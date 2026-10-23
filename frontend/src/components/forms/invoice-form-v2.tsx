/**
 * @schema InvoiceFormV2
 * @purpose Invoice creation form: customer, subject, dates, positions edited in place, totals
 * @input {InvoiceDraft} value - Current invoice draft state
 * @input {(next: InvoiceDraft) => void} onChange - State update callback
 * @output One white card; every field says what it does and what happens when it is left empty
 */
import { useEffect, useId, useState, type ReactNode } from "react";
import { Trash2 } from "lucide-react";
import { CustomerSelector } from "./customer-selector";
import { dueDateLabel, PAYMENT_TERM_DAYS } from "@/lib/invoice-draft";
import type { InvoiceDraft, InvoiceItem } from "@/lib/schemas/invoice";

interface InvoiceFormV2Props {
  value: InvoiceDraft;
  onChange: (next: InvoiceDraft) => void;
}

const INPUT =
  "w-full bg-white border border-[var(--color-border)] rounded-[var(--radius-lg)] px-[var(--space-sm)] py-2 text-[14px] text-[var(--color-text-primary)] focus:border-[#001a42] focus:ring-1 focus:ring-[#001a42] transition-all duration-150 outline-none";
const CELL_INPUT =
  "w-full bg-transparent border-0 border-b border-transparent focus:border-[#001a42] focus:ring-0 px-0 py-1 text-[14px] text-[var(--color-text-primary)] outline-none transition-colors placeholder:text-[var(--color-text-secondary)]";
const money = (value: number) => value.toLocaleString("de-DE", { minimumFractionDigits: 2 });

function FormField({ label, hint, children }: { label: string; hint?: string; children: (ids: { id: string; hintId?: string }) => ReactNode }) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div>
      <label htmlFor={id} className="mb-[var(--space-xs)] block text-[14px] font-bold text-[var(--color-text-primary)]">
        {label}
      </label>
      {children({ id, hintId })}
      {hint && (
        <p id={hintId} className="mt-1 text-[12px] text-[var(--color-text-muted)]">
          {hint}
        </p>
      )}
    </div>
  );
}

export function InvoiceFormV2({ value, onChange }: InvoiceFormV2Props) {
  const [removed, setRemoved] = useState<{ item: InvoiceItem; index: number } | null>(null);
  const [focusIndex, setFocusIndex] = useState<number | null>(null);
  const [touched, setTouched] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!removed) return;
    const timer = setTimeout(() => setRemoved(null), 8000);
    return () => clearTimeout(timer);
  }, [removed]);

  const setField = <K extends keyof InvoiceDraft>(key: K, v: InvoiceDraft[K]) => onChange({ ...value, [key]: v });

  const addItem = () => {
    setFocusIndex(value.items.length);
    setField("items", [...value.items, { description: "", quantity: 1, unit_price: 0 }]);
  };

  const removeItem = (idx: number) => {
    setRemoved({ item: value.items[idx], index: idx });
    setField("items", value.items.filter((_, i) => i !== idx));
  };

  const undoRemove = () => {
    if (!removed) return;
    const next = [...value.items];
    next.splice(Math.min(removed.index, next.length), 0, removed.item);
    setField("items", next);
    setRemoved(null);
  };

  const updateItemField = (idx: number, field: keyof InvoiceItem, val: string | number) => {
    const next = [...value.items];
    next[idx] = { ...next[idx], [field]: val };
    setField("items", next);
  };

  const subtotalNet = value.items.reduce((sum, it) => sum + it.quantity * it.unit_price, 0);
  const taxAmount = value.ust_enabled ? subtotalNet * (value.vat_rate / 100) : 0;
  const gross = subtotalNet + taxAmount;
  const due = dueDateLabel(value.date);

  return (
    <div className="space-y-0">
      {/* Header: customer and subject on the left, number and dates on the right */}
      <div className="mb-[var(--space-xl)] grid grid-cols-12 gap-[var(--space-gutter)] border-b border-[var(--color-border)] pb-[var(--space-xl)]">
        <div className="col-span-12 space-y-[var(--space-md)] md:col-span-6">
          <CustomerSelector value={value.customer_id} onChange={(id) => setField("customer_id", id)} />

          <FormField label="Betreff" hint="Steht fett über dem Einleitungstext, auch in der Mail. Leer ist in Ordnung.">
            {({ id, hintId }) => (
              <input
                id={id}
                aria-describedby={hintId}
                type="text"
                value={value.subject}
                onChange={(e) => setField("subject", e.target.value)}
                placeholder="z. B. DJ-Set Hammahalle, Sa auf So"
                className={INPUT}
              />
            )}
          </FormField>
        </div>

        <div className="col-span-12 grid grid-cols-2 gap-[var(--space-sm)] md:col-span-6">
          <p className="col-span-2 text-[14px] text-[var(--color-text-secondary)]">
            <span className="font-bold text-[var(--color-text-primary)]">Rechnungsnummer</span>
            <br />
            Wird beim Erstellen vergeben und lässt sich danach nicht mehr ändern.
          </p>
          <FormField label="Rechnungsdatum">
            {({ id }) => (
              <input id={id} type="date" value={value.date} onChange={(e) => setField("date", e.target.value)} className={INPUT} />
            )}
          </FormField>
          <FormField label="Leistungsdatum" hint="Leer = wie Rechnungsdatum.">
            {({ id, hintId }) => (
              <input
                id={id}
                aria-describedby={hintId}
                type="date"
                value={value.delivery_date}
                onChange={(e) => setField("delivery_date", e.target.value)}
                className={INPUT}
              />
            )}
          </FormField>
          <p className="col-span-2 text-[13px] text-[var(--color-text-secondary)]">
            Zahlungsziel {PAYMENT_TERM_DAYS} Tage
            {due ? (
              <>
                {" "}
                · zahlbar bis <span className="font-semibold text-[var(--color-text-primary)]">{due}</span>
              </>
            ) : null}
          </p>
        </div>
      </div>

      {/* Intro text */}
      <div className="mb-[var(--space-xl)]">
        <FormField label="Einleitung" hint="Optional. Ohne Text steht: „Vielen Dank für den Auftrag. Hiermit stelle ich folgende Leistungen in Rechnung.“">
          {({ id, hintId }) => (
            <textarea
              id={id}
              aria-describedby={hintId}
              value={value.intro_text}
              onChange={(e) => setField("intro_text", e.target.value)}
              rows={2}
              maxLength={2000}
              className={`${INPUT} resize-y`}
            />
          )}
        </FormField>
      </div>

      {/* Positions, edited in place */}
      <div className="mb-[var(--space-xl)]">
        <h3 className="mb-[var(--space-md)] text-[20px] font-semibold text-[var(--color-text-primary)]">Positionen</h3>
        <div className="w-full overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-y border-[var(--color-border)] bg-[#F1F5F9]">
                <th className="w-1/2 px-[var(--space-sm)] py-[var(--space-xs)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)]">Beschreibung</th>
                <th className="w-1/6 px-[var(--space-sm)] py-[var(--space-xs)] text-right text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)]">Menge</th>
                <th className="w-1/6 px-[var(--space-sm)] py-[var(--space-xs)] text-right text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)]">Einzelpreis</th>
                <th className="w-1/6 px-[var(--space-sm)] py-[var(--space-xs)] text-right text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)]">Betrag</th>
                <th className="w-12 px-[var(--space-sm)] py-[var(--space-xs)]">
                  <span className="sr-only">Entfernen</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {value.items.map((it, idx) => {
                const number = idx + 1;
                const quantityBad = !(it.quantity > 0);
                const priceBad = it.unit_price < 0;
                const descriptionBad = touched.has(idx) && !it.description.trim();
                return (
                  <tr key={idx} className="border-b border-[var(--color-border)] transition-colors hover:bg-[var(--color-surface-bright)]">
                    <td className="px-[var(--space-sm)] py-[var(--space-sm)]">
                      <input
                        type="text"
                        aria-label={`Beschreibung Position ${number}`}
                        aria-invalid={descriptionBad}
                        value={it.description}
                        autoFocus={focusIndex === idx}
                        onChange={(e) => updateItemField(idx, "description", e.target.value)}
                        onBlur={() => setTouched((prev) => new Set(prev).add(idx))}
                        maxLength={500}
                        placeholder="z. B. DJ-Set, 4 bis 7 Uhr"
                        className={`${CELL_INPUT} ${descriptionBad ? "border-b-red-500" : ""}`}
                      />
                    </td>
                    <td className="px-[var(--space-sm)] py-[var(--space-sm)]">
                      <input
                        type="number"
                        inputMode="decimal"
                        aria-label={`Menge Position ${number}`}
                        aria-invalid={quantityBad}
                        min="0.01"
                        step="any"
                        value={it.quantity}
                        onChange={(e) => updateItemField(idx, "quantity", Number(e.target.value))}
                        className={`${CELL_INPUT} text-right font-mono text-sm ${quantityBad ? "border-b-red-500" : ""}`}
                      />
                    </td>
                    <td className="px-[var(--space-sm)] py-[var(--space-sm)]">
                      <div className="flex items-center justify-end">
                        <span className="mr-1 font-mono text-sm text-[var(--color-text-secondary)]">€</span>
                        <input
                          type="number"
                          inputMode="decimal"
                          aria-label={`Einzelpreis Position ${number}`}
                          aria-invalid={priceBad}
                          min="0"
                          step="0.01"
                          value={it.unit_price}
                          onChange={(e) => updateItemField(idx, "unit_price", Number(e.target.value))}
                          className={`${CELL_INPUT} w-24 text-right font-mono text-sm ${priceBad ? "border-b-red-500" : ""}`}
                        />
                      </div>
                    </td>
                    <td className="px-[var(--space-sm)] py-[var(--space-sm)] text-right font-mono text-sm text-[var(--color-text-primary)]">
                      {money(it.quantity * it.unit_price)} €
                    </td>
                    <td className="px-[var(--space-sm)] py-[var(--space-sm)] text-center">
                      <button
                        type="button"
                        onClick={() => removeItem(idx)}
                        aria-label={`Position ${number} entfernen`}
                        title="Position entfernen"
                        className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--radius)] text-[var(--color-text-muted)] transition-colors hover:bg-red-50 hover:text-red-600"
                      >
                        <Trash2 size={18} />
                      </button>
                    </td>
                  </tr>
                );
              })}
              <tr>
                <td colSpan={5} className="px-[var(--space-sm)] py-[var(--space-sm)]">
                  <button
                    type="button"
                    onClick={addItem}
                    className="flex items-center gap-[var(--space-xs)] text-[14px] font-semibold text-[var(--color-brand-text)] transition-colors hover:text-[var(--color-brand-text-hover)]"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]" aria-hidden="true">
                      <path d="M12 5v14M5 12h14" />
                    </svg>
                    Neue Position
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        {removed && (
          <p role="status" className="mt-2 flex items-center gap-3 rounded-[var(--radius)] bg-[var(--color-surface-container-low)] px-3 py-2 text-[13px] text-[var(--color-text-secondary)]">
            Position {removed.index + 1} entfernt.
            <button type="button" onClick={undoRemove} className="font-semibold text-[var(--color-brand-text)] underline">
              Rückgängig
            </button>
          </p>
        )}
      </div>

      {/* Totals */}
      <div className="flex justify-end border-t border-[var(--color-border)] pt-[var(--space-md)]">
        <div className="w-full max-w-sm space-y-[var(--space-sm)]">
          <div className="flex items-center justify-between px-[var(--space-sm)]">
            <span className="text-[14px] text-[var(--color-text-secondary)]">Nettobetrag</span>
            <span className="font-mono text-sm text-[var(--color-text-primary)]">{money(subtotalNet)} €</span>
          </div>
          <div className="flex items-center gap-2 px-[var(--space-sm)]">
            <input
              type="checkbox"
              id="ust-ausweisen"
              checked={value.ust_enabled}
              onChange={(e) =>
                onChange({
                  ...value,
                  ust_enabled: e.target.checked,
                  vat_rate: e.target.checked && value.vat_rate === 0 ? 19 : value.vat_rate,
                })
              }
              className="h-4 w-4 rounded border-[var(--color-border)] accent-[#001a42]"
            />
            <label htmlFor="ust-ausweisen" className="cursor-pointer select-none text-[14px] text-[var(--color-text-primary)]">
              Umsatzsteuer ausweisen
            </label>
          </div>
          {value.ust_enabled ? (
            <div className="flex items-center justify-between px-[var(--space-sm)]">
              <div className="flex items-center gap-2">
                <label htmlFor="ust-satz" className="text-[14px] text-[var(--color-text-secondary)]">
                  USt-Satz
                </label>
                <input
                  id="ust-satz"
                  type="number"
                  inputMode="decimal"
                  step="0.1"
                  min="0"
                  max="100"
                  value={value.vat_rate}
                  onChange={(e) => setField("vat_rate", Number(e.target.value))}
                  className="w-16 rounded border border-[var(--color-border)] bg-[var(--color-surface-bright)] px-1 py-0.5 text-right font-mono text-sm text-[var(--color-text-primary)] outline-none transition-all duration-150 focus:border-[#001a42] focus:ring-1 focus:ring-[#001a42]"
                />
                <span className="font-mono text-sm text-[var(--color-text-secondary)]">%</span>
              </div>
              <span className="font-mono text-sm text-[var(--color-text-primary)]">{money(taxAmount)} €</span>
            </div>
          ) : (
            <p className="px-[var(--space-sm)] text-[12px] text-[var(--color-text-muted)]">
              Auf dieser Rechnung wird keine Umsatzsteuer ausgewiesen.
            </p>
          )}
          <div className="mt-[var(--space-sm)] flex items-center justify-between rounded-[var(--radius-lg)] bg-[var(--color-surface-container-low)] px-[var(--space-sm)] py-[var(--space-xs)]">
            <span className="text-[20px] font-bold text-[var(--color-text-primary)]">Gesamtbetrag</span>
            <span className="font-mono text-[20px] font-bold text-[var(--color-text-primary)]">{money(gross)} €</span>
          </div>
        </div>
      </div>
    </div>
  );
}
