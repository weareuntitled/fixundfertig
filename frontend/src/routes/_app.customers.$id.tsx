import { useState } from "react";
import { createFileRoute, useParams, useNavigate } from "@tanstack/react-router";
import { Trash2 } from "lucide-react";
import { useCustomer, useCreateCustomer, useUpdateCustomer, useDeleteCustomer } from "@/lib/use-customers";

export const Route = createFileRoute("/_app/customers/$id")({
  component: CustomerDetailPage,
});

interface FormState {
  name: string;
  vorname: string;
  nachname: string;
  email: string;
  strasse: string;
  plz: string;
  ort: string;
  country: string;
  recipient_name: string;
  recipient_street: string;
  recipient_postal_code: string;
  recipient_city: string;
  vat_id: string;
  archived: boolean;
}

const emptyForm: FormState = {
  name: "",
  vorname: "",
  nachname: "",
  email: "",
  strasse: "",
  plz: "",
  ort: "",
  country: "DE",
  recipient_name: "",
  recipient_street: "",
  recipient_postal_code: "",
  recipient_city: "",
  vat_id: "",
  archived: false,
};

function CustomerDetailPage() {
  const { id } = useParams({ from: "/_app/customers/$id" });
  const isNew = id === "new";
  const customerId = isNew ? 0 : Number(id);
  const navigate = useNavigate();

  const { data: customer, isLoading } = useCustomer(customerId);
  const create = useCreateCustomer();
  const update = useUpdateCustomer();
  const del = useDeleteCustomer();

  const [form, setForm] = useState<FormState>(emptyForm);

  // Populate form when customer loads (only for edit mode)
  if (!isNew && customer && form.name === "" && customer.name === "" && customer.email === "") {
    setForm({
      name: customer.name,
      vorname: customer.vorname,
      nachname: customer.nachname,
      email: customer.email,
      strasse: customer.strasse,
      plz: customer.plz,
      ort: customer.ort,
      country: customer.country || "DE",
      recipient_name: customer.recipient_name,
      recipient_street: customer.recipient_street,
      recipient_postal_code: customer.recipient_postal_code,
      recipient_city: customer.recipient_city,
      vat_id: customer.vat_id,
      archived: customer.archived,
    });
  }

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((prev) => ({ ...prev, [k]: v }));

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: Record<string, unknown> = { ...form };
    if (isNew) {
      create.mutate(payload, { onSuccess: () => void navigate({ to: "/customers" }) });
    } else {
      update.mutate({ id: customerId, data: payload }, {
        onSuccess: () => void navigate({ to: "/customers" }),
      });
    }
  };

  const onDelete = () => {
    if (!confirm("Kunde wirklich löschen? (Nur möglich, wenn keine Rechnungen existieren.)")) return;
    del.mutate(customerId, { onSuccess: () => void navigate({ to: "/customers" }) });
  };

  if (!isNew && isLoading) {
    return <p className="text-sm text-[var(--color-text-tertiary)]">Lade Kunde…</p>;
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">
          {isNew ? "Neuer Kunde" : `Kunde #${customerId}`}
        </h1>
        <div className="flex gap-2">
          {!isNew && (
            <button
              type="button"
              onClick={onDelete}
              className="inline-flex items-center gap-1 rounded-md border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50"
            >
              <Trash2 size={12} /> Löschen
            </button>
          )}
          <button
            type="submit"
            disabled={create.isPending || update.isPending}
            className="rounded-md bg-[var(--color-text-heading)] px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {create.isPending || update.isPending ? "Speichere…" : "Speichern"}
          </button>
        </div>
      </header>

      <section className="rounded-xl border border-[var(--color-border)] bg-white p-4">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Firma / Name</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Input label="Firma" value={form.name} onChange={(v) => set("name", v)} />
          <Input label="Vorname" value={form.vorname} onChange={(v) => set("vorname", v)} />
          <Input label="Nachname" value={form.nachname} onChange={(v) => set("nachname", v)} />
          <Input label="E-Mail" type="email" value={form.email} onChange={(v) => set("email", v)} className="sm:col-span-2" />
          <Input label="USt-ID" value={form.vat_id} onChange={(v) => set("vat_id", v)} />
        </div>
      </section>

      <section className="rounded-xl border border-[var(--color-border)] bg-white p-4">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Adresse</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-6">
          <Input label="Straße" value={form.strasse} onChange={(v) => set("strasse", v)} className="sm:col-span-4" />
          <Input label="PLZ" value={form.plz} onChange={(v) => set("plz", v)} className="sm:col-span-2" />
          <Input label="Ort" value={form.ort} onChange={(v) => set("ort", v)} className="sm:col-span-4" />
          <Input label="Land" value={form.country} onChange={(v) => set("country", v)} className="sm:col-span-2" maxLength={2} />
        </div>
      </section>

      <section className="rounded-xl border border-[var(--color-border)] bg-white p-4">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Abweichende Rechnungsadresse</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-6">
          <Input label="Empfänger" value={form.recipient_name} onChange={(v) => set("recipient_name", v)} className="sm:col-span-2" />
          <Input label="Straße" value={form.recipient_street} onChange={(v) => set("recipient_street", v)} className="sm:col-span-2" />
          <Input label="PLZ" value={form.recipient_postal_code} onChange={(v) => set("recipient_postal_code", v)} />
          <Input label="Ort" value={form.recipient_city} onChange={(v) => set("recipient_city", v)} className="sm:col-span-2" />
        </div>
      </section>

      <section className="rounded-xl border border-[var(--color-border)] bg-white p-4">
        <label className="flex items-center gap-2 text-xs text-[var(--color-text-primary)]">
          <input
            type="checkbox"
            checked={form.archived}
            onChange={(e) => set("archived", e.target.checked)}
          />
          Kunde archivieren
        </label>
      </section>

      {(create.isError || update.isError) && (
        <p className="text-xs text-rose-600" role="alert">
          Speichern fehlgeschlagen.
        </p>
      )}
    </form>
  );
}

interface InputProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  className?: string;
  maxLength?: number;
}

function Input({ label, value, onChange, type = "text", className = "", maxLength }: InputProps) {
  return (
    <label className={`block text-xs font-medium text-[var(--color-text-primary)] ${className}`}>
      {label}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        maxLength={maxLength}
        className="mt-1 block w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-text-heading)]"
      />
    </label>
  );
}
