import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useChangePassword } from "@/lib/use-account";
import { ArrowLeft, Save } from "lucide-react";

export const Route = createFileRoute("/_app/settings/account")({
  component: AccountSettingsPage,
});

function AccountSettingsPage() {
  const { data: user } = useAuth();
  const changePassword = useChangePassword();
  const [current, setCurrent] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (newPw !== confirm) return;
    changePassword.mutate({ current_password: current, new_password: newPw });
  }

  const mismatch = confirm.length > 0 && newPw !== confirm;
  const tooShort = newPw.length > 0 && newPw.length < 6;

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <Link
          to="/settings"
          className="inline-flex items-center gap-1 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-heading)]"
          data-testid="back-to-hub"
        >
          <ArrowLeft className="h-4 w-4" /> Zurück
        </Link>
        <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-heading)]">Account</h1>
      </header>

      <section className="rounded-xl border border-[var(--color-border)] bg-white p-4">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Angemeldet als</h2>
        <p className="text-sm text-[var(--color-text-heading)]" data-testid="account-email">{user?.email ?? "—"}</p>
      </section>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-[var(--color-border)] bg-white p-4" data-testid="password-form">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">Passwort ändern</h2>

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-[var(--color-text-primary)]">Aktuelles Passwort</span>
          <input
            type="password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            data-testid="current-password"
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-[var(--color-text-primary)]">Neues Passwort (min. 6 Zeichen)</span>
          <input
            type="password"
            required
            minLength={6}
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
            className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            data-testid="new-password"
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-[var(--color-text-primary)]">Neues Passwort bestätigen</span>
          <input
            type="password"
            required
            minLength={6}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="w-full rounded-md border border-[var(--color-border-strong)] px-3 py-2 text-sm"
            data-testid="confirm-password"
          />
        </label>

        {mismatch && (
          <p className="text-xs text-rose-600" data-testid="password-mismatch">Passwörter stimmen nicht überein.</p>
        )}
        {tooShort && (
          <p className="text-xs text-rose-600">Neues Passwort zu kurz.</p>
        )}

        {changePassword.isError && (
          <p className="text-xs text-rose-600" data-testid="password-error">
            {changePassword.error instanceof Error ? changePassword.error.message : "Fehler beim Ändern."}
          </p>
        )}
        {changePassword.isSuccess && (
          <p className="text-xs text-emerald-600" data-testid="password-saved">Passwort geändert.</p>
        )}

        <div className="flex justify-end border-t border-[var(--color-border-subtle)] pt-3">
          <button
            type="submit"
            disabled={changePassword.isPending || !current || !newPw || mismatch || tooShort}
            className="inline-flex items-center gap-1 rounded-md bg-[var(--color-text-heading)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            data-testid="password-save"
          >
            <Save className="h-4 w-4" />
            {changePassword.isPending ? "Speichere…" : "Passwort ändern"}
          </button>
        </div>
      </form>
    </div>
  );
}
