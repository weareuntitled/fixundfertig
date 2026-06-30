/**
 * @schema TopBar
 * @purpose Apple-style top bar: glass effect, search, actions, user
 */
import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { useNotification } from "@/lib/use-notifications";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Search, Bell, HelpCircle, X, Building2 } from "lucide-react";

interface CompanyEntry { id: number; name: string }

interface TopBarProps {
  className?: string;
}

export function TopBar({ className = "" }: TopBarProps) {
  const { data: user } = useAuth();
  const { notifications, dismiss } = useNotification();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [coDropdownOpen, setCoDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const coDropdownRef = useRef<HTMLDivElement>(null);

  const { data: companies = [] } = useQuery({
    queryKey: ["companies"],
    queryFn: () => api.get<CompanyEntry[]>("/api/company/list"),
    staleTime: 60_000,
  });

  const switchCompany = (id: number) => {
    document.cookie = `ff_company=${id}; path=/; max-age=${60*60*24*365}`;
    window.location.reload();
  };

  // ponytail: read cookie once on mount, reload handles updates
  const companyIdFromCookie = (() => {
    const m = document.cookie.match(/ff_company=(\d+)/);
    return m ? parseInt(m[1]) : 0;
  })();
  const activeCompanyName = companies.find(c => c.id === companyIdFromCookie)?.name || companies[0]?.name;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
      if (coDropdownRef.current && !coDropdownRef.current.contains(e.target as Node)) {
        setCoDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header
      className={`h-14 sticky top-0 z-10 flex items-center justify-between gap-4 px-6 md:px-10 border-b border-[var(--color-border)] bg-white/72 backdrop-blur-xl ${className}`}
    >
      {/* Search */}
      <div className="flex-1 max-w-md">
        <div className="relative">
          <Search
            size={14}
            strokeWidth={2}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)] pointer-events-none"
          />
          <input
            type="text"
            placeholder="Suchen…"
            className="w-full h-9 rounded-[8px] border border-transparent bg-[var(--color-gray-50)] pl-9 pr-3 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] outline-none transition-all hover:bg-[var(--color-gray-100)] focus:bg-white focus:border-[var(--color-border-strong)] focus:shadow-[var(--shadow-focus)]"
          />
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-1">
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            aria-label="Benachrichtigungen"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="relative h-9 w-9 inline-flex items-center justify-center rounded-full text-[var(--color-text-secondary)] hover:bg-[var(--color-gray-50)] transition-colors"
          >
            <Bell size={16} strokeWidth={1.75} />
            {notifications.length > 0 && (
              <span className="absolute top-2 right-2 w-1.5 h-1.5 bg-[var(--color-red-500)] rounded-full" />
            )}
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 top-full mt-1 w-72 rounded-xl border border-[var(--color-border)] bg-white shadow-lg overflow-hidden">
              <div className="px-3 py-2 border-b border-[var(--color-border)]">
                <p className="text-[12px] font-semibold uppercase tracking-[0.05em] text-[var(--color-text-secondary)]">
                  Benachrichtigungen
                </p>
              </div>
              <div className="max-h-60 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="px-3 py-6 text-center text-[13px] text-[var(--color-text-muted)]">
                    Keine Benachrichtigungen
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      className="flex items-start gap-2 px-3 py-2.5 border-b border-[var(--color-border)] hover:bg-[var(--color-surface-bright)] transition-colors cursor-pointer"
                      onClick={() => dismiss(n.id)}
                    >
                      <div
                        className="mt-0.5 h-2 w-2 shrink-0 rounded-full"
                        style={{
                          backgroundColor:
                            n.type === "success" ? "#059669" : n.type === "error" ? "#dc2626" : "#6e6e73",
                        }}
                      />
                      <p className="text-[13px] text-[var(--color-text-primary)] flex-1 leading-snug">
                        {n.message}
                      </p>
                      <X size={12} className="text-[var(--color-text-muted)] mt-0.5 shrink-0" />
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <button
          type="button"
          aria-label="Hilfe"
          className="h-9 w-9 inline-flex items-center justify-center rounded-full text-[var(--color-text-secondary)] hover:bg-[var(--color-gray-50)] transition-colors"
        >
          <HelpCircle size={16} strokeWidth={1.75} />
        </button>

        {/* ponytail: company switcher — cookie-based, reloads on change */}
        {companies.length > 1 && (
          <div className="relative" ref={coDropdownRef}>
            <button
              type="button"
              onClick={() => setCoDropdownOpen(!coDropdownOpen)}
              className="h-8 inline-flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-white px-3 text-[12px] font-medium text-[var(--color-text-primary)] hover:bg-[var(--color-surface-container-high)] transition-colors"
            >
              <Building2 size={14} />
              {activeCompanyName}
            </button>
            {coDropdownOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 rounded-xl border border-[var(--color-border)] bg-white shadow-lg overflow-hidden z-50">
                {companies.map(c => (
                  <button
                    key={c.id}
                    onClick={() => switchCompany(c.id)}
                    className="w-full text-left px-3 py-2 text-[13px] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-container-high)] transition-colors"
                  >
                    {c.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="h-8 w-8 ml-1.5 rounded-full bg-gradient-to-br from-[var(--color-blue-100)] to-[var(--color-blue-200)] flex items-center justify-center text-[12px] font-semibold text-[var(--color-blue-700)] cursor-pointer ring-2 ring-white">
          {user?.email?.charAt(0).toUpperCase() || "?"}
        </div>
      </div>
    </header>
  );
}
