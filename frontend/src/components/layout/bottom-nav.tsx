/**
 * @schema BottomNav
 * @purpose Mobile bottom navigation
 */
import { Link } from "@tanstack/react-router";
import { Home, FileText, Users, BarChart3, Settings } from "lucide-react";

interface BottomNavProps {
  className?: string;
}

const ITEMS = [
  { to: "/", label: "Home", icon: Home },
  { to: "/invoices", label: "Rechnungen", icon: FileText },
  { to: "/customers", label: "Kunden", icon: Users },
  { to: "/documents", label: "Belege", icon: BarChart3 },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

export function BottomNav({ className = "" }: BottomNavProps) {
  return (
    <nav
      className={`fixed bottom-0 left-0 right-0 z-30 flex items-center justify-around border-t border-[var(--color-border)] bg-white/85 backdrop-blur-xl px-2 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] ${className}`}
    >
      {ITEMS.map(({ to, label, icon: Icon }) => (
        <Link
          key={to}
          to={to}
          className="flex flex-col items-center gap-0.5 rounded-[8px] px-3 py-1.5 text-[var(--color-text-secondary)] [&.active]:text-[var(--color-text-heading)] transition-colors"
        >
          <Icon size={20} strokeWidth={1.75} />
          <span className="text-[10px] font-medium">{label}</span>
        </Link>
      ))}
    </nav>
  );
}
