/**
 * @schema SettingsPage
 * @purpose Unified settings: company, billing, invoice numbering, security, share links, integrations
 * @input None (loads/saves via /api/company, /api/auth/password)
 * @output Renders Lumina-Ledger-style 12-col layout (8/4 split) with 6 sections
 * @tokens Uses: card-*, color-text-*, color-border, color-brand-*, color-surface-*
 *               + inline tertiary-container #001a42 for primary dark actions
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createFileRoute, useBlocker } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCompany, type Company } from "@/lib/use-company";
import { useChangePassword } from "@/lib/use-account";
import { api } from "@/lib/api";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PageHeader } from "@/components/ui/page-header";
import { PAYMENT_TERM_DAYS } from "@/lib/invoice-draft";
import {
  invoiceFilenameExample,
  invoiceNumberExample,
  isValidEmail,
  isValidIban,
  isValidVatId,
} from "@/lib/settings-checks";
import {
  CloudUpload,
  Copy,
  Check,
  Mail,
  Webhook,
  Folder,
  Pencil,
} from "lucide-react";

export const Route = createFileRoute("/_app/settings")({
  component: SettingsPage,
});

type CompanyForm = Omit<Company, "id">;

const DEFAULTS: CompanyForm = {
  name: "",
  first_name: "",
  last_name: "",
  business_type: "",
  is_small_business: false,
  street: "",
  postal_code: "",
  city: "",
  country: "Deutschland",
  email: "",
  phone: "",
  iban: "",
  bic: "",
  bank_name: "",
  account_holder: "",
  tax_id: "",
  vat_id: "",
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
  next_invoice_nr: 10000,
  invoice_number_template: "{seq}",
  invoice_filename_template: "rechnung_{nr}",
  logo_url: "",
  stripe_secret_key: "",
  stripe_publishable_key: "",
  paypal_email: "",
  payment_enabled: false,
};

function SettingsPage() {
  const { data: company, isLoading, isError } = useCompany();
  const updateCompany = useCompanyUpdate();
  const changePassword = useChangePassword();
  const qc = useQueryClient();

  const [form, setForm] = useState<CompanyForm>(DEFAULTS);
  const [shareEnabled, setShareEnabled] = useState(true);
  const [shareHours, setShareHours] = useState(48);
  const [shareInvoiceId, setShareInvoiceId] = useState("");
  const [pwCurrent, setPwCurrent] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwConfirm, setPwConfirm] = useState("");
  const [testEmailTo, setTestEmailTo] = useState("");
  const [testEmailStatus, setTestEmailStatus] = useState<"idle" | "sending" | "ok" | "error">("idle");
  const [testEmailMsg, setTestEmailMsg] = useState("");
  const [copiedOneTime, setCopiedOneTime] = useState(false);
  const [copiedPermanent, setCopiedPermanent] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const [savedVisible, setSavedVisible] = useState(false);
  const [discardOpen, setDiscardOpen] = useState(false);

  const handleLogoUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLogoUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const csrf = document.cookie.split("; ").find((c) => c.startsWith("ff_csrf="))?.split("=")[1];
      const res: Company = await fetch("/api/company/logo", {
        method: "POST",
        credentials: "include",
        headers: csrf ? { "X-CSRF-Token": csrf } : {},
        body: fd,
      }).then((r) => r.json());
      qc.setQueryData(["company"], res);
    } catch {
      // ignore
    } finally {
      setLogoUploading(false);
    }
  }, []);

  useEffect(() => {
    if (company) setForm({ ...DEFAULTS, ...company });
  }, [company]);

  const saved = useMemo(() => (company ? { ...DEFAULTS, ...company } : DEFAULTS), [company]);
  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(saved), [form, saved]);

  const errors = useMemo(() => {
    const found: Partial<Record<keyof CompanyForm, string>> = {};
    if (form.email.trim() && !isValidEmail(form.email)) found.email = "Das sieht nicht nach einer E-Mail-Adresse aus.";
    if (form.iban.trim() && !isValidIban(form.iban)) found.iban = "Diese IBAN ist nicht gültig. Bitte noch einmal prüfen.";
    if (form.vat_id.trim() && !isValidVatId(form.vat_id)) found.vat_id = "Bitte prüfen, zum Beispiel DE123456789.";
    if (!Number.isInteger(form.next_invoice_nr) || form.next_invoice_nr < 1) {
      found.next_invoice_nr = "Eine ganze Zahl ab 1.";
    }
    return found;
  }, [form]);
  const errorLabels: Partial<Record<keyof CompanyForm, string>> = {
    email: "E-Mail",
    iban: "IBAN",
    vat_id: "USt-ID",
    next_invoice_nr: "Nächste Rechnungsnummer",
  };
  const errorKeys = Object.keys(errors) as (keyof CompanyForm)[];

  // Leaving with unsaved changes (link, back button or closing the tab) asks first.
  const leaving = useBlocker({
    shouldBlockFn: () => dirty,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });

  const businessTypeOptions = [
    "Einzelunternehmen",
    ...(form.business_type === "Kleinunternehmer" ? ["Kleinunternehmer"] : []),
    "GmbH",
    "GbR",
    "UG",
    "AG",
    "DJ / Producer",
  ];
  const today = new Date().toISOString().slice(0, 10);
  const numberExample = invoiceNumberExample(form.invoice_number_template, form.next_invoice_nr, today);
  const filenameExample = invoiceFilenameExample(form.invoice_filename_template, numberExample, today);

  const oneTimeLink = useMemo(
    () => `${window.location.origin}/share/1x/${Math.random().toString(36).slice(2, 11)}…`,
    [],
  );
  const permanentLink = `${window.location.origin}/share/p/user_${company?.id ?? "me"}`;

  const handleCopy = (text: string, type: "onetime" | "permanent") => {
    void navigator.clipboard.writeText(text);
    if (type === "onetime") {
      setCopiedOneTime(true);
      setTimeout(() => setCopiedOneTime(false), 2000);
    } else {
      setCopiedPermanent(true);
      setTimeout(() => setCopiedPermanent(false), 2000);
    }
  };

  const set = <K extends keyof CompanyForm>(key: K, value: CompanyForm[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleDiscard = () => {
    if (company) setForm({ ...DEFAULTS, ...company });
    setDiscardOpen(false);
  };

  const handleSaveAll = () => {
    updateCompany.mutate(form, {
      onSuccess: () => {
        setSavedVisible(true);
        setTimeout(() => setSavedVisible(false), 4000);
      },
    });
  };

  const handleUpdatePassword = () => {
    if (pwNew !== pwConfirm) return;
    changePassword.mutate(
      { current_password: pwCurrent, new_password: pwNew },
      {
        onSuccess: () => {
          setPwCurrent("");
          setPwNew("");
          setPwConfirm("");
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-brand-text)]" />
      </div>
    );
  }

  if (isError || !company) {
    return (
      <p className="text-sm text-rose-600" data-testid="settings-error">
        Einstellungen konnten nicht geladen werden.
      </p>
    );
  }

  const pwMismatch = pwConfirm.length > 0 && pwNew !== pwConfirm;
  const pwTooShort = pwNew.length > 0 && pwNew.length < 6;
  const pwValid = pwCurrent && pwNew && pwNew === pwConfirm && pwNew.length >= 6;

  return (
    <div className="animate-fade-in space-y-6">
      <PageHeader
        title="Einstellungen"
        subtitle="Konto-, Firmen- und Integrationseinstellungen verwalten."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* ── Left Column: 8/12 ── */}
        <div className="space-y-6 lg:col-span-8">
          {/* Company & Contact */}
          <Section title="Unternehmen & Kontaktdaten">
            <div className="flex flex-col gap-6 md:flex-row">
              <div className="shrink-0">
                <button
                  type="button"
                  aria-label={company.logo_url ? "Logo ersetzen" : "Logo hochladen"}
                  onClick={() => logoInputRef.current?.click()}
                  className="group relative flex h-32 w-32 flex-col items-center justify-center overflow-hidden rounded-[var(--radius)] border-2 border-dashed border-[var(--color-border)] bg-[var(--color-surface-sunken)] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-overlay)] focus-visible:ring-2 focus-visible:ring-[#001a42]"
                >
                  {company.logo_url ? (
                    <>
                      <img src={company.logo_url} alt="" className="h-full w-full object-contain" />
                      <span className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                        <Pencil size={18} className="text-white" />
                      </span>
                    </>
                  ) : (
                    <>
                      <CloudUpload size={20} className="mb-1" />
                      <span className="px-2 text-center text-[11px] leading-tight">
                        {logoUploading ? "Lädt hoch…" : "Kein Logo"}
                        <br />
                        {!logoUploading && "Zum Hochladen klicken"}
                      </span>
                    </>
                  )}
                </button>
                <input
                  ref={logoInputRef}
                  type="file"
                  accept="image/png,image/jpeg"
                  className="hidden"
                  onChange={handleLogoUpload}
                  aria-label="Logo-Datei auswählen"
                />
              </div>
              <div className="flex-1 grid grid-cols-1 gap-3 md:grid-cols-2">
                <Field
                  className="md:col-span-2"
                  label="Firmen- / Künstlername"
                  value={form.name}
                  onChange={(v) => set("name", v)}
                  placeholder="Firma GmbH oder Daniel S."
                />
                <Field
                  label="Vorname"
                  value={form.first_name}
                  onChange={(v) => set("first_name", v)}
                  placeholder="Max"
                />
                <Field
                  label="Nachname"
                  value={form.last_name}
                  onChange={(v) => set("last_name", v)}
                  placeholder="Mustermann"
                />
                <Field
                  label="E-Mail"
                  type="email"
                  value={form.email}
                  onChange={(v) => set("email", v)}
                  error={errors.email}
                  placeholder="rechnung@firma.de"
                />
                <Field
                  label="Telefon"
                  type="tel"
                  value={form.phone}
                  onChange={(v) => set("phone", v)}
                  placeholder="+49 123 456789"
                />
              </div>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-3 border-t border-[var(--color-border)] pt-4 md:grid-cols-2">
              <Field
                className="md:col-span-2"
                label="Straße"
                value={form.street}
                onChange={(v) => set("street", v)}
                placeholder="Musterstraße 123"
              />
              <Field
                label="PLZ"
                value={form.postal_code}
                onChange={(v) => set("postal_code", v)}
                placeholder="10115"
              />
              <Field
                label="Ort"
                value={form.city}
                onChange={(v) => set("city", v)}
                placeholder="Berlin"
              />
              <SelectField
                className="md:col-span-2"
                label="Land"
                value={form.country}
                onChange={(v) => set("country", v)}
                options={["Deutschland", "Österreich", "Schweiz"]}
              />
            </div>
          </Section>

          {/* Business Meta */}
          <Section title="Geschäftsdaten">
            <SelectField
              className="md:w-1/2"
              label="Unternehmensform / Branche"
              value={form.business_type}
              onChange={(v) => set("business_type", v)}
              options={businessTypeOptions}
            />
            <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
              „DJ / Producer“ aktiviert bei gepflegtem Vor- und Nachnamen den Text-Rechnungskopf für deinen Künstlerauftritt
              und ersetzt dort ein vorhandenes Bildlogo. Der Inhaber wird als rechtlicher Rechnungsaussteller genannt.
              Bereits gespeicherte Rechnungs-PDFs bleiben unverändert.
            </p>
            {form.business_type.trim().toLowerCase() === "dj / producer" && form.name.trim() && (form.first_name.trim() || form.last_name.trim()) && (
              <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
                Im PDF steht: „{form.name.trim()} ist der Künstlername von {[form.first_name.trim(), form.last_name.trim()].filter(Boolean).join(" ")}.“
              </p>
            )}
            <div className="mt-4 flex items-start justify-between gap-4 rounded-[var(--radius)] bg-[var(--color-surface-sunken)] p-3">
              <div>
                <p className="text-[14px] font-semibold text-[var(--color-text-primary)]">Kleinunternehmer (§ 19 UStG)</p>
                <p className="mt-0.5 text-[12px] text-[var(--color-text-secondary)]">
                  Keine Umsatzsteuer auf deinen Rechnungen, mit Hinweis im PDF. Neue Rechnungen starten ohne Umsatzsteuer.
                </p>
              </div>
              <Toggle
                label="Kleinunternehmer (§ 19 UStG)"
                checked={form.is_small_business}
                onChange={(v) => set("is_small_business", v)}
              />
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 border-b border-[var(--color-border)] pb-3 md:grid-cols-2">
              <Field
                className="md:col-span-2"
                label="Kontoinhaber"
                value={form.account_holder}
                onChange={(v) => set("account_holder", v)}
                hint="Leer = dein Vor- und Nachname."
                placeholder="Daniel Peters"
              />
              <Field
                className="md:col-span-2"
                label="IBAN"
                mono
                value={form.iban}
                onChange={(v) => set("iban", v)}
                error={errors.iban}
                hint="Auf der Rechnung steht sie in Vierergruppen."
                placeholder="DE00 0000 0000 0000 0000 00"
              />
              <Field
                label="BIC"
                mono
                value={form.bic}
                onChange={(v) => set("bic", v)}
                placeholder="ABCDEF00XXX"
              />
              <Field
                label="Bankname"
                value={form.bank_name}
                onChange={(v) => set("bank_name", v)}
                placeholder="Musterbank AG"
              />
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field
                label="Steuernummer"
                mono
                value={form.tax_id}
                onChange={(v) => set("tax_id", v)}
                placeholder="00/000/00000"
              />
              <Field
                label="USt-ID"
                mono
                value={form.vat_id}
                onChange={(v) => set("vat_id", v)}
                error={errors.vat_id}
                placeholder="DE123456789"
              />
            </div>
          </Section>

          {/* Invoice Numbering */}
          <Section title="Rechnungsnummern">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field
                label="Nächste Rechnungsnummer"
                type="number"
                mono
                value={form.next_invoice_nr}
                onChange={(v) => set("next_invoice_nr", Number(v))}
                error={errors.next_invoice_nr}
                hint="Die nächste Rechnung bekommt genau diese Nummer. Schon vergebene Nummern nicht noch einmal verwenden."
              />
              <Field
                label="Rechnungsnummer-Regel"
                mono
                value={form.invoice_number_template}
                onChange={(v) => set("invoice_number_template", v)}
                placeholder="RE-{date}-{seq}"
              />
              <Field
                className="md:col-span-2"
                label="Dateiname-Regel (PDF)"
                mono
                value={form.invoice_filename_template}
                onChange={(v) => set("invoice_filename_template", v)}
                placeholder="{nr}_{customer_code}.pdf"
              />
            </div>
            <div className="mt-3 rounded-[var(--radius)] bg-[var(--color-surface-sunken)] p-3 font-mono text-[11px] text-[var(--color-text-secondary)]">
              Verfügbare Platzhalter: {"{seq}"} {"{date}"} {"{customer_code}"} {"{customer_kdnr}"} {"{nr}"}
            </div>
            <div className="mt-3 space-y-1 rounded-[var(--radius)] border border-[var(--color-border)] p-3 text-[12px] text-[var(--color-text-secondary)]" aria-live="polite">
              <p>
                Nächste Rechnung: <span className="font-mono font-semibold text-[var(--color-text-primary)]">{numberExample}</span>
              </p>
              <p>
                Dateiname: <span className="font-mono font-semibold text-[var(--color-text-primary)]">{filenameExample}</span>
              </p>
              <p>Zahlungsfrist auf allen Rechnungen: {PAYMENT_TERM_DAYS} Tage ab Rechnungsdatum.</p>
            </div>
          </Section>

          {/* Account Security */}
          <Section title="Kontosicherheit">
            <div className="max-w-md space-y-3">
              <Field
                label="Aktuelles Passwort"
                type="password"
                value={pwCurrent}
                onChange={setPwCurrent}
                placeholder="••••••••"
              />
              <Field
                label="Neues Passwort (min. 6 Zeichen)"
                type="password"
                value={pwNew}
                onChange={setPwNew}
                placeholder="••••••••"
              />
              <Field
                label="Neues Passwort bestätigen"
                type="password"
                value={pwConfirm}
                onChange={setPwConfirm}
                placeholder="••••••••"
              />
              {pwMismatch && (
                <p className="text-[12px] text-rose-600">Passwörter stimmen nicht überein.</p>
              )}
              {pwTooShort && (
                <p className="text-[12px] text-rose-600">Neues Passwort zu kurz.</p>
              )}
              {changePassword.isError && (
                <p className="text-[12px] text-rose-600">
                  {changePassword.error instanceof Error
                    ? changePassword.error.message
                    : "Fehler beim Ändern."}
                </p>
              )}
              {changePassword.isSuccess && (
                <p className="text-[12px] text-emerald-600">Passwort geändert.</p>
              )}
              <div className="pt-1">
                <button
                  type="button"
                  onClick={handleUpdatePassword}
                  disabled={!pwValid || changePassword.isPending}
                  className="rounded-[var(--radius)] border border-[var(--color-border)] bg-white px-3 py-1.5 text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-bright)] transition-colors disabled:opacity-50"
                >
                  {changePassword.isPending ? "Speichere…" : "Passwort aktualisieren"}
                </button>
              </div>
            </div>
          </Section>
        </div>

        {/* ── Right Column: 4/12 ── */}
        <div className="space-y-6 lg:col-span-4">
          {/* Share Links (Read-only) */}
          <Section
            title="Freigabelinks (Read-only)"
            action={<Toggle label="Freigabelinks aktivieren" checked={shareEnabled} onChange={setShareEnabled} />}
          >
            <div className="space-y-3">
              <Field
                label="Gültig (Stunden)"
                type="number"
                mono
                value={shareHours}
                onChange={(v) => setShareHours(Number(v))}
              />
              <Field
                label="Rechnung-ID (optional)"
                mono
                value={shareInvoiceId}
                onChange={setShareInvoiceId}
                placeholder="Leer für generisch"
              />
              <div className="border-t border-[var(--color-border)] pt-3">
                <div className="text-[12px] font-semibold text-[var(--color-text-primary)]">Einmal-Link</div>
                <div className="mt-1 flex gap-1.5">
                  <input
                    readOnly
                    value={oneTimeLink}
                    className="flex-1 rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-surface-sunken)] px-2 py-1 font-mono text-[11px] text-[var(--color-text-secondary)] outline-none truncate"
                  />
                  <button
                    type="button"
                    onClick={() => handleCopy(oneTimeLink, "onetime")}
                    className="rounded-[var(--radius)] border border-[var(--color-border)] bg-white px-2 py-1 text-[var(--color-text-muted)] hover:bg-[var(--color-surface-bright)] transition-colors"
                    aria-label="Einmal-Link kopieren"
                  >
                    {copiedOneTime ? (
                      <Check size={14} className="text-emerald-600" />
                    ) : (
                      <Copy size={14} />
                    )}
                  </button>
                </div>
              </div>
              <div>
                <div className="text-[12px] font-semibold text-[var(--color-text-primary)]">Permanenter Link</div>
                <div className="mt-1 flex gap-1.5">
                  <input
                    readOnly
                    value={permanentLink}
                    className="flex-1 rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-surface-sunken)] px-2 py-1 font-mono text-[11px] text-[var(--color-text-secondary)] outline-none truncate"
                  />
                  <button
                    type="button"
                    onClick={() => handleCopy(permanentLink, "permanent")}
                    className="rounded-[var(--radius)] border border-[var(--color-border)] bg-white px-2 py-1 text-[var(--color-text-muted)] hover:bg-[var(--color-surface-bright)] transition-colors"
                    aria-label="Permanenten Link kopieren"
                  >
                    {copiedPermanent ? (
                      <Check size={14} className="text-emerald-600" />
                    ) : (
                      <Copy size={14} />
                    )}
                  </button>
                </div>
              </div>
            </div>
          </Section>

          {/* Integrations */}
          <Section title="Integrationen">
            {/* SMTP */}
            <div className="mb-5">
              <h3 className="mb-2 flex items-center gap-1.5 text-[14px] font-semibold text-[var(--color-text-primary)]">
                <Mail size={16} /> SMTP-Konfiguration
              </h3>
              <div className="space-y-2">
                <Field
                  value={form.smtp_server}
                  onChange={(v) => set("smtp_server", v)}
                  placeholder="Server (z.B. smtp.mailgun.org)"
                />
                <div className="grid grid-cols-2 gap-2">
                  <Field
                    type="number"
                    value={form.smtp_port}
                    onChange={(v) => set("smtp_port", Number(v))}
                    placeholder="Port (587)"
                  />
                  <Field
                    value={form.default_sender_email}
                    onChange={(v) => set("default_sender_email", v)}
                    placeholder="Standard-Absender"
                  />
                </div>
                <Field
                  value={form.smtp_user}
                  onChange={(v) => set("smtp_user", v)}
                  placeholder="Benutzer"
                />
                <Field
                  type="password"
                  value={form.smtp_password}
                  onChange={(v) => set("smtp_password", v)}
                  placeholder="Passwort"
                />
              </div>
              <div className="mt-3 flex items-center gap-2">
                <input
                  id="test-email-recipient"
                  value={testEmailTo}
                  onChange={(e) => setTestEmailTo(e.target.value)}
                  placeholder="test@example.com"
                  className="flex-1 rounded-[var(--radius)] border border-[var(--color-border)] px-3 py-1.5 text-[12px] outline-none focus:border-[#001a42]"
                />
                <button
                  type="button"
                  onClick={async () => {
                    if (!testEmailTo) return;
                    setTestEmailStatus("sending");
                    try {
                      const res = await fetch("/api/company/test-email", {
                        method: "POST",
                        credentials: "include",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          to: testEmailTo,
                          smtp_host: form.smtp_server,
                          smtp_port: form.smtp_port,
                          smtp_user: form.smtp_user,
                          smtp_password: form.smtp_password,
                        }),
                      });
                      const data = await res.json();
                      setTestEmailStatus(data.success ? "ok" : "error");
                      setTestEmailMsg(data.message);
                    } catch {
                      setTestEmailStatus("error");
                      setTestEmailMsg("Fehler beim Senden.");
                    }
                  }}
                  disabled={testEmailStatus === "sending" || !testEmailTo}
                  className="shrink-0 rounded-[var(--radius)] border border-[var(--color-border)] bg-white px-3 py-1.5 text-[12px] font-semibold uppercase tracking-[0.05em] hover:bg-[var(--color-surface-bright)] transition-colors disabled:opacity-50"
                >
                  {testEmailStatus === "sending" ? "Sende…" : "Test-E-Mail"}
                </button>
              </div>
              {testEmailMsg && (
                <p className={`mt-1 text-[11px] ${testEmailStatus === "ok" ? "text-emerald-600" : "text-rose-600"}`}>
                  {testEmailMsg}
                </p>
              )}
              <p className="mt-1 text-[11px] text-[var(--color-text-secondary)]">
                STARTTLS oder SSL/TLS je nach Port erforderlich.
              </p>
            </div>

            {/* n8n */}
            <div className="mb-5 border-t border-[var(--color-border)] pt-5">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="flex items-center gap-1.5 text-[14px] font-semibold text-[var(--color-text-primary)]">
                  <Webhook size={16} /> n8n Automatisierungen
                </h3>
                <Toggle
                  label="n8n Automatisierungen aktivieren"
                  checked={form.n8n_enabled}
                  onChange={(v) => set("n8n_enabled", v)}
                />
              </div>
              <div
                className={`space-y-2 transition-opacity ${
                  form.n8n_enabled ? "" : "pointer-events-none opacity-40"
                }`}
              >
                <Field
                  mono
                  value={form.n8n_webhook_url_test}
                  onChange={(v) => set("n8n_webhook_url_test", v)}
                  placeholder="Webhook-URL (Test)"
                />
                <Field
                  mono
                  value={form.n8n_webhook_url_prod}
                  onChange={(v) => set("n8n_webhook_url_prod", v)}
                  placeholder="Webhook-URL (Produktion)"
                />
                <Field
                  type="password"
                  mono
                  value={form.n8n_secret}
                  onChange={(v) => set("n8n_secret", v)}
                  placeholder="Geheimer Schlüssel"
                />
              </div>
            </div>

            {/* Stripe / Payment */}
            <div className="mb-5 border-t border-[var(--color-border)] pt-5">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="flex items-center gap-1.5 text-[14px] font-semibold text-[var(--color-text-primary)]">
                  <span className="text-[16px]">💳</span> Stripe / Online-Zahlungen
                </h3>
                <Toggle
                  label="Online-Zahlungen aktivieren"
                  checked={form.payment_enabled}
                  onChange={(v) => set("payment_enabled", v)}
                />
              </div>
              <div
                className={`space-y-2 transition-opacity ${
                  form.payment_enabled ? "" : "pointer-events-none opacity-40"
                }`}
              >
                <Field
                  type="password"
                  mono
                  value={form.stripe_secret_key}
                  onChange={(v) => set("stripe_secret_key", v)}
                  placeholder="Stripe Secret Key (sk_live_...)"
                />
                <Field
                  mono
                  value={form.stripe_publishable_key}
                  onChange={(v) => set("stripe_publishable_key", v)}
                  placeholder="Stripe Publishable Key (pk_live_...)"
                />
                <Field
                  value={form.paypal_email}
                  onChange={(v) => set("paypal_email", v)}
                  placeholder="PayPal-E-Mail (optional)"
                />
                <button
                  type="button"
                  onClick={async () => {
                    const res = await fetch("/api/company/test-stripe", { method: "POST", credentials: "include" });
                    const data = await res.json();
                    if (data.success) {
                      alert("✅ " + data.message);
                    } else {
                      alert("❌ " + data.message);
                    }
                  }}
                  className="w-full rounded-[var(--radius)] border border-[var(--color-border)] bg-white px-3 py-1.5 text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-bright)] transition-colors"
                >
                  Stripe-Verbindung testen
                </button>
              </div>
            </div>

            {/* Google Drive */}
            <div className="border-t border-[var(--color-border)] pt-5">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="flex items-center gap-1.5 text-[14px] font-semibold text-[var(--color-text-primary)]">
                  <Folder size={16} /> Google Drive
                </h3>
                <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-sunken)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[var(--color-text-muted)]">
                  Deaktiviert
                </span>
              </div>
              <div className="space-y-2">
                <Field
                  mono
                  value={form.google_drive_folder_id}
                  onChange={(v) => set("google_drive_folder_id", v)}
                  placeholder="Drive Folder ID"
                />
                <button
                  type="button"
                  className="w-full rounded-[var(--radius)] border border-[var(--color-border)] bg-white px-3 py-1.5 text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-bright)] transition-colors"
                >
                  Mit Google authentifizieren
                </button>
              </div>
            </div>
          </Section>
        </div>
      </div>

      {(dirty || savedVisible || updateCompany.isError) && (
        <div role="region" aria-label="Änderungen speichern" className="sticky bottom-[4.75rem] z-20 md:bottom-4">
          <div className="flex flex-col gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white p-3 shadow-lg sm:flex-row sm:items-center sm:justify-between">
            <p
              aria-live="polite"
              className={`text-[13px] ${
                (dirty && errorKeys.length > 0) || updateCompany.isError ? "text-rose-700" : "text-[var(--color-text-secondary)]"
              }`}
            >
              {updateCompany.isPending
                ? "Speichere…"
                : dirty && errorKeys.length > 0
                  ? `Bitte prüfen: ${errorKeys.map((key) => errorLabels[key]).join(" · ")}`
                  : updateCompany.isError && dirty
                    ? "Speichern hat nicht geklappt. Deine Änderungen sind noch da."
                    : dirty
                      ? "Ungespeicherte Änderungen"
                      : savedVisible
                        ? "Gespeichert."
                        : ""}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setDiscardOpen(true)}
                disabled={!dirty || updateCompany.isPending}
                className="rounded-[var(--radius)] border border-[var(--color-border)] bg-white px-3 py-2 text-[13px] font-semibold text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-bright)] disabled:cursor-not-allowed disabled:opacity-50"
                data-testid="settings-discard"
              >
                Verwerfen
              </button>
              <button
                type="button"
                onClick={handleSaveAll}
                disabled={updateCompany.isPending || !dirty || errorKeys.length > 0}
                className="rounded-[var(--radius)] bg-[#001a42] px-3 py-2 text-[13px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                data-testid="settings-save"
              >
                {updateCompany.isPending ? "Speichere…" : "Änderungen speichern"}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={leaving.status === "blocked"}
        title="Seite verlassen?"
        message="Du hast ungespeicherte Änderungen. Wenn du die Seite verlässt, gehen sie verloren."
        confirmLabel="Seite verlassen"
        cancelLabel="Bleiben"
        destructive
        onConfirm={() => leaving.status === "blocked" && leaving.proceed()}
        onCancel={() => leaving.status === "blocked" && leaving.reset()}
      />

      <ConfirmDialog
        open={discardOpen}
        title="Änderungen verwerfen?"
        message="Alles, was du seit dem letzten Speichern geändert hast, geht verloren."
        confirmLabel="Verwerfen"
        destructive
        onConfirm={handleDiscard}
        onCancel={() => setDiscardOpen(false)}
      />
    </div>
  );
}

