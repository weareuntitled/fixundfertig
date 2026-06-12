import { Download, FileText, Database } from "lucide-react";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/_app/exports")({
  component: ExportsPage,
});

/**
 * Triggers a browser download by creating a hidden <a download> element.
 * Works with same-origin URLs (Vite proxy forwards /api/* to the backend).
 */
function triggerDownload(path: string, filename: string) {
  const a = document.createElement("a");
  a.href = path;
  a.download = filename;
  a.target = "_blank";
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function ExportsPage() {
  const currentYear = new Date().getFullYear();
  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Exports</h1>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ExportCard
          title="Rechnungen (PDF, ZIP)"
          description={`Alle Rechnungen des aktuellen Jahres als PDF-Bundle`}
          icon={FileText}
          onClick={() => triggerDownload(`/api/exports/invoices-pdf?year=${currentYear}`, `rechnungen-${currentYear}.zip`)}
        />
        <ExportCard
          title="Rechnungen (CSV)"
          description="Rechnungsdaten als CSV für Buchhaltung"
          icon={FileText}
          onClick={() => triggerDownload(`/api/exports/invoices-csv?year=${currentYear}`, `rechnungen-${currentYear}.csv`)}
        />
        <ExportCard
          title="Positionen (CSV)"
          description="Alle Rechnungspositionen als CSV"
          icon={FileText}
          onClick={() => triggerDownload(`/api/exports/items-csv?year=${currentYear}`, `positionen-${currentYear}.csv`)}
        />
        <ExportCard
          title="Kunden (CSV)"
          description="Kundenstammdaten als CSV"
          icon={FileText}
          onClick={() => triggerDownload(`/api/exports/customers-csv`, `kunden.csv`)}
        />
        <ExportCard
          title="Datenbank-Backup (ZIP)"
          description="Vollständiges Backup der Datenbank + Rechnungs-PDFs"
          icon={Database}
          onClick={() => triggerDownload(`/api/exports/db-backup`, `backup-${currentYear}.zip`)}
        />
      </div>
    </div>
  );
}

interface ExportCardProps {
  title: string;
  description: string;
  icon: typeof FileText;
  onClick: () => void;
}

function ExportCard({ title, description, icon: Icon, onClick }: ExportCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="block rounded-xl border border-[var(--color-border)] bg-white p-4 text-left transition-colors hover:border-[var(--color-border-strong)]"
    >
      <div className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-heading)]">
        <Icon size={16} /> {title}
      </div>
      <div className="mt-1 text-xs text-[var(--color-text-tertiary)]">{description}</div>
      <div className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-[var(--color-text-heading)]">
        <Download size={12} /> Herunterladen
      </div>
    </button>
  );
}
