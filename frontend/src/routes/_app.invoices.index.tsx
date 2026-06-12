import { Link, createFileRoute } from "@tanstack/react-router";
import { Plus, Search, FileText, X } from "lucide-react";
import { useInvoices } from "@/lib/use-invoices";
import { useState, useMemo } from "react";
import { StatusBadge, STATUS_LABELS } from "@/components/ui/status-badge";

export const Route = createFileRoute("/_app/invoices/")({
  component: InvoicesListPage,
});

const STATUS_FILTERS = ["ALL", "OPEN", "SENT", "PAID", "DRAFT", "FINALIZED", "CANCELLED"] as const;

const eur = (n: number) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

function InvoicesListPage() {
  const { data: invoices, isLoading, isError } = useInvoices();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>("ALL");

  const filtered = useMemo(() => {
    if (!invoices) return [];
    const q = search.toLowerCase();
    return invoices.filter((inv) => {
      const matchesSearch =
        !q ||
        inv.nr?.toLowerCase().includes(q) ||
        inv.title?.toLowerCase().includes(q) ||
        inv.recipient_name?.toLowerCase().includes(q);
      const matchesStatus = statusFilter === "ALL" || inv.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [invoices, search, statusFilter]);

  const statusCounts = useMemo(() => {
    if (!invoices) return {} as Record<string, number>;
    const counts: Record<string, number> = { ALL: invoices.length };
    for (const inv of invoices) {
      counts[inv.status] = (counts[inv.status] || 0) + 1;
    }
    return counts;
  }, [invoices]);

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-[32px] font-semibold tracking-tight text-[var(--color-text-heading)] leading-[1.1]">
            Rechnungen
          </h1>
          <p className="mt-1.5 text-[15px] text-[var(--color-text-secondary)]">
            {invoices ? `${invoices.length} Rechnungen insgesamt` : "Lädt…"}
          </p>
        </div>
        <Link
          to="/invoices/new"
          className="inline-flex items-center justify-center gap-1.5 h-9 px-4 rounded-[8px] bg-[var(--color-text-heading)] text-[13px] font-medium text-white shadow-sm transition-all hover:bg-[var(--color-gray-700)] active:scale-[0.97]"
        >
          <Plus size={15} strokeWidth={2.25} />
          Neue Rechnung
        </Link>
      </div>

      {/* Search */}
      <div className="relative">
        <Search
          size={15}
          strokeWidth={2}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)] pointer-events-none"
        />
        <input
          type="text"
          placeholder="Rechnungen suchen…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full h-10 rounded-[10px] border border-[var(--color-border)] bg-white pl-9 pr-9 text-[14px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] outline-none transition-all focus:border-[var(--color-border-focus)] focus:shadow-[0_0_0_3px_rgba(0,122,255,0.12)]"
        />
        {search && (
          <button
            type="button"
            onClick={() => setSearch("")}
            aria-label="Suche löschen"
            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded-full text-[var(--color-text-tertiary)] hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text-secondary)] transition-colors"
          >
            <X size={13} />
          </button>
        )}
      </div>

      {/* Status tabs — Apple-style pill strip */}
      <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-1 px-1">
        {STATUS_FILTERS.map((s) => {
          const active = statusFilter === s;
          const count = statusCounts[s];
          return (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={`whitespace-nowrap inline-flex items-center gap-1.5 rounded-full px-3.5 h-8 text-[13px] font-medium transition-all ${
                active
                  ? "bg-[var(--color-text-heading)] text-white shadow-sm"
                  : "bg-white text-[var(--color-text-secondary)] border border-[var(--color-border)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-text-primary)]"
              }`}
            >
              {STATUS_LABELS[s]}
              {count !== undefined && (
                <span className={`text-[11px] ${active ? "opacity-70" : "text-[var(--color-text-tertiary)]"}`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Invoice Cards — editorial layout */}
      <div className="space-y-2">
        {isLoading && (
          <div className="flex items-center justify-center py-16">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-text-heading)]" />
          </div>
        )}

        {isError && (
          <div className="rounded-[10px] border border-[var(--color-red-100)] bg-[var(--color-red-50)] px-4 py-3 text-[14px] text-[var(--color-red-600)]">
            Fehler beim Laden der Rechnungen.
          </div>
        )}

        {!isLoading && !isError && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center rounded-[12px] border border-dashed border-[var(--color-border)] bg-white py-16">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-gray-50)]">
              <FileText size={20} className="text-[var(--color-text-tertiary)]" />
            </div>
            <p className="text-[15px] font-medium text-[var(--color-text-primary)]">
              {search || statusFilter !== "ALL" ? "Keine Ergebnisse" : "Noch keine Rechnungen"}
            </p>
            <p className="mt-1 text-[13px] text-[var(--color-text-tertiary)]">
              {search || statusFilter !== "ALL"
                ? "Versuche andere Suchkriterien"
                : "Erstelle deine erste Rechnung"}
            </p>
          </div>
        )}

        {filtered.map((inv, i) => (
          <Link
            key={inv.id}
            to="/invoices/$id"
            params={{ id: String(inv.id) }}
            className="group flex items-stretch overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-white transition-all duration-150 hover:border-[var(--color-border-strong)] hover:shadow-[0_2px_12px_rgba(0,0,0,0.04)] animate-fade-in"
            style={{ animationDelay: `${i * 30}ms` }}
          >
            {/* Status strip — left edge */}
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

            {/* Content */}
            <div className="flex flex-1 items-center gap-5 px-5 py-3.5">
              {/* Nr + Date */}
              <div className="w-28 shrink-0">
                <div className="font-mono text-[12.5px] font-semibold text-[var(--color-text-primary)]">
                  {inv.nr || `#${inv.id}`}
                </div>
                <div className="mt-0.5 text-[11.5px] text-[var(--color-text-tertiary)]">
                  {inv.date || "—"}
                </div>
              </div>

              {/* Title + Customer */}
              <div className="min-w-0 flex-1">
                <div className="truncate text-[14px] font-medium text-[var(--color-text-primary)]">
                  {inv.title || "Rechnung"}
                </div>
                <div className="mt-0.5 truncate text-[12.5px] text-[var(--color-text-tertiary)]">
                  {inv.recipient_name || `Kunde #${inv.customer_id}`}
                </div>
              </div>

              {/* Amount — right-aligned, tabular */}
              <div className="text-right">
                <div className="font-mono text-[15px] font-semibold tabular-nums text-[var(--color-text-primary)]">
                  {eur(inv.total_brutto)}
                </div>
              </div>

              {/* Status badge */}
              <div className="w-24 shrink-0 text-right">
                <StatusBadge status={inv.status} />
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
