import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Upload, FileText, Search, X, Download, CalendarDays } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api";

export const Route = createFileRoute("/_app/documents")({
  component: DocumentsPage,
  validateSearch: (search: Record<string, unknown>) => ({
    year: (search.year as string) || "",
  }),
});

const documentSchema = z.object({
  id: z.number().int(),
  original_filename: z.string().default(""),
  title: z.string().default(""),
  vendor: z.string().default(""),
  doc_number: z.string().default(""),
  doc_date: z.string().default(""),
  amount_total: z.number().nullable().default(null),
  amount_net: z.number().nullable().default(null),
  amount_tax: z.number().nullable().default(null),
  currency: z.string().default(""),
  mime: z.string().default(""),
  size: z.number().int().default(0),
  source: z.string().default("MANUAL"),
  type: z.string().default(""),
  created_at: z.string().default(""),
});
type Document = z.infer<typeof documentSchema>;

function fmtCurrency(amount: number | null, currency: string): string {
  if (amount == null) return "—";
  return `${amount.toFixed(2)} ${currency || "EUR"}`;
}

function fmtDate(raw: string): string {
  if (!raw) return "—";
  try {
    return new Date(raw).toLocaleDateString("de-DE");
  } catch {
    return raw.slice(0, 10);
  }
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function sourceBadge(source: string) {
  const colors: Record<string, string> = {
    MANUAL: "bg-blue-100 text-blue-700",
    N8N: "bg-purple-100 text-purple-700",
    n8n: "bg-purple-100 text-purple-700",
  };
  return colors[source] || "bg-gray-100 text-gray-600";
}

function typeBadge(type: string) {
  const colors: Record<string, string> = {
    pdf: "bg-rose-100 text-rose-700",
    jpg: "bg-amber-100 text-amber-700",
    jpeg: "bg-amber-100 text-amber-700",
    png: "bg-teal-100 text-teal-700",
  };
  return colors[type] || "bg-gray-100 text-gray-600";
}

const YEARS = Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i);

function buildParams(year: string, search: string) {
  const params = new URLSearchParams();
  if (year) {
    params.set("date_from", `${year}-01-01`);
    params.set("date_to", `${year}-12-31`);
  }
  if (search) params.set("q", search);
  return params.toString();
}

function DocumentsPage() {
  const { year } = Route.useSearch();
  const [selectedYear, setSelectedYear] = useState<string>(year || String(new Date().getFullYear()));
  const qc = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["documents", selectedYear, search],
    queryFn: () =>
      api
        .get<unknown>(`/api/documents?${buildParams(selectedYear, search)}`)
        .then((res) => z.array(documentSchema).parse(res))
        .catch(() => [] as Document[]),
  });

  const filtered = data ?? [];

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const csrf = document.cookie
        .split("; ")
        .find((c) => c.startsWith("ff_csrf="))
        ?.split("=")[1];
      const response = await fetch("/api/documents/upload", {
        method: "POST",
        credentials: "include",
        headers: csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {},
        body: form,
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      qc.invalidateQueries({ queryKey: ["documents"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload fehlgeschlagen");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const exportZip = () => {
    window.open(
      `/api/exports/documents-zip?${buildParams(selectedYear, "")}`,
      "_blank",
    );
  };

  return (
    <div>
      <header className="mb-4 flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Belege</h1>
        <div className="flex items-center gap-2">
          <div className="relative">
            <CalendarDays size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(e.target.value)}
              className="h-8 rounded-md border border-[var(--color-border)] bg-white pl-7 pr-2 text-xs outline-none focus:border-indigo-400 appearance-none"
            >
              <option value="">Alle Jahre</option>
              {YEARS.map((y) => (
                <option key={y} value={String(y)}>{y}</option>
              ))}
            </select>
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Suchen..."
              className="h-8 rounded-md border border-[var(--color-border)] bg-white pl-8 pr-7 text-xs outline-none focus:border-indigo-400"
            />
            {search && (
              <button onClick={() => setSearch("")} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)] hover:text-gray-700">
                <X size={14} />
              </button>
            )}
          </div>
          <button
            onClick={exportZip}
            className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-[var(--color-border)] bg-white px-3 py-1.5 text-sm text-[var(--color-text-heading)] hover:bg-[var(--color-gray-50)]"
          >
            <Download size={14} />
            Export
          </button>
          <label className="inline-flex cursor-pointer items-center gap-1 rounded-md bg-[var(--color-text-heading)] px-3 py-1.5 text-sm font-semibold text-white">
            <Upload size={14} />
            {uploading ? "Lädt hoch…" : "Upload"}
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={onUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
        </div>
      </header>

      {error && (
        <p className="mb-3 text-xs text-rose-600" role="alert">{error}</p>
      )}

      <div className="overflow-x-auto rounded-xl border border-[var(--color-border)] bg-white">
        <table className="w-full text-sm whitespace-nowrap">
          <thead className="border-b border-[var(--color-border)] bg-[var(--color-gray-50)] text-left text-xs uppercase tracking-wider text-[var(--color-text-tertiary)]">
            <tr>
              <th className="px-3 py-2">Beleg</th>
              <th className="px-3 py-2">Lieferant</th>
              <th className="px-3 py-2">Beleg-Nr.</th>
              <th className="px-3 py-2">Datum</th>
              <th className="px-3 py-2 text-right">Betrag</th>
              <th className="px-3 py-2 text-right">Netto</th>
              <th className="px-3 py-2">Typ</th>
              <th className="px-3 py-2">Quelle</th>
              <th className="px-3 py-2 text-right">Größe</th>
              <th className="px-3 py-2">Hochgeladen</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={10} className="px-3 py-6 text-center text-[var(--color-text-tertiary)]">Lädt…</td>
              </tr>
            )}
            {!isLoading && filtered.length === 0 && (
              <tr>
                <td colSpan={10} className="px-3 py-6 text-center text-xs text-[var(--color-text-tertiary)]">
                  {search ? "Keine Belege gefunden." : "Noch keine Belege."}
                </td>
              </tr>
            )}
            {filtered.map((d) => (
              <tr key={d.id} className="border-b border-[var(--color-border-subtle)] last:border-0 hover:bg-[var(--color-gray-50)]">
                <td className="px-3 py-2 max-w-[200px] truncate">
                  <a
                    href={`/api/documents/${d.id}/file`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-[var(--color-text-heading)] hover:underline"
                  >
                    <FileText size={12} className="shrink-0" />
                    <span className="truncate">{d.title || d.original_filename}</span>
                  </a>
                </td>
                <td className="px-3 py-2 text-xs text-[var(--color-text-tertiary)]">{d.vendor || "—"}</td>
                <td className="px-3 py-2 text-xs text-[var(--color-text-tertiary)]">{d.doc_number || "—"}</td>
                <td className="px-3 py-2 text-xs text-[var(--color-text-tertiary)]">{fmtDate(d.doc_date)}</td>
                <td className="px-3 py-2 text-right text-xs font-medium tabular-nums">{fmtCurrency(d.amount_total, d.currency)}</td>
                <td className="px-3 py-2 text-right text-xs tabular-nums text-[var(--color-text-tertiary)]">{fmtCurrency(d.amount_net, d.currency)}</td>
                <td className="px-3 py-2">
                  <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${typeBadge(d.type)}`}>
                    {d.type || "?"}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${sourceBadge(d.source)}`}>
                    {d.source}
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-xs text-[var(--color-text-tertiary)] tabular-nums">
                  {fmtSize(d.size)}
                </td>
                <td className="px-3 py-2 text-xs text-[var(--color-text-tertiary)]">{fmtDate(d.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
