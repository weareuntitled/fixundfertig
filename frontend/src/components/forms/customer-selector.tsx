/**
 * @schema CustomerSelector
 * @purpose Dropdown selector for choosing an existing customer + inline creation
 * @input {number | null} value - Selected customer ID
 * @input {(customerId: number) => void} onChange - Selection callback
 * @input {string} className - Optional additional classes
 * @output Renders select dropdown with customer list + add button + creation modal
 * @tokens Uses: input-*, color-text-primary, color-border, modal-*
 */
import { useState } from "react";
import { Plus, X } from "lucide-react";
import { Select } from "@/components/forms/select";
import { useCustomers, useCreateCustomer, type Customer } from "@/lib/use-customers";

interface CustomerSelectorProps {
  value: number | null;
  onChange: (customerId: number) => void;
  className?: string;
}

export function CustomerSelector({ value, onChange, className = "" }: CustomerSelectorProps) {
  const { data: customers, isLoading } = useCustomers();
  const createCustomer = useCreateCustomer();
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({ vorname: "", nachname: "", email: "" });

  const handleCreate = async () => {
    const result = await createCustomer.mutateAsync(form);
    setModalOpen(false);
    setForm({ vorname: "", nachname: "", email: "" });
    onChange(result.id);
  };

  if (isLoading) {
    return (
      <label className="block">
        <span className="mb-1.5 block text-xs font-semibold text-[var(--color-text-secondary)]">
          Kunde
        </span>
        <div className="h-10 w-full animate-pulse rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface-container-low)]" />
      </label>
    );
  }

  return (
    <>
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <Select
            label="Kunde"
            value={value}
            onChange={(v) => onChange(Number(v))}
            options={(customers ?? []).map((c: Customer) => ({
              value: c.id,
              label: _displayName(c),
            }))}
            className={className}
          />
        </div>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="flex items-center justify-center h-10 w-10 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white hover:bg-[var(--color-surface-container-low)] transition-colors shrink-0"
          title="Neuen Kunden anlegen"
        >
          <Plus size={18} />
        </button>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
          onClick={() => setModalOpen(false)}
        >
          <div
            className="bg-white rounded-[var(--radius-xl)] shadow-xl p-6 w-full max-w-sm border border-[var(--color-border)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-[var(--color-text-primary)]">
                Neuen Kunden anlegen
              </h3>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="rounded-full p-1 text-[var(--color-text-muted)] hover:bg-[var(--color-surface-container-low)]"
              >
                <X size={18} />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-[var(--color-text-secondary)] mb-1">
                  Vorname
                </label>
                <input
                  type="text"
                  value={form.vorname}
                  onChange={(e) => setForm({ ...form, vorname: e.target.value })}
                  className="w-full h-10 px-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] text-sm outline-none focus:ring-2 focus:ring-[var(--color-brand)] focus:border-transparent"
                  placeholder="Max"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[var(--color-text-secondary)] mb-1">
                  Nachname
                </label>
                <input
                  type="text"
                  value={form.nachname}
                  onChange={(e) => setForm({ ...form, nachname: e.target.value })}
                  className="w-full h-10 px-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] text-sm outline-none focus:ring-2 focus:ring-[var(--color-brand)] focus:border-transparent"
                  placeholder="Mustermann"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[var(--color-text-secondary)] mb-1">
                  E-Mail
                </label>
                <input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full h-10 px-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] text-sm outline-none focus:ring-2 focus:ring-[var(--color-brand)] focus:border-transparent"
                  placeholder="max@example.com"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="px-4 py-2 text-sm font-semibold rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white text-[var(--color-text-primary)] hover:bg-[var(--color-surface-container-low)] transition-colors"
              >
                Abbrechen
              </button>
              <button
                type="button"
                onClick={handleCreate}
                disabled={!form.vorname || !form.nachname || createCustomer.isPending}
                className="px-4 py-2 text-sm font-semibold rounded-[var(--radius-lg)] bg-[var(--color-brand)] text-white hover:bg-[var(--color-brand-hover)] disabled:opacity-50 transition-colors"
              >
                {createCustomer.isPending ? "Wird angelegt..." : "Anlegen"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function _displayName(c: Customer): string {
  if (c.name) return c.name;
  const combined = [c.vorname, c.nachname].filter(Boolean).join(" ");
  return combined || `Kunde #${c.id}`;
}
