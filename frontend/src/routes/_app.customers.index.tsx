import { Link, createFileRoute } from "@tanstack/react-router";
import { Plus, Users, Mail, MapPin, Search } from "lucide-react";
import { useCustomers } from "@/lib/use-customers";
import { useState, useMemo } from "react";

export const Route = createFileRoute("/_app/customers/")({
  component: CustomersListPage,
});

function displayName(c: { name: string; vorname: string; nachname: string }): string {
  if (c.name) return c.name;
  const combined = [c.vorname, c.nachname].filter(Boolean).join(" ");
  return combined || "(unbenannt)";
}

function CustomersListPage() {
  const { data: customers, isLoading, isError } = useCustomers();
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!customers) return [];
    if (!search) return customers;
    const q = search.toLowerCase();
    return customers.filter(
      (c) =>
        c.name?.toLowerCase().includes(q) ||
        c.vorname?.toLowerCase().includes(q) ||
        c.nachname?.toLowerCase().includes(q) ||
        c.email?.toLowerCase().includes(q) ||
        c.ort?.toLowerCase().includes(q)
    );
  }, [customers, search]);

  return (
    <div className="animate-fade-in space-y-4">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--color-text-heading)]">Kunden</h1>
          <p className="mt-0.5 text-sm text-[var(--color-text-tertiary)]">
            {customers ? `${customers.length} Kunden insgesamt` : "Lädt..."}
          </p>
        </div>
        <Link
          to="/customers/$id"
          params={{ id: "new" }}
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--color-text-heading)] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-[var(--color-gray-700)] hover:shadow-md"
        >
          <Plus size={16} /> Neuer Kunde
        </Link>
      </header>

      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
        <input
          type="text"
          placeholder="Kunden suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-[var(--color-border)] bg-white py-2.5 pl-10 pr-4 text-sm outline-none transition-colors focus:border-[var(--color-text-heading)] focus:ring-2 focus:ring-[var(--color-text-heading)]/10"
        />
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading && (
          <div className="col-span-full flex items-center justify-center py-12">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--color-border-strong)] border-t-[var(--color-text-heading)]" />
          </div>
        )}
        {isError && (
          <div className="col-span-full py-12 text-center">
            <p className="text-sm text-rose-600">Fehler beim Laden der Kunden.</p>
          </div>
        )}
        {!isLoading && !isError && filtered.length === 0 && (
          <div className="col-span-full py-12 text-center">
            <Users size={40} className="mx-auto mb-3 text-[var(--color-gray-300)]" />
            <p className="text-sm font-medium text-[var(--color-text-heading)]">
              {search ? "Keine Ergebnisse" : "Noch keine Kunden"}
            </p>
            <p className="mt-1 text-xs text-[var(--color-text-tertiary)]">
              {search ? "Versuche andere Suchkriterien" : 'Erstelle deinen ersten Kunden mit "Neuer Kunde"'}
            </p>
          </div>
        )}
        {filtered.map((c) => (
          <Link
            key={c.id}
            to="/customers/$id"
            params={{ id: String(c.id) }}
            className="group rounded-xl border border-[var(--color-border)] bg-white p-4 shadow-sm transition-all hover:border-[var(--color-blue-500)] hover:shadow-md"
          >
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--color-blue-50)] text-sm font-semibold text-[var(--color-text-heading)]">
                {displayName(c).charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-[var(--color-text-heading)] group-hover:text-[var(--color-text-heading)]">
                  {displayName(c)}
                </div>
                {c.email && (
                  <div className="mt-0.5 flex items-center gap-1 text-xs text-[var(--color-text-tertiary)]">
                    <Mail size={10} /> {c.email}
                  </div>
                )}
                {(c.plz || c.ort) && (
                  <div className="mt-1 flex items-center gap-1 text-xs text-[var(--color-text-tertiary)]">
                    <MapPin size={10} /> {c.plz} {c.ort}
                  </div>
                )}
              </div>
            </div>
            {c.offen_eur > 0 && (
              <div className="mt-3 rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs font-semibold text-amber-700">
                {c.offen_eur.toLocaleString("de-DE", { minimumFractionDigits: 2 })} € offen
              </div>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
