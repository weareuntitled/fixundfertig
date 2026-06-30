import { useRef, useState, useMemo } from "react";
import { Link, createFileRoute, useParams, useNavigate } from "@tanstack/react-router";
import { Trash2, Mail, MapPin, FileText, Pencil } from "lucide-react";
import { useCustomer, useCreateCustomer, useUpdateCustomer, useDeleteCustomer } from "@/lib/use-customers";
import { useInvoices } from "@/lib/use-invoices";
import { StatusBadge } from "@/components/ui/status-badge";
import { useQueryClient } from "@tanstack/react-query";

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

function displayName(c: { name: string; vorname: string; nachname: string }): string {
  if (c.name) return c.name;
  const combined = [c.vorname, c.nachname].filter(Boolean).join(" ");
  return combined || "(unbenannt)";
}

const eur = (n: number) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

function CustomerDetailPage() {
  const { id } = useParams({ from: "/_app/customers/$id" });
  const isNew = id === "new";
  const customerId = isNew ? 0 : Number(id);
  const navigate = useNavigate();

  const { data: customer, isLoading } = useCustomer(customerId);
  const { data: invoices, isLoading: invoicesLoading } = useInvoices();
  const create = useCreateCustomer();
  const update = useUpdateCustomer();
  const del = useDeleteCustomer();
  const qc = useQueryClient();

  const [form, setForm] = useState<FormState>(emptyForm);
  const [editing, setEditing] = useState(isNew);
  const initialized = useRef(false);

  // Populate form when customer loads (only for edit mode)
  // ponytail: use ref guard instead of fragile empty-field check
  if (!isNew && customer && !initialized.current) {
    initialized.current = true;
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

  const customerInvoices = useMemo(() => {
    if (!invoices) return [];
    return invoices.filter((inv) => inv.customer_id === customerId).sort((a, b) => (b.id || 0) - (a.id || 0));
  }, [invoices, customerId]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((prev) => ({ ...prev, [k]: v }));

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: Record<string, unknown> = { ...form };
    if (isNew) {
      create.mutate(payload, { onSuccess: () => void navigate({ to: "/customers" }) });
    } else {
      update.mutate({ id: customerId, data: payload }, {
        onSuccess: () => {
          qc.invalidateQueries({ queryKey: ["customers", customerId] });
          setEditing(false);
        },
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
    <div className="animate-fade-in space-y-5">
      {/* Header */}
      <header className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">
          {isNew ? "Neuer Kunde" : displayName(customer || emptyForm)}
        </h1>
        <div className="flex gap-2">
          {!isNew && (
            <>
              <button
                type="button"
                onClick={() => {
                  if (editing) {
                    setForm(emptyForm);
                    initialized.current = false;
                  }
                  setEditing((v) => !v);
                }}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-[var(--color-text-primary)] hover:bg-[var(--color-gray-50)]"
              >
                <Pencil size={12} /> {editing ? "Abbrechen" : "Bearbeiten"}
              </button>
              <button
                type="button"
                onClick={onDelete}
                className="inline-flex items-center gap-1 rounded-md border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50"
              >
                <Trash2 size={12} /> Löschen
              </button>
            </>
          )}
        </div>
      </header>

      {/* Detail card */}
      {!isNew && customer && !editing && (
        <section className="rounded-xl border border-[var(--color-border)] bg-white p-5">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[var(--color-blue-50)] text-base font-semibold text-[var(--color-text-heading)]">
              {displayName(customer).charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-base font-semibold text-[var(--color-text-heading)]">
                {displayName(customer)}
              </h2>
              {customer.email && (
                <p className="mt-1 flex items-center gap-1 text-sm text-[var(--color-text-tertiary)]">
                  <Mail size={12} /> {customer.email}
                </p>
              )}
              {(customer.strasse || customer.plz || customer.ort) && (
                <p className="mt-1 flex items-start gap-1 text-sm text-[var(--color-text-tertiary)]">
                  <MapPin size={12} className="mt-0.5 shrink-0" />
                  <span>
                    {customer.strasse && <>{customer.strasse}<br /></>}
                    {customer.plz} {customer.ort}
                  </span>
                </p>
              )}
              {customer.vat_id && (
                <p className="mt-1 text-sm text-[var(--color-text-tertiary)]">USt-ID: {customer.vat_id}</p>
              )}
              {customer.archived && (
                <span className="mt-2 inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-600">
                  Archiviert
                </span>
              )}
            </div>
            {customer.offen_eur > 0 && (
              <div className="text-right">
                <p className="text-xs text-[var(--color-text-tertiary)]">Offener Betrag</p>
                <p className="text-lg font-semibold text-amber-700">{eur(customer.offen_eur)}</p>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Edit form */}
      {(isNew || editing) && (
        <form onSubmit={onSubmit} className="space-y-4">
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

          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={create.isPending || update.isPending}
              className="rounded-md bg-[var(--color-text-heading)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {create.isPending || update.isPending ? "Speichere…" : "Speichern"}
            </button>
            {!isNew && (
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setForm(emptyForm);
                  initialized.current = false;
                }}
                className="rounded-md border border-[var(--color-border)] px-4 py-2 text-sm font-semibold text-[var(--color-text-primary)] hover:bg-[var(--color-gray-50)]"
              >
                Abbrechen
              </button>
            )}
          </div>

          {(create.isError || update.isError) && (
            <p className="text-xs text-rose-600" role="alert">
              Speichern fehlgeschlagen.
            </p>
          )}
        </form>
      )}

      {/* Invoices */}
      {!isNew && (
        <section className="rounded-xl border border-[var(--color-border)] bg-white p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
            Rechnungen ({customerInvoices.length})
          </h2>
          {invoicesLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-text-heading)]" />
            </div>
          ) : customerInvoices.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-[10px] border border-dashed border-[var(--color-border)] py-10">
              <FileText size={20} className="text-[var(--color-text-tertiary)]" />
              <p className="mt-2 text-sm text-[var(--color-text-tertiary)]">Noch keine Rechnungen für diesen Kunden.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {customerInvoices.map((inv, i) => (
                <Link
                  key={inv.id}
                  to="/invoices/$id"
                  params={{ id: String(inv.id) }}
                  className="group flex items-stretch overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-white transition-all duration-150 hover:border-[var(--color-border-strong)] hover:shadow-[0_2px_12px_rgba(0,0,0,0.04)]"
                  style={{ animationDelay: `${i * 30}ms` }}
                >
                  <div
                    className={`w-1 shrink-0 ${
                      inv.status === "PAID"
                        ? "bg-[var(--color-green-500)]"
                        : inv.status === "OPEN" || inv.status === "SENT"
                        ? "bg-[var(--color-blue-500)]"
                        : inv.status === "CANCELLED"
                        ? "bg-[var(--color-red-500)]"
                        : inv.status === "FINALIZED"
                        ? "bg-[var(--color-violet-500)]"
                        : "bg-[var(--color-gray-300)]"
                    }`}
                  />
                  <div className="flex flex-1 items-center gap-4 px-4 py-3">
                    <div className="w-24 shrink-0">
                      <div className="font-mono text-xs font-semibold text-[var(--color-text-primary)]">
                        {inv.nr || `#${inv.id}`}
                      </div>
                      <div className="mt-0.5 text-[11px] text-[var(--color-text-tertiary)]">{inv.date || "—"}</div>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-[var(--color-text-primary)]">
                        {inv.title || "Rechnung"}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-sm font-semibold tabular-nums text-[var(--color-text-primary)]">
                        {eur(inv.total_brutto)}
                      </div>
                    </div>
                    <div className="w-20 shrink-0 text-right">
                      <StatusBadge status={inv.status} />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
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
