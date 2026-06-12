import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useCompany, useUpdateCompany } from "@/lib/use-company";
import { ArrowLeft, Save } from "lucide-react";

export const Route = createFileRoute("/_app/settings/company")({
  component: CompanySettingsPage,
});

function CompanySettingsPage() {
  const { data: company, isLoading, isError } = useCompany();
  const updateCompany = useUpdateCompany();
  const [form, setForm] = useState({
    name: "",
    first_name: "",
    last_name: "",
    business_type: "",
    street: "",
    postal_code: "",
    city: "",
    country: "Deutschland",
    email: "",
    phone: "",
  });

  useEffect(() => {
    if (company) {
      setForm({
        name: company.name,
        first_name: company.first_name,
        last_name: company.last_name,
        business_type: company.business_type,
        street: company.street,
        postal_code: company.postal_code,
        city: company.city,
        country: company.country,
        email: company.email,
        phone: company.phone,
      });
    }
  }, [company]);

  if (isLoading) return <p className="text-sm text-[var(--color-text-tertiary)]">Lade Firmendaten…</p>;
  if (isError || !company) return <p className="text-sm text-rose-600">Firmendaten konnten nicht geladen werden.</p>;

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
        <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Firma</h1>
      </header>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-[var(--color-border)] bg-white p-4" data-testid="company-form">
        <FormField label="Firmenname" required>
          <input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            data-testid="company-name"
          />
        </FormField>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FormField label="Vorname (Inhaber)">
            <input
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            />
          </FormField>
          <FormField label="Nachname (Inhaber)">
            <input
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            />
          </FormField>
        </div>
        <FormField label="Rechtsform / Branche">
          <input
            value={form.business_type}
            onChange={(e) => setForm({ ...form, business_type: e.target.value })}
            className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
          />
        </FormField>
        <FormField label="Straße + Nr.">
          <input
            value={form.street}
            onChange={(e) => setForm({ ...form, street: e.target.value })}
            className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
          />
        </FormField>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <FormField label="PLZ">
            <input
              value={form.postal_code}
              onChange={(e) => setForm({ ...form, postal_code: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            />
          </FormField>
          <FormField label="Stadt">
            <input
              value={form.city}
              onChange={(e) => setForm({ ...form, city: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            />
          </FormField>
          <FormField label="Land">
            <input
              value={form.country}
              onChange={(e) => setForm({ ...form, country: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            />
          </FormField>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FormField label="E-Mail">
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            />
          </FormField>
          <FormField label="Telefon">
            <input
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            />
          </FormField>
        </div>

        <div className="flex items-center justify-between border-t border-[var(--color-border-subtle)] pt-3">
          {updateCompany.isSuccess && (
            <p className="text-xs text-emerald-600" data-testid="company-saved">Gespeichert.</p>
          )}
          {updateCompany.isError && (
            <p className="text-xs text-rose-600">Fehler beim Speichern.</p>
          )}
          <button
            type="submit"
            disabled={updateCompany.isPending || !form.name}
            className="ml-auto inline-flex items-center gap-1 rounded-md bg-[var(--color-text-heading)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            data-testid="company-save"
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
