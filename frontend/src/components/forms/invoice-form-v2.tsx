/**
 * @schema InvoiceFormV2
 * @purpose Invoice creation form matching Lumina Ledger HTML exactly
 * @input {InvoiceDraft} value - Current invoice draft state
 * @input {(next: InvoiceDraft) => void} onChange - State update callback
 * @output Renders single white card with 12-col grid header, full-width line items table, totals, notes
 * @tokens Uses: color-surface-card, color-border, color-text-*, input-*, table-*
 */
import { useState } from "react";
import { Trash2 } from "lucide-react";
import { CustomerSelector } from "./customer-selector";
import { LineItemDialog } from "./line-item-dialog";
import type { InvoiceDraft, InvoiceItem } from "@/lib/schemas/invoice";

interface InvoiceFormV2Props {
  value: InvoiceDraft;
  onChange: (next: InvoiceDraft) => void;
}

export function InvoiceFormV2({ value, onChange }: InvoiceFormV2Props) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const setField = <K extends keyof InvoiceDraft>(key: K, v: InvoiceDraft[K]) =>
    onChange({ ...value, [key]: v });

  const addItem = () => {
    setEditingIndex(null);
    setDialogOpen(true);
  };

  const saveItem = (item: InvoiceItem) => {
    if (editingIndex === null) {
      setField("items", [...value.items, item]);
    } else {
      const next = [...value.items];
      next[editingIndex] = item;
      setField("items", next);
    }
    setDialogOpen(false);
  };

  const removeItem = (idx: number) => {
    setField(
      "items",
      value.items.filter((_, i) => i !== idx),
    );
  };

  const updateItemField = (idx: number, field: keyof InvoiceItem, val: string | number) => {
    const next = [...value.items];
    next[idx] = { ...next[idx], [field]: val };
    setField("items", next);
  };

  const subtotalNet = value.items.reduce((sum, it) => sum + it.quantity * it.unit_price, 0);
  const taxAmount = value.ust_enabled ? subtotalNet * (value.vat_rate / 100) : 0;
  const gross = subtotalNet + taxAmount;

  return (
    <div className="space-y-0">
      {/* Header Section: Client & Dates — 12-col grid */}
      <div className="grid grid-cols-12 gap-[var(--space-gutter)] mb-[var(--space-xl)] border-b border-[var(--color-border)] pb-[var(--space-xl)]">
        {/* Left: Client Details */}
        <div className="col-span-12 md:col-span-6 space-y-[var(--space-md)]">
          <div>
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)] mb-[var(--space-xs)]">
              Kundendetails
            </label>
            <CustomerSelector
              value={value.customer_id}
              onChange={(id) => setField("customer_id", id)}
            />
          </div>

          <div>
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)] mb-[var(--space-xs)]">
              Betreff
            </label>
            <input
              type="text"
              value={value.subject}
              onChange={(e) => setField("subject", e.target.value)}
              placeholder="Rechnungsbetreff (optional)"
              className="w-full bg-white border border-[var(--color-border)] rounded-[var(--radius-lg)] px-[var(--space-sm)] py-2 text-[14px] text-[var(--color-text-primary)] focus:border-[var(--color-black)] focus:ring-1 focus:ring-[var(--color-black)] transition-all duration-150 outline-none"
            />
          </div>
        </div>

        {/* Right: Invoice Number + Dates */}
        <div className="col-span-12 md:col-span-6 grid grid-cols-2 gap-[var(--space-sm)]">
          <div className="col-span-2">
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)] mb-[var(--space-xs)]">
              Rechnungsnummer
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)] font-mono text-sm">
                INV-
              </span>
              <input
                type="text"
                readOnly
                value={"Wird beim Finalisieren vergeben"}
                className="w-full bg-white border border-[var(--color-border)] rounded-[var(--radius-lg)] pl-12 pr-4 py-2 font-mono text-sm text-[var(--color-text-primary)] focus:border-[var(--color-black)] focus:ring-1 focus:ring-[var(--color-black)] transition-all duration-150 outline-none"
              />
            </div>
          </div>
          <div>
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)] mb-[var(--space-xs)]">
              Rechnungsdatum
            </label>
            <input
              type="date"
              value={value.date}
              onChange={(e) => setField("date", e.target.value)}
              className="w-full bg-white border border-[var(--color-border)] rounded-[var(--radius-lg)] px-[var(--space-sm)] py-2 text-[14px] text-[var(--color-text-primary)] focus:border-[var(--color-black)] focus:ring-1 focus:ring-[var(--color-black)] transition-all duration-150 outline-none"
            />
          </div>
          <div>
            <label className="block text-[14px] font-bold text-[var(--color-text-primary)] mb-[var(--space-xs)]">
              Leistungszeitraum
            </label>
            <input
              type="date"
              value={value.delivery_date}
              onChange={(e) => setField("delivery_date", e.target.value)}
              className="w-full bg-white border border-[var(--color-border)] rounded-[var(--radius-lg)] px-[var(--space-sm)] py-2 text-[14px] text-[var(--color-text-primary)] focus:border-[var(--color-black)] focus:ring-1 focus:ring-[var(--color-black)] transition-all duration-150 outline-none"
            />
          </div>
        </div>
      </div>

      {/* Line Items Section */}
      <div className="mb-[var(--space-xl)]">
        <h3 className="text-[20px] font-semibold text-[var(--color-text-primary)] mb-[var(--space-md)]">
          Positionen
        </h3>
        <div className="w-full overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#F1F5F9] border-y border-[var(--color-border)]">
                <th className="py-[var(--space-xs)] px-[var(--space-sm)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)] w-1/2">
                  Beschreibung
                </th>
                <th className="py-[var(--space-xs)] px-[var(--space-sm)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)] text-right w-1/6">
                  Menge
                </th>
                <th className="py-[var(--space-xs)] px-[var(--space-sm)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)] text-right w-1/6">
                  Preis
                </th>
                <th className="py-[var(--space-xs)] px-[var(--space-sm)] text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)] text-right w-1/6">
                  Betrag
                </th>
                <th className="py-[var(--space-xs)] px-[var(--space-sm)] w-10" />
              </tr>
            </thead>
            <tbody>
              {value.items.map((it, idx) => (
                <tr
                  key={idx}
                  className="border-b border-[var(--color-border)] group hover:bg-[var(--color-surface-bright)] transition-colors"
                >
                  <td className="py-[var(--space-sm)] px-[var(--space-sm)]">
                    <input
                      type="text"
                      value={it.description}
                      onChange={(e) => updateItemField(idx, "description", e.target.value)}
                      placeholder="Beschreibung"
                      className="w-full bg-transparent border-0 border-b border-transparent focus:border-[var(--color-black)] focus:ring-0 px-0 py-1 text-[14px] text-[var(--color-text-primary)] outline-none transition-colors placeholder:text-[var(--color-text-secondary)]"
                    />
                  </td>
                  <td className="py-[var(--space-sm)] px-[var(--space-sm)]">
                    <input
                      type="number"
                      value={it.quantity}
                      onChange={(e) => updateItemField(idx, "quantity", Number(e.target.value))}
                      className="w-full text-right bg-transparent border-0 border-b border-transparent focus:border-[var(--color-black)] focus:ring-0 px-0 py-1 font-mono text-sm text-[var(--color-text-primary)] outline-none transition-colors"
                    />
                  </td>
                  <td className="py-[var(--space-sm)] px-[var(--space-sm)]">
                    <div className="relative flex items-center justify-end">
                      <span className="text-[var(--color-text-secondary)] font-mono text-sm mr-1">€</span>
                      <input
                        type="number"
                        value={it.unit_price}
                        onChange={(e) => updateItemField(idx, "unit_price", Number(e.target.value))}
                        className="w-24 text-right bg-transparent border-0 border-b border-transparent focus:border-[var(--color-black)] focus:ring-0 px-0 py-1 font-mono text-sm text-[var(--color-text-primary)] outline-none transition-colors"
                      />
                    </div>
                  </td>
                  <td className="py-[var(--space-sm)] px-[var(--space-sm)] text-right font-mono text-sm text-[var(--color-text-primary)]">
                    {(it.quantity * it.unit_price).toLocaleString("de-DE", {
                      minimumFractionDigits: 2,
                    })}{" "}
                    €
                  </td>
                  <td className="py-[var(--space-sm)] px-[var(--space-sm)] text-center">
                    <button
                      type="button"
                      onClick={() => removeItem(idx)}
                      className="text-[var(--color-border)] hover:text-[var(--color-danger)] transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                    >
                      <Trash2 size={20} />
                    </button>
                  </td>
                </tr>
              ))}
              {/* Add Row */}
              <tr>
                <td colSpan={5} className="py-[var(--space-sm)] px-[var(--space-sm)]">
                  <button
                    type="button"
                    onClick={addItem}
                    className="flex items-center gap-[var(--space-xs)] text-[var(--color-brand-text)] text-[14px] font-semibold hover:text-[var(--color-brand-text-hover)] transition-colors"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-[18px] h-[18px]">
                      <path d="M12 5v14M5 12h14" />
                    </svg>
                    Neue Position
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Bottom Calculation Area */}
      <div className="flex justify-end pt-[var(--space-md)] border-t border-[var(--color-border)]">
        <div className="w-full max-w-sm space-y-[var(--space-sm)]">
          <div className="flex justify-between items-center px-[var(--space-sm)]">
            <span className="text-[14px] text-[var(--color-text-secondary)]">Nettobetrag</span>
            <span className="font-mono text-sm text-[var(--color-text-primary)]">
              {subtotalNet.toLocaleString("de-DE", { minimumFractionDigits: 2 })} €
            </span>
          </div>
          <div className="flex justify-between items-center px-[var(--space-sm)] group">
            <div className="flex items-center gap-2">
              <span className="text-[14px] text-[var(--color-text-secondary)]">USt</span>
              <div className="flex items-center">
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  value={value.vat_rate}
                  onChange={(e) => setField("vat_rate", Number(e.target.value))}
                  disabled={!value.ust_enabled}
                  className="w-14 text-right bg-[var(--color-surface-bright)] border border-[var(--color-border)] rounded px-1 py-0.5 font-mono text-sm text-[var(--color-text-primary)] focus:border-[var(--color-black)] focus:ring-1 focus:ring-[var(--color-black)] transition-all duration-150 outline-none disabled:opacity-30"
                />
                <span className="font-mono text-sm text-[var(--color-text-secondary)] ml-1">%</span>
              </div>
            </div>
            <span className="font-mono text-sm text-[var(--color-text-primary)]">
              {value.ust_enabled
                ? taxAmount.toLocaleString("de-DE", { minimumFractionDigits: 2 }) + " €"
                : "0,00 €"}
            </span>
          </div>
          <div className="flex items-center gap-2 px-[var(--space-sm)]">
            <input
              type="checkbox"
              id="kleinunternehmer"
              checked={!value.ust_enabled}
              onChange={(e) => {
                setField("ust_enabled", !e.target.checked);
                if (e.target.checked) setField("vat_rate", 0);
              }}
              className="h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-black)] focus:ring-[var(--color-black)]"
            />
            <label htmlFor="kleinunternehmer" className="text-[12px] text-[var(--color-text-muted)] cursor-pointer select-none">
              Kleinunternehmer (§19 UStG) — keine Umsatzsteuer
            </label>
          </div>
          <div className="flex justify-between items-center px-[var(--space-sm)] py-[var(--space-xs)] bg-[var(--color-surface-container-low)] rounded-[var(--radius-lg)] mt-[var(--space-sm)]">
            <span className="text-[20px] font-bold text-[var(--color-text-primary)]">Gesamtbetrag</span>
            <span className="font-mono text-[20px] font-bold text-[var(--color-text-primary)]">
              {gross.toLocaleString("de-DE", { minimumFractionDigits: 2 })} €
            </span>
          </div>
        </div>
      </div>

      {/* Notes */}
      <div className="mt-[var(--space-xl)] pt-[var(--space-md)] border-t border-[var(--color-border)] flex flex-col">
        <label className="text-[14px] font-bold text-[var(--color-text-primary)] mb-[var(--space-xs)]">
          Notizen / Zahlungsbedingungen
        </label>
        <textarea
          value={value.notes}
          onChange={(e) => setField("notes", e.target.value)}
          placeholder="Zahlung innerhalb von 30 Tagen. Vielen Dank für Ihren Auftrag."
          rows={3}
          className="w-full bg-white border border-[var(--color-border)] rounded-[var(--radius-lg)] p-[var(--space-sm)] text-[14px] text-[var(--color-text-primary)] focus:border-[var(--color-black)] focus:ring-1 focus:ring-[var(--color-black)] transition-all duration-150 outline-none resize-y"
        />
      </div>

      {/* Line Item Dialog */}
      <LineItemDialog
        open={dialogOpen}
        initial={editingIndex !== null ? value.items[editingIndex] : undefined}
        onSave={saveItem}
        onCancel={() => setDialogOpen(false)}
      />
    </div>
  );
}
