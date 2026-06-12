import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Upload, FileText } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api";

export const Route = createFileRoute("/_app/documents")({
  component: DocumentsPage,
});

const documentSchema = z.object({
  id: z.number().int(),
  filename: z.string(),
  original_filename: z.string().default(""),
  mime: z.string().default(""),
  size: z.number().int().default(0),
  source: z.string().default("MANUAL"),
  created_at: z.string().default(""),
});
type Document = z.infer<typeof documentSchema>;

function DocumentsPage() {
  const qc = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () =>
      api
        .get<unknown>("/api/documents")
        .then((res) => z.array(documentSchema).parse(res))
        .catch(() => [] as Document[]),
  });

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

  return (
    <div>
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Belege</h1>
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
      </header>

      {error && (
        <p className="mb-3 text-xs text-rose-600" role="alert">{error}</p>
      )}

      <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-[var(--color-border)] bg-[var(--color-gray-50)] text-left text-xs uppercase tracking-wider text-[var(--color-text-tertiary)]">
            <tr>
              <th className="px-3 py-2">Datei</th>
              <th className="px-3 py-2">Quelle</th>
              <th className="px-3 py-2">Datum</th>
              <th className="px-3 py-2 text-right">Größe</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-[var(--color-text-tertiary)]">Lädt…</td>
              </tr>
            )}
            {data && data.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-xs text-[var(--color-text-tertiary)]">
                  Noch keine Belege.
                </td>
              </tr>
            )}
            {data?.map((d) => (
              <tr key={d.id} className="border-b border-[var(--color-border-subtle)] last:border-0">
                <td className="px-3 py-2">
                  <a
                    href={`/api/documents/${d.id}/file`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-[var(--color-text-heading)] hover:underline"
                  >
                    <FileText size={12} /> {d.original_filename || d.filename}
                  </a>
                </td>
                <td className="px-3 py-2 text-xs text-[var(--color-text-tertiary)]">{d.source}</td>
                <td className="px-3 py-2 text-xs text-[var(--color-text-tertiary)]">{d.created_at || "—"}</td>
                <td className="px-3 py-2 text-right text-xs text-[var(--color-text-tertiary)]">
                  {(d.size / 1024).toFixed(1)} KB
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}