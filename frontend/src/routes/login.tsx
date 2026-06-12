import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useAuth, useLogin, isUnauthorizedError } from "@/lib/auth";
import { LogIn, Sparkles } from "lucide-react";

export const Route = createFileRoute("/login")({
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { data: user, isLoading } = useAuth();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && user) {
      void navigate({ to: "/" });
    }
  }, [user, isLoading, navigate]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    login.mutate(
      { email, password },
      {
        onSuccess: () => void navigate({ to: "/" }),
        onError: (err) => {
          if (isUnauthorizedError(err)) {
            setError("Ungültige Zugangsdaten");
          } else {
            setError(err instanceof Error ? err.message : "Login fehlgeschlagen");
          }
        },
      }
    );
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--color-background)] px-4 py-12">
      {/* Apple-style ambient background */}
      <div
        className="absolute inset-0 opacity-60"
        style={{
          backgroundImage:
            "radial-gradient(at 20% 20%, rgba(0,122,255,0.08) 0px, transparent 50%), radial-gradient(at 80% 0%, rgba(175,82,222,0.06) 0px, transparent 50%), radial-gradient(at 0% 100%, rgba(52,199,89,0.05) 0px, transparent 50%)",
        }}
      />

      <div className="relative w-full max-w-[400px]">
        {/* Brand */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-[14px] bg-gradient-to-br from-[#0a0a0a] to-[#3a3a3a] shadow-lg shadow-black/10">
            <Sparkles size={26} className="text-white" strokeWidth={2.5} />
          </div>
          <h1 className="text-[28px] font-semibold tracking-tight text-[var(--color-text-heading)]">
            FixundFertig
          </h1>
          <p className="mt-1.5 text-[15px] text-[var(--color-text-secondary)]">
            Melde dich an, um fortzufahren
          </p>
        </div>

        {/* Form Card */}
        <div className="rounded-[16px] border border-[var(--color-border)] bg-white/80 backdrop-blur-xl p-7 shadow-[0_10px_40px_rgba(0,0,0,0.04)]">
          <form onSubmit={onSubmit}>
            <div className="space-y-4">
              <div>
                <label htmlFor="email" className="mb-1.5 block text-[13px] font-medium text-[var(--color-text-primary)]">
                  E-Mail
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full h-10 rounded-[8px] border border-[var(--color-border-strong)] bg-white px-3.5 text-[14px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-placeholder)] outline-none transition-all focus:border-[var(--color-border-focus)] focus:shadow-[0_0_0_3px_rgba(0,122,255,0.12)]"
                  placeholder="name@firma.de"
                />
              </div>

              <div>
                <label htmlFor="password" className="mb-1.5 block text-[13px] font-medium text-[var(--color-text-primary)]">
                  Passwort
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full h-10 rounded-[8px] border border-[var(--color-border-strong)] bg-white px-3.5 text-[14px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-placeholder)] outline-none transition-all focus:border-[var(--color-border-focus)] focus:shadow-[0_0_0_3px_rgba(0,122,255,0.12)]"
                  placeholder="Dein Passwort"
                />
              </div>
            </div>

            {error && (
              <div
                className="mt-4 rounded-[8px] border border-[var(--color-red-100)] bg-[var(--color-red-50)] px-3 py-2.5 text-[13px] text-[var(--color-red-600)]"
                role="alert"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={login.isPending}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-[8px] bg-[var(--color-text-heading)] h-10 px-4 text-[14px] font-medium text-white shadow-sm transition-all hover:bg-[var(--color-gray-700)] active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <LogIn size={15} strokeWidth={2.25} />
              {login.isPending ? "Wird angemeldet…" : "Anmelden"}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-[12px] text-[var(--color-text-tertiary)]">
          Nur für autorisierte Benutzer
        </p>
      </div>
    </div>
  );
}
