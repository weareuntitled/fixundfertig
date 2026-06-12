import { Link, createFileRoute } from "@tanstack/react-router";
import { Building2, Hash, FileSignature, Plug, UserCog, Share2 } from "lucide-react";

export const Route = createFileRoute("/_app/settings/")({
  component: SettingsHubPage,
});

function SettingsHubPage() {
  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Einstellungen</h1>
      <p className="mb-4 text-xs text-[var(--color-text-tertiary)]">
        Hub: Wähle eine Kategorie.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <HubCard icon={Building2} title="Firma" subtitle="Stammdaten, Adresse" to="/settings/company" testId="hub-company" />
        <HubCard icon={Hash} title="Rechnungsnummern" subtitle="Template, nächste Nummer" to="/settings/invoice-numbers" testId="hub-invoice-numbers" />
        <HubCard icon={FileSignature} title="Steuern & Bank" subtitle="USt-ID, IBAN, BIC" to="/settings/tax-banking" testId="hub-tax-banking" />
        <HubCard icon={Plug} title="Integrationen" subtitle="SMTP, n8n, Google Drive" to="/settings/integrations" testId="hub-integrations" />
        <HubCard icon={UserCog} title="Account" subtitle="Passwort ändern" to="/settings/account" testId="hub-account" />
        <HubCard icon={Share2} title="Teilen" subtitle="Read-only-Links verwalten" to="/settings/share" testId="hub-share" />
      </div>
    </div>
  );
}

interface HubCardProps {
  icon: typeof Building2;
  title: string;
  subtitle: string;
  to: string;
  testId?: string;
}

function HubCard({ icon: Icon, title, subtitle, to, testId }: HubCardProps) {
  return (
    <Link
      to={to}
      className="block rounded-xl border border-[var(--color-border)] bg-white p-4 transition-colors hover:border-[var(--color-border-strong)]"
      data-testid={testId}
    >
      <div className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-heading)]">
        <Icon size={16} /> {title}
      </div>
      <div className="mt-1 text-xs text-[var(--color-text-tertiary)]">{subtitle}</div>
    </Link>
  );
}