/* ── Helper Components ── */

function Section({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white p-[var(--space-md)]">
      <div className="mb-4 flex items-center justify-between border-b border-[var(--color-border)] pb-2">
        <h2 className="text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-primary)]">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Field({
  label,
  type = "text",
  mono = false,
  value,
  onChange,
  placeholder,
  className,
  hint,
  error,
}: {
  label?: string;
  type?: string;
  mono?: boolean;
  value: string | number;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
  hint?: string;
  error?: string;
}) {
  const id = useId();
  const noteId = `${id}-note`;
  const base =
    "w-full rounded-[var(--radius)] border bg-white px-3 py-2 text-[14px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:ring-1 outline-none transition-colors";
  const tone = error
    ? "border-rose-500 focus:border-rose-500 focus:ring-rose-500"
    : "border-[var(--color-border)] focus:border-[#001a42] focus:ring-[#001a42]";

  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="mb-1 block text-[14px] font-semibold text-[var(--color-text-primary)]">
          {label}
        </label>
      )}
      <input
        id={id}
        type={type}
        aria-label={label ? undefined : placeholder}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? noteId : undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`${base} ${tone} ${mono ? "font-mono text-[12px]" : ""}`}
      />
      {(error || hint) && (
        <p id={noteId} className={`mt-1 text-[12px] ${error ? "text-rose-700" : "text-[var(--color-text-muted)]"}`}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
  className,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  className?: string;
}) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-[14px] font-semibold text-[var(--color-text-primary)]">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-[var(--radius)] border border-[var(--color-border)] bg-white px-3 py-2 text-[14px] text-[var(--color-text-primary)] focus:border-[#001a42] focus:ring-1 focus:ring-[#001a42] outline-none transition-colors"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="relative inline-flex cursor-pointer items-center">
      <input
        type="checkbox"
        role="switch"
        aria-label={label}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="peer sr-only"
      />
      <span
        className={`block h-5 w-8 rounded-full transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-[#001a42] peer-focus-visible:ring-offset-2 ${
          checked ? "bg-[#001a42]" : "bg-[var(--color-border)]"
        }`}
      />
      <span
        className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-3.5" : "translate-x-0"
        }`}
      />
    </label>
  );
}

function useCompanyUpdate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<CompanyForm>) =>
      api.put<Company>("/api/company", patch),
    onSuccess: (data: Company) => {
      qc.setQueryData(["company"], data);
    },
  });
}
