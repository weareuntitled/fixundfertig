import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ArrowLeft, Plus, Trash2, ExternalLink } from "lucide-react";
import { z } from "zod";

export const Route = createFileRoute("/_app/settings/share")({
  component: ShareSettingsPage,
});

const shareLinkSchema = z.object({
  id: z.number(),
  token: z.string(),
  invoice_id: z.number().nullable(),
  created_at: z.string(),
  expires_at: z.string().nullable(),
});
type ShareLink = z.infer<typeof shareLinkSchema>;

function ShareSettingsPage() {
  const qc = useQueryClient();
  const [invoiceId, setInvoiceId] = useState("");

  const { data: links, isLoading } = useQuery({
    queryKey: ["share-links"],
    queryFn: () =>
      api
        .get<unknown>("/api/invites")
        .then((res) => {
          // The backend currently uses the invites endpoint for share links
          // This is a placeholder until a dedicated share-links endpoint exists
          const parsed = z.array(shareLinkSchema).safeParse(res);
          return parsed.success ? parsed.data : ([] as ShareLink[]);
        })
        .catch(() => [] as ShareLink[]),
  });

  const createLink = useMutation({
    mutationFn: (data: { invoice_id?: number }) =>
      api.post("/api/invites", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["share-links"] });
      setInvoiceId("");
    },
  });

  const deleteLink = useMutation({
    mutationFn: (id: number) => api.delete(`/api/invites/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["share-links"] }),
  });

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <Link
          to="/settings"
          className="inline-flex items-center gap-1 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-heading)]"
        >
          <ArrowLeft className="h-4 w-4" /> Zurück
        </Link>
        <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Teilen</h1>
      </header>

      <p className="text-xs text-[var(--color-text-tertiary)]">
        Erstelle Read-only-Links für deine Rechnungen. Diese können ohne Login eingesehen werden.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const data: { invoice_id?: number } = {};
          if (invoiceId) data.invoice_id = Number(invoiceId);
          createLink.mutate(data);
        }}
        className="flex gap-2"
      >
        <input
          type="number"
          placeholder="Rechnungs-ID (optional)"
          value={invoiceId}
          onChange={(e) => setInvoiceId(e.target.value)}
          className="block flex-1 rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-text-heading)]"
        />
        <button
          type="submit"
          disabled={createLink.isPending}
          className="inline-flex items-center gap-1 rounded-md bg-[var(--color-text-heading)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          <Plus size={14} /> Link erstellen
        </button>
      </form>

      <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-white">
        <ul className="divide-y divide-slate-100">
          {isLoading && <li className="px-3 py-4 text-center text-xs text-[var(--color-text-tertiary)]">Lädt…</li>}
          {links && links.length === 0 && (
            <li className="px-3 py-4 text-center text-xs text-[var(--color-text-tertiary)]">Keine Share-Links vorhanden.</li>
          )}
          {links?.map((link) => (
            <li key={link.id} className="flex items-center justify-between px-3 py-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-[var(--color-text-secondary)]">{link.token}</span>
                {link.invoice_id && (
                  <span className="rounded bg-[var(--color-gray-100)] px-1.5 py-0.5 text-xs text-[var(--color-text-tertiary)]">
                    Rechnung #{link.invoice_id}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                <a
                  href={`/share/read/${link.token}`}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded p-1 text-[var(--color-text-tertiary)] hover:bg-[var(--color-gray-50)]"
                  aria-label="Link öffnen"
                >
                  <ExternalLink size={14} />
                </a>
                <button
                  type="button"
                  onClick={() => deleteLink.mutate(link.id)}
                  aria-label="Link löschen"
                  className="rounded p-1 text-rose-500 hover:bg-rose-50"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
