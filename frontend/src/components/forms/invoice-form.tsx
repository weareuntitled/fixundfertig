import { useState } from "react";
import { Trash2, Pencil, Plus } from "lucide-react";
import { CustomerSelector } from "./customer-selector";
import { LineItemDialog } from "./line-item-dialog";
import type { InvoiceDraft, InvoiceItem } from "@/lib/schemas/invoice";

interface InvoiceFormProps {
  value: InvoiceDraft;
  onChange: (next: InvoiceDraft) => void;
}

export function InvoiceForm({ value, onChange }: InvoiceFormProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const setField = <K extends keyof InvoiceDraft>(key: K, v: InvoiceDraft[K]) =>
    onChange({ ...value, [key]: v });

  const addItem = () => {
    setEditingIndex(null);
    setDialogOpen(true);
  };

  const editItem = (idx: number) => {
    setEditingIndex(idx);
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

  const subtotalNet = value.items.reduce((sum, it) => sum + it.quantity * it.unit_price, 0);
  const taxAmount = value.ust_enabled ? subtotalNet * (value.vat_rate / 100) : 0;
  const gross = subtotalNet + taxAmount;

  return (
    <div className="space-y-4">
      <CustomerSelector
        value={value.customer_id}
        onChange={(id) => setField("customer_id", id)}
      />

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-xs font-medium text-slate-700">
          Rechnungsdatum
          <input
            type="date"
            value={value.date}
            onChange={(e) => setField("date", e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-[var(--brand-primary)]"
          />
        </label>
        <label className="block text-xs font-medium text-slate-700">
          Leistungszeitraum
          <input
            type="date"
            value={value.delivery_date}
            onChange={(e) => setField("delivery_date", e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-[var(--brand-primary)]"
          />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-xs font-medium text-slate-700">
          USt (%)
          <input
            type="number"
            step="0.1"
            min="0"
            max="100"
            disabled={!value.ust_enabled}
            value={value.vat_rate}
            onChange={(e) => setField("vat_rate", Number(e.target.value))}
            className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-[var(--brand-primary)] disabled:bg-slate-50"
          />
        </label>
        <label className="flex items-end gap-2 pb-2 text-xs font-medium text-slate-700">
          <input
            type="checkbox"
            checked={value.ust_enabled}
            onChange={(e) => setField("ust_enabled", e.target.checked)}
          />
          USt ausweisen
        </label>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Positionen
          </h3>
          <button
            type="button"
            onClick={addItem}
            className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200"
          >
            <Plus size={12} /> Position
          </button>
        </div>
        <ul className="divide-y divide-slate-200 rounded-md border border-slate-200 bg-white">
          {value.items.length === 0 && (
            <li className="px-3 py-4 text-center text-xs text-slate-500">
              Noch keine Positionen — Vorschau erscheint, sobald mindestens eine vorhanden.
            </li>
          )}
          {value.items.map((it, idx) => (
            <li key={idx} className="flex items-center gap-3 px-3 py-2 text-sm">
              <div className="min-w-0 flex-1">
                <div className="truncate text-slate-900">{it.description}</div>
                <div className="text-xs text-slate-500">
                  {it.quantity} × {it.unit_price.toFixed(2)} €
                </div>
              </div>
              <div className="font-numeric tabular-nums text-slate-900">
                {(it.quantity * it.unit_price).toFixed(2)} €
              </div>
              <button
                type="button"
                onClick={() => editItem(idx)}
                aria-label="Position bearbeiten"
                className="rounded p-1 text-slate-500 hover:bg-slate-100"
              >
                <Pencil size={14} />
              </button>
              <button
                type="button"
                onClick={() => removeItem(idx)}
                aria-label="Position löschen"
                className="rounded p-1 text-rose-500 hover:bg-rose-50"
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
        <div className="flex justify-between text-slate-600">
          <span>Netto</span>
          <span className="font-numeric tabular-nums">{subtotalNet.toFixed(2)} €</span>
        </div>
        {value.ust_enabled && (
          <div className="flex justify-between text-slate-600">
            <span>USt ({value.vat_rate}%)</span>
            <span className="font-numeric tabular-nums">{taxAmount.toFixed(2)} €</span>
          </div>
        )}
        <div className="mt-1 flex justify-between border-t border-slate-200 pt-1 font-semibold text-slate-900">
          <span>Brutto</span>
          <span className="font-numeric tabular-nums">{gross.toFixed(2)} €</span>
        </div>
      </div>

      <LineItemDialog
        open={dialogOpen}
        initial={editingIndex !== null ? value.items[editingIndex] : undefined}
        onSave={saveItem}
        onCancel={() => setDialogOpen(false)}
      />
    </div>
  );
}
