import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useCompany, useUpdateCompany } from "@/lib/use-company";
import { ArrowLeft, Save } from "lucide-react";

export const Route = createFileRoute("/_app/settings/tax-banking")({
  component: TaxBankingPage,
});

function TaxBankingPage() {
  const { data: company, isLoading, isError } = useCompany();
  const updateCompany = useUpdateCompany();
  const [form, setForm] = useState({
    tax_id: "",
    vat_id: "",
    iban: "",
    bic: "",
    bank_name: "",
  });

  useEffect(() => {
    if (company) {
      setForm({
        tax_id: company.tax_id,
        vat_id: company.vat_id,
        iban: company.iban,
        bic: company.bic,
        bank_name: company.bank_name,
      });
    }
  }, [company]);

  if (isLoading) return <p className="text-sm text-[var(--color-text-tertiary)]">Lade Daten…</p>;
  if (isError || !company) return <p className="text-sm text-rose-600">Daten konnten nicht geladen werden.</p>;

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
          data-testid="back-to-hub"
        >
          <ArrowLeft className="h-4 w-4" /> Zurück
        </Link>
        <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Steuern & Bank</h1>
      </header>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-[var(--color-border)] bg-white p-4" data-testid="tax-banking-form">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FormField label="Steuernummer">
            <input
              value={form.tax_id}
              onChange={(e) => setForm({ ...form, tax_id: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
              data-testid="tax-id"
            />
          </FormField>
          <FormField label="USt-ID">
            <input
              value={form.vat_id}
              onChange={(e) => setForm({ ...form, vat_id: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
              data-testid="vat-id"
            />
          </FormField>
        </div>

        <FormField label="IBAN">
          <input
            value={form.iban}
            onChange={(e) => setForm({ ...form, iban: e.target.value })}
            className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm font-mono"
            data-testid="iban"
          />
        </FormField>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FormField label="BIC">
            <input
              value={form.bic}
              onChange={(e) => setForm({ ...form, bic: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm font-mono"
            />
          </FormField>
          <FormField label="Bankname">
            <input
              value={form.bank_name}
              onChange={(e) => setForm({ ...form, bank_name: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            />
          </FormField>
        </div>

        <div className="flex items-center justify-between border-t border-[var(--color-border-subtle)] pt-3">
          {updateCompany.isSuccess && (
            <p className="text-xs text-emerald-600" data-testid="tax-banking-saved">Gespeichert.</p>
          )}
          {updateCompany.isError && (
            <p className="text-xs text-rose-600">Fehler beim Speichern.</p>
          )}
          <button
            type="submit"
            disabled={updateCompany.isPending}
            className="ml-auto inline-flex items-center gap-1 rounded-md bg-[var(--color-text-heading)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            data-testid="tax-banking-save"
          >
            <Save className="h-4 w-4" />
            {updateCompany.isPending ? "Speichere…" : "Speichern"}
          </button>
        </div>
      </form>
    </div>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--color-text-primary)]">{label}</span>
      {children}
    </label>
  );
}
