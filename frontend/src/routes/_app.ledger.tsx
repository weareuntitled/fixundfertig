import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/_app/ledger")({
  component: LedgerPage,
});

const ledgerEntrySchema = z.object({
  type: z.enum(["invoice", "expense"]),
  id: z.number().int(),
  date: z.string(),
  description: z.string(),
  amount: z.number(),
});

function LedgerPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["ledger"],
    queryFn: () =>
      api
        .get<unknown>("/api/ledger")
        .then((res) => z.array(ledgerEntrySchema).parse(res)),
  });

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Buchhaltung</h1>
      <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-[var(--color-border)] bg-[var(--color-gray-50)] text-left text-xs uppercase tracking-wider text-[var(--color-text-tertiary)]">
            <tr>
              <th className="px-3 py-2">Datum</th>
              <th className="px-3 py-2">Typ</th>
              <th className="px-3 py-2">Beschreibung</th>
              <th className="px-3 py-2 text-right">Betrag</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-[var(--color-text-tertiary)]">Lädt…</td>
              </tr>
            )}
            {isError && (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-rose-600">Fehler beim Laden.</td>
              </tr>
            )}
            {data && data.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-xs text-[var(--color-text-tertiary)]">
                  Keine Einträge.
                </td>
              </tr>
            )}
            {data?.map((entry, idx) => (
              <tr key={`${entry.type}-${entry.id}-${idx}`} className="border-b border-[var(--color-border-subtle)] last:border-0">
                <td className="px-3 py-2 text-[var(--color-text-secondary)]">{entry.date}</td>
                <td className="px-3 py-2">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${
                      entry.type === "invoice"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-rose-100 text-rose-800"
                    }`}
                  >
                    {entry.type === "invoice" ? "Einnahme" : "Ausgabe"}
                  </span>
                </td>
                <td className="px-3 py-2 text-[var(--color-text-heading)]">{entry.description}</td>
                <td className={`px-3 py-2 text-right font-numeric tabular-nums ${
                  entry.type === "invoice" ? "text-emerald-700" : "text-rose-700"
                }`}>
                  {entry.type === "expense" ? "−" : ""}
                  {entry.amount.toFixed(2)} €
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}