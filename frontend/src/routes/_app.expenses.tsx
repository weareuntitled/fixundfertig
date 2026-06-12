import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api";

export const Route = createFileRoute("/_app/expenses")({
  component: ExpensesPage,
});

const expenseSchema = z.object({
  id: z.number().int(),
  date: z.string(),
  category: z.string(),
  description: z.string(),
  amount: z.number(),
  source: z.string().default(""),
});
type Expense = z.infer<typeof expenseSchema>;

function ExpensesPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["expenses"],
    queryFn: () =>
      api
        .get<unknown>("/api/expenses")
        .then((res) => z.array(expenseSchema).parse(res))
        .catch(() => [] as Expense[]), // M5-Lite: Endpoint noch nicht da, fallback leer
  });

  const del = useMutation({
    mutationFn: (id: number) => api.delete(`/api/expenses/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["expenses"] }),
  });

  const [showForm, setShowForm] = useState(false);

  return (
    <div>
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Ausgaben</h1>
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="inline-flex items-center gap-1 rounded-md bg-[var(--color-text-heading)] px-3 py-1.5 text-sm font-semibold text-white"
        >
          <Plus size={14} /> Neue Ausgabe
        </button>
      </header>

      <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-[var(--color-border)] bg-[var(--color-gray-50)] text-left text-xs uppercase tracking-wider text-[var(--color-text-tertiary)]">
            <tr>
              <th className="px-3 py-2">Datum</th>
              <th className="px-3 py-2">Kategorie</th>
              <th className="px-3 py-2">Beschreibung</th>
              <th className="px-3 py-2 text-right">Betrag</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-[var(--color-text-tertiary)]">Lädt…</td>
              </tr>
            )}
            {isError && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-rose-600">Fehler beim Laden.</td>
              </tr>
            )}
            {data && data.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-xs text-[var(--color-text-tertiary)]">
                  Noch keine Ausgaben erfasst. (M5-Lite: Backend-Endpoint <code>GET /api/expenses</code> folgt in der API-Finalisierung.)
                </td>
              </tr>
            )}
            {data?.map((e) => (
              <tr key={e.id} className="border-b border-[var(--color-border-subtle)] last:border-0">
                <td className="px-3 py-2 text-[var(--color-text-secondary)]">{e.date}</td>
                <td className="px-3 py-2 text-[var(--color-text-primary)]">{e.category}</td>
                <td className="px-3 py-2 text-[var(--color-text-heading)]">{e.description}</td>
                <td className="px-3 py-2 text-right font-numeric tabular-nums text-[var(--color-text-heading)]">
                  {e.amount.toFixed(2)} €
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => del.mutate(e.id)}
                    aria-label="Ausgabe löschen"
                    className="rounded p-1 text-rose-500 hover:bg-rose-50"
                  >
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <ExpenseForm
          onClose={() => setShowForm(false)}
          onCreated={() => {
            setShowForm(false);
            qc.invalidateQueries({ queryKey: ["expenses"] });
          }}
        />
      )}
    </div>
  );
}

interface ExpenseFormProps {
  onClose: () => void;
  onCreated: () => void;
}

function ExpenseForm({ onClose, onCreated }: ExpenseFormProps) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [category, setCategory] = useState("Sonstiges");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState(0);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    api
      .post("/api/expenses", { date, category, description, amount })
      .then(onCreated)
      .catch(() => alert("M5-Lite: Backend-Endpoint noch nicht aktiv."));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-md rounded-xl border border-[var(--color-border)] bg-white p-6 shadow-lg"
      >
        <h2 className="mb-4 text-base font-semibold text-[var(--color-text-heading)]">Neue Ausgabe</h2>
        <div className="space-y-3">
          <label className="block text-xs font-medium text-[var(--color-text-primary)]">
            Datum
            <input
              type="date"
              required
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 block w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-xs font-medium text-[var(--color-text-primary)]">
            Kategorie
            <input
              type="text"
              required
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="mt-1 block w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-xs font-medium text-[var(--color-text-primary)]">
            Beschreibung
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="mt-1 block w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-xs font-medium text-[var(--color-text-primary)]">
            Betrag (€)
            <input
              type="number"
              step="0.01"
              min="0"
              required
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
            />
          </label>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-3 py-2 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-gray-50)]"
          >
            Abbrechen
          </button>
          <button
            type="submit"
            className="rounded-md bg-[var(--color-text-heading)] px-3 py-2 text-sm font-semibold text-white"
          >
            Speichern
          </button>
        </div>
      </form>
    </div>
  );
}