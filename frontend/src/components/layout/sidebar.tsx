/**
 * @schema Sidebar
 * @purpose Refined Apple-style navigation rail
 */
import { Link } from "@tanstack/react-router";
import { navItems } from "@/lib/nav-items";
import { useAuth, useLogout } from "@/lib/auth";
import { LogOut, Sparkles } from "lucide-react";

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className = "" }: SidebarProps) {
  const { data: user } = useAuth();
  const logout = useLogout();

  return (
    <nav
      className={`w-[260px] h-screen fixed left-0 top-0 z-20 flex flex-col border-r border-[var(--color-border)] bg-white/80 backdrop-blur-xl ${className}`}
    >
      {/* Brand */}
      <Link to="/" className="px-5 pt-5 pb-3 flex items-center gap-2.5 group">
        <div className="w-7 h-7 rounded-[7px] bg-gradient-to-br from-[#0a0a0a] to-[#3a3a3a] flex items-center justify-center shadow-sm">
          <Sparkles size={15} className="text-white" strokeWidth={2.5} />
        </div>
        <div className="leading-tight">
          <h1 className="text-[15px] font-semibold tracking-tight text-[var(--color-text-heading)]">
            FixundFertig
          </h1>
          <p className="text-[10px] font-medium text-[var(--color-text-tertiary)] tracking-wide uppercase">
            Invoicing
          </p>
        </div>
      </Link>

      {/* New Invoice Button */}
      <div className="px-4 pb-3">
        <Link
          to="/invoices/new"
          className="w-full inline-flex items-center justify-center gap-1.5 rounded-[8px] bg-[var(--color-text-heading)] py-2 px-3 text-[13px] font-medium text-white shadow-sm transition-all hover:bg-[var(--color-gray-700)] active:scale-[0.98]"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Neue Rechnung
        </Link>
      </div>

      {/* Navigation */}
      <div className="flex-1 px-3 space-y-0.5 overflow-y-auto">
        <p className="px-2.5 pt-2 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
          Navigation
        </p>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.id}
              to={item.to}
              className="group flex items-center gap-2.5 rounded-[8px] px-2.5 py-2 text-[13px] font-medium text-[var(--color-text-secondary)] transition-all hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text-heading)] [&.active]:bg-[var(--color-gray-100)] [&.active]:text-[var(--color-text-heading)] [&.active]:font-semibold"
              activeProps={{ className: "" }}
            >
              <Icon size={16} strokeWidth={1.75} className="shrink-0 opacity-70 group-[.active]:opacity-100 group-hover:opacity-100 transition-opacity" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>

      {/* User Footer */}
      <div className="border-t border-[var(--color-border)] p-3">
        <div className="flex items-center gap-2.5 px-1.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[var(--color-blue-100)] to-[var(--color-blue-200)] text-[12px] font-semibold text-[var(--color-blue-700)]">
            {user?.email?.charAt(0).toUpperCase() || "?"}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[12.5px] font-medium text-[var(--color-text-primary)]">
              {user?.first_name || user?.email || "User"}
            </div>
            <div className="truncate text-[10.5px] text-[var(--color-text-tertiary)]">
              {user?.email || "—"}
            </div>
          </div>
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="rounded-full p-1.5 text-[var(--color-text-tertiary)] hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text-secondary)] transition-colors"
            title="Abmelden"
          >
            <LogOut size={13} strokeWidth={1.75} />
          </button>
        </div>
      </div>
    </nav>
  );
}
