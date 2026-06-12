import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api";

export const Route = createFileRoute("/_app/invites")({
  component: InvitesPage,
});

const inviteSchema = z.object({
  email: z.string(),
  invited_at: z.string().default(""),
});
type Invite = z.infer<typeof inviteSchema>;

function InvitesPage() {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["invites"],
    queryFn: () =>
      api
        .get<unknown>("/api/invites")
        .then((res) => z.array(inviteSchema).parse(res))
        .catch(() => [] as Invite[]),
  });

  const add = useMutation({
    mutationFn: (e: string) => api.post("/api/invites", { email: e }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invites"] });
      setEmail("");
    },
  });

  const remove = useMutation({
    mutationFn: (e: string) => api.delete(`/api/invites/${encodeURIComponent(e)}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invites"] }),
  });

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Einladungen</h1>
      <p className="mb-4 text-xs text-[var(--color-text-tertiary)]">
        Nur der Owner kann diese Seite sehen. Eingeladene E-Mails dürfen sich registrieren.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (email) add.mutate(email);
        }}
        className="mb-4 flex gap-2"
      >
        <input
          type="email"
          required
          placeholder="neue@firma.de"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="block flex-1 rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-text-heading)]"
        />
        <button
          type="submit"
          disabled={add.isPending}
          className="inline-flex items-center gap-1 rounded-md bg-[var(--color-text-heading)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          <Plus size={14} /> Hinzufügen
        </button>
      </form>

      <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-white">
        <ul className="divide-y divide-slate-100">
          {isLoading && <li className="px-3 py-4 text-center text-xs text-[var(--color-text-tertiary)]">Lädt…</li>}
          {data && data.length === 0 && (
            <li className="px-3 py-4 text-center text-xs text-[var(--color-text-tertiary)]">Keine Einladungen.</li>
          )}
          {data?.map((inv) => (
            <li key={inv.email} className="flex items-center justify-between px-3 py-2 text-sm">
              <span className="text-[var(--color-text-heading)]">{inv.email}</span>
              <button
                type="button"
                onClick={() => remove.mutate(inv.email)}
                aria-label="Einladung entfernen"
                className="rounded p-1 text-rose-500 hover:bg-rose-50"
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-4 text-xs text-[var(--color-text-tertiary)]">
        Hinweis: <code className="rounded bg-[var(--color-gray-100)] px-1">/api/invites</code> ist M5-Lite; das Backend bietet aktuell
        <code className="rounded bg-[var(--color-gray-100)] px-1">services.auth.list_invited_emails / add_invited_email / remove_invited_email</code>,
        das im API-Finalisierungsschritt an einen Router angebunden wird.
      </p>
    </div>
  );
}