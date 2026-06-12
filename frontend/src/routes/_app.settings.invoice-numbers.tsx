import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useCompany, useUpdateCompany } from "@/lib/use-company";
import { ArrowLeft, Save } from "lucide-react";

export const Route = createFileRoute("/_app/settings/invoice-numbers")({
  component: InvoiceNumbersSettingsPage,
});

function InvoiceNumbersSettingsPage() {
  const { data: company, isLoading, isError } = useCompany();
  const updateCompany = useUpdateCompany();
  const [form, setForm] = useState({
    next_invoice_nr: 10000,
    invoice_number_template: "{seq}",
    invoice_filename_template: "rechnung_{nr}",
  });

  useEffect(() => {
    if (company) {
      setForm({
        next_invoice_nr: company.next_invoice_nr,
        invoice_number_template: company.invoice_number_template,
        invoice_filename_template: company.invoice_filename_template,
      });
    }
  }, [company]);

  if (isLoading) return <p className="text-sm text-[var(--color-text-tertiary)]">Lade Einstellungen…</p>;
  if (isError || !company) return <p className="text-sm text-rose-600">Einstellungen konnten nicht geladen werden.</p>;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    updateCompany.mutate(form);
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <Link
          to="/settings"
          className="inline-flex items-center gap-1 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-heading)]"
        >
          <ArrowLeft className="h-4 w-4" /> Zurück
        </Link>
        <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Rechnungsnummern</h1>
      </header>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-[var(--color-border)] bg-white p-4">
        <FormField label="Nächste Rechnungsnummer" required>
          <input
            type="number"
            required
            value={form.next_invoice_nr}
            onChange={(e) => setForm({ ...form, next_invoice_nr: Number(e.target.value) })}
            className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
          />
        </FormField>
        <FormField label="Nummern-Template" required>
          <input
            required
            value={form.invoice_number_template}
            onChange={(e) => setForm({ ...form, invoice_number_template: e.target.value })}
            className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            placeholder="{seq}"
          />
          <p className="mt-1 text-xs text-[var(--color-text-tertiary)]">
            Platzhalter: {'{seq}'} = fortlaufende Nummer, {'{year}'} = Jahr
          </p>
        </FormField>
        <FormField label="Dateiname-Template" required>
          <input
            required
            value={form.invoice_filename_template}
            onChange={(e) => setForm({ ...form, invoice_filename_template: e.target.value })}
            className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            placeholder="rechnung_{nr}"
          />
          <p className="mt-1 text-xs text-[var(--color-text-tertiary)]">
            Platzhalter: {'{nr}'} = Rechnungsnummer
          </p>
        </FormField>

        <div className="flex items-center justify-between border-t border-[var(--color-border-subtle)] pt-3">
          {updateCompany.isSuccess && (
            <p className="text-xs text-emerald-600">Gespeichert.</p>
          )}
          {updateCompany.isError && (
            <p className="text-xs text-rose-600">Fehler beim Speichern.</p>
          )}
          <button
            type="submit"
            disabled={updateCompany.isPending}
            className="ml-auto inline-flex items-center gap-1 rounded-md bg-[var(--color-text-heading)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            <Save className="h-4 w-4" />
            {updateCompany.isPending ? "Speichere…" : "Speichern"}
          </button>
        </div>
      </form>
    </div>
  );
}

function FormField({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--color-text-primary)]">
        {label} {required && <span className="text-rose-600">*</span>}
      </span>
      {children}
    </label>
  );
}
