import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useCompany, useUpdateCompany } from "@/lib/use-company";
import { ArrowLeft, Save } from "lucide-react";

export const Route = createFileRoute("/_app/settings/integrations")({
  component: IntegrationsSettingsPage,
});

function IntegrationsSettingsPage() {
  const { data: company, isLoading, isError } = useCompany();
  const updateCompany = useUpdateCompany();
  const [form, setForm] = useState({
    smtp_server: "",
    smtp_port: 587,
    smtp_user: "",
    smtp_password: "",
    default_sender_email: "",
    n8n_webhook_url: "",
    n8n_webhook_url_test: "",
    n8n_webhook_url_prod: "",
    n8n_secret: "",
    n8n_enabled: false,
    google_drive_folder_id: "",
  });

  useEffect(() => {
    if (company) {
      setForm({
        smtp_server: company.smtp_server,
        smtp_port: company.smtp_port,
        smtp_user: company.smtp_user,
        smtp_password: company.smtp_password,
        default_sender_email: company.default_sender_email,
        n8n_webhook_url: company.n8n_webhook_url,
        n8n_webhook_url_test: company.n8n_webhook_url_test,
        n8n_webhook_url_prod: company.n8n_webhook_url_prod,
        n8n_secret: company.n8n_secret,
        n8n_enabled: company.n8n_enabled,
        google_drive_folder_id: company.google_drive_folder_id,
      });
    }
  }, [company]);

  if (isLoading) return <p className="text-sm text-[var(--color-text-tertiary)]">Lade Einstellungen…</p>;
  if (isError || !company) return <p className="text-sm text-rose-600">Einstellungen konnten nicht geladen werden.</p>;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    updateCompany.mutate(form);
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <Link
          to="/settings"
          className="inline-flex items-center gap-1 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-heading)]"
        >
          <ArrowLeft className="h-4 w-4" /> Zurück
        </Link>
        <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Integrationen</h1>
      </header>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* SMTP Section */}
        <section className="rounded-xl border border-[var(--color-border)] bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-[var(--color-text-heading)]">E-Mail (SMTP)</h2>
          <div className="space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <FormField label="SMTP-Server">
                <input
                  value={form.smtp_server}
                  onChange={(e) => setForm({ ...form, smtp_server: e.target.value })}
                  className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
                  placeholder="smtp.example.com"
                />
              </FormField>
              <FormField label="Port">
                <input
                  type="number"
                  value={form.smtp_port}
                  onChange={(e) => setForm({ ...form, smtp_port: Number(e.target.value) })}
                  className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
                />
              </FormField>
            </div>
            <FormField label="SMTP-Benutzer">
              <input
                value={form.smtp_user}
                onChange={(e) => setForm({ ...form, smtp_user: e.target.value })}
                className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
              />
            </FormField>
            <FormField label="SMTP-Passwort">
              <input
                type="password"
                value={form.smtp_password}
                onChange={(e) => setForm({ ...form, smtp_password: e.target.value })}
                className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
              />
            </FormField>
            <FormField label="Standard-Absender-E-Mail">
              <input
                type="email"
                value={form.default_sender_email}
                onChange={(e) => setForm({ ...form, default_sender_email: e.target.value })}
                className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
              />
            </FormField>
          </div>
        </section>

        {/* n8n Section */}
        <section className="rounded-xl border border-[var(--color-border)] bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-[var(--color-text-heading)]">n8n Automation</h2>
          <div className="space-y-3">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.n8n_enabled}
                onChange={(e) => setForm({ ...form, n8n_enabled: e.target.checked })}
                className="h-4 w-4 rounded border-[var(--color-border-strong)]"
              />
              <span className="text-sm text-[var(--color-text-primary)]">n8n aktiviert</span>
            </label>
            <FormField label="Webhook-URL (Produktion)">
              <input
                value={form.n8n_webhook_url_prod}
                onChange={(e) => setForm({ ...form, n8n_webhook_url_prod: e.target.value })}
                className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
                placeholder="https://your-n8n.example.com/webhook/..."
              />
            </FormField>
            <FormField label="Webhook-URL (Test)">
              <input
                value={form.n8n_webhook_url_test}
                onChange={(e) => setForm({ ...form, n8n_webhook_url_test: e.target.value })}
                className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
              />
            </FormField>
            <FormField label="n8n Secret">
              <input
                type="password"
                value={form.n8n_secret}
                onChange={(e) => setForm({ ...form, n8n_secret: e.target.value })}
                className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
              />
            </FormField>
          </div>
        </section>

        {/* Google Drive Section */}
        <section className="rounded-xl border border-[var(--color-border)] bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-[var(--color-text-heading)]">Google Drive</h2>
          <FormField label="Google Drive Folder ID">
            <input
              value={form.google_drive_folder_id}
              onChange={(e) => setForm({ ...form, google_drive_folder_id: e.target.value })}
              className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
              placeholder="Optional: Folder ID für Backup-Uploads"
            />
          </FormField>
        </section>

        <div className="flex items-center justify-between">
          {updateCompany.isSuccess && (
            <p className="text-xs text-emerald-600">Gespeichert.</p>
          )}
          {updateCompany.isError && (
            <p className="text-xs text-rose-600">Fehler beim Speichern.</p>
          )}
          <button
            type="submit"
            disabled={updateCompany.isPending}
            className="ml-auto inline-flex items-center gap-1 rounded-md bg-[var(--color-text-heading)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            <Save className="h-4 w-4" />
            {updateCompany.isPending ? "Speichere…" : "Speichern"}
          </button>
        </div>
      </form>
    </div>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--color-text-primary)]">{label}</span>
      {children}
    </label>
  );
}
