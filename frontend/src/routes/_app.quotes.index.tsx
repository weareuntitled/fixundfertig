/**
 * @schema QuotesListPage
 * @purpose All quotes of the current company, with the way to write a new one
 */
import { Link, createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { QuoteList } from "@/components/quote/quote-list";
import { useQuotes } from "@/lib/use-invoices";

export const Route = createFileRoute("/_app/quotes/")({
  component: QuotesListPage,
});

function QuotesListPage() {
  const { data: quotes, isLoading, isError } = useQuotes();

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-[32px] font-semibold tracking-tight text-[var(--color-text-heading)] leading-[1.1]">
            Angebote
          </h1>
          <p className="mt-1.5 text-[15px] text-[var(--color-text-secondary)]">
            {quotes ? `${quotes.length} Angebote insgesamt` : "Lädt…"}
          </p>
        </div>
        <Link
          to="/quotes/new"
          className="inline-flex min-h-[44px] items-center justify-center gap-1.5 px-4 rounded-[8px] bg-[var(--color-text-heading)] text-[13px] font-medium text-white shadow-sm transition-all hover:bg-[var(--color-gray-700)] active:scale-[0.97]"
        >
          <Plus size={15} strokeWidth={2.25} />
          Neues Angebot
        </Link>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-text-heading)]" />
        </div>
      )}

      {isError && (
        <div className="rounded-[10px] border border-[var(--color-red-100)] bg-[var(--color-red-50)] px-4 py-3 text-[14px] text-[var(--color-red-600)]">
          Fehler beim Laden der Angebote.
        </div>
      )}

      {quotes && <QuoteList quotes={quotes} />}
    </div>
  );
}
