import { createFileRoute } from "@tanstack/react-router";
import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import { useAuth } from "@/lib/auth";
import { useInvoices } from "@/lib/use-invoices";
import { useCustomers } from "@/lib/use-customers";
import {
  TrendingUp,
  Clock,
  CheckCircle2,
  FileText,
  ArrowUpRight,
  Plus,
  Users,
} from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";

export const Route = createFileRoute("/_app/")({
  component: DashboardPage,
});

const eur = (n: number) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

function DashboardPage() {
  const { data: user } = useAuth();
  const { data: invoices } = useInvoices();
  const { data: customers } = useCustomers();

  const stats = useMemo(() => {
    if (!invoices) {
      return { open: 0, paid: 0, draft: 0, total: 0, openSum: 0, paidSum: 0 };
    }
    let open = 0;
    let paid = 0;
    let draft = 0;
    let openSum = 0;
    let paidSum = 0;
    for (const inv of invoices) {
      if (inv.status === "OPEN" || inv.status === "SENT") {
        open += 1;
        openSum += inv.total_brutto;
      } else if (inv.status === "PAID") {
        paid += 1;
        paidSum += inv.total_brutto;
      } else if (inv.status === "DRAFT") {
        draft += 1;
      }
    }
    return { open, paid, draft, total: invoices.length, openSum, paidSum };
  }, [invoices]);

  const greeting = (() => {
    const hour = new Date().getHours();
    if (hour < 12) return "Guten Morgen";
    if (hour < 18) return "Hallo";
    return "Guten Abend";
  })();

  return (
    <div className="animate-fade-in space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-[34px] font-semibold tracking-tight text-[var(--color-text-heading)] leading-[1.1]">
          {greeting}, {user?.first_name || user?.email?.split("@")[0] || "!"}
        </h1>
        <p className="mt-1.5 text-[15px] text-[var(--color-text-secondary)]">
          Hier ist dein Überblick für heute.
        </p>
      </div>

      {/* KPI Cards — Apple-style with subtle gradient hint */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard
          icon={Clock}
          label="Offen"
          value={String(stats.open)}
          hint={eur(stats.openSum)}
          accent="blue"
        />
        <KpiCard
          icon={CheckCircle2}
          label="Bezahlt"
          value={String(stats.paid)}
          hint={eur(stats.paidSum)}
          accent="green"
        />
        <KpiCard
          icon={FileText}
          label="Entwürfe"
          value={String(stats.draft)}
          hint="Noch nicht gesendet"
          accent="gray"
        />
        <KpiCard
          icon={TrendingUp}
          label="Gesamt"
          value={String(stats.total)}
          hint={`${customers?.length ?? 0} Kunden`}
          accent="violet"
        />
      </div>

      {/* Quick Actions + Recent Invoices */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Recent Invoices */}
        <section className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-[18px] font-semibold tracking-tight text-[var(--color-text-heading)]">
              Letzte Rechnungen
            </h2>
            <Link
              to="/invoices"
              className="inline-flex items-center gap-1 text-[13px] font-medium text-[var(--color-blue-500)] hover:text-[var(--color-blue-600)] transition-colors"
            >
              Alle ansehen <ArrowUpRight size={13} />
            </Link>
          </div>
          <div className="rounded-[12px] border border-[var(--color-border)] bg-white overflow-hidden">
            <table className="w-full text-[14px]">
              <thead>
                <tr className="border-b border-[var(--color-border)] bg-[var(--color-gray-25)]">
                  <th className="px-5 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
                    Nr.
                  </th>
                  <th className="px-5 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
                    Datum
                  </th>
                  <th className="px-5 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
                    Titel
                  </th>
                  <th className="px-5 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
                    Betrag
                  </th>
                  <th className="px-5 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {invoices?.slice(0, 8).map((inv) => (
                  <tr
                    key={inv.id}
                    className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-gray-25)] transition-colors group"
                  >
                    <td className="px-5 py-3">
                      <Link
                        to="/invoices/$id"
                        params={{ id: String(inv.id) }}
                        className="font-mono text-[12.5px] font-medium text-[var(--color-text-heading)] hover:text-[var(--color-blue-500)] transition-colors"
                      >
                        {inv.nr || `#${inv.id}`}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-[13px] text-[var(--color-text-secondary)]">
                      {inv.date || "—"}
                    </td>
                    <td className="px-5 py-3 font-medium text-[var(--color-text-primary)]">
                      {inv.title || "Rechnung"}
                    </td>
                    <td className="px-5 py-3 text-right font-mono text-[13.5px] tabular-nums font-semibold text-[var(--color-text-primary)]">
                      {eur(inv.total_brutto)}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <StatusBadge status={inv.status} />
                    </td>
                  </tr>
                ))}
                {invoices?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-5 py-16 text-center">
                      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-gray-50)]">
                        <FileText size={20} className="text-[var(--color-text-tertiary)]" />
                      </div>
                      <p className="text-[14px] font-medium text-[var(--color-text-primary)]">
                        Noch keine Rechnungen
                      </p>
                      <Link
                        to="/invoices/new"
                        className="mt-2 inline-flex items-center gap-1 text-[13px] font-medium text-[var(--color-blue-500)] hover:text-[var(--color-blue-600)] transition-colors"
                      >
                        <Plus size={13} /> Erste Rechnung erstellen
                      </Link>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Quick Actions */}
        <section>
          <h2 className="mb-3 text-[18px] font-semibold tracking-tight text-[var(--color-text-heading)]">
            Schnellzugriff
          </h2>
          <div className="space-y-2">
            <QuickAction
              to="/invoices/new"
              icon={FileText}
              title="Neue Rechnung"
              subtitle="Rechnung erstellen und versenden"
            />
            <QuickAction
              to="/customers"
              icon={Users}
              title="Kunden"
              subtitle={`${customers?.length ?? 0} Kunden in deinem Adressbuch`}
            />
            <QuickAction
              to="/documents"
              icon={FileText}
              title="Belege"
              subtitle="Dokumente und Belege verwalten"
            />
          </div>
        </section>
      </div>
    </div>
  );
}

interface KpiCardProps {
  icon: typeof Clock;
  label: string;
  value: string;
  hint?: string;
  accent: "blue" | "green" | "gray" | "violet";
}

const accentMap = {
  blue: { bg: "bg-[var(--color-blue-50)]", text: "text-[var(--color-blue-500)]" },
  green: { bg: "bg-[var(--color-green-50)]", text: "text-[var(--color-green-600)]" },
  gray: { bg: "bg-[var(--color-gray-100)]", text: "text-[var(--color-gray-700)]" },
  violet: { bg: "bg-[var(--color-violet-50)]", text: "text-[var(--color-violet-500)]" },
} as const;

function KpiCard({ icon: Icon, label, value, hint, accent }: KpiCardProps) {
  const a = accentMap[accent];
  return (
    <div className="rounded-[12px] border border-[var(--color-border)] bg-white p-5 transition-all hover:border-[var(--color-border-strong)] hover:shadow-[0_4px_16px_rgba(0,0,0,0.04)]">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[12px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">
            {label}
          </p>
          <p className="mt-2 font-mono text-[32px] font-semibold tracking-tight tabular-nums text-[var(--color-text-heading)]">
            {value}
          </p>
          {hint && (
            <p className="mt-0.5 text-[12.5px] text-[var(--color-text-tertiary)]">
              {hint}
            </p>
          )}
        </div>
        <div className={`flex h-9 w-9 items-center justify-center rounded-[8px] ${a.bg}`}>
          <Icon size={16} className={a.text} strokeWidth={2} />
        </div>
      </div>
    </div>
  );
}

interface QuickActionProps {
  to: string;
  icon: typeof FileText;
  title: string;
  subtitle: string;
}

function QuickAction({ to, icon: Icon, title, subtitle }: QuickActionProps) {
  return (
    <Link
      to={to}
      className="group flex items-center gap-3 rounded-[10px] border border-[var(--color-border)] bg-white p-3.5 transition-all hover:border-[var(--color-border-strong)] hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-[var(--color-gray-50)] text-[var(--color-text-secondary)] group-hover:bg-[var(--color-blue-50)] group-hover:text-[var(--color-blue-500)] transition-colors">
        <Icon size={16} strokeWidth={1.75} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[14px] font-medium text-[var(--color-text-primary)]">
          {title}
        </div>
        <div className="truncate text-[12.5px] text-[var(--color-text-tertiary)]">
          {subtitle}
        </div>
      </div>
      <ArrowUpRight
        size={14}
        className="text-[var(--color-text-tertiary)] transition-colors group-hover:text-[var(--color-blue-500)]"
      />
    </Link>
  );
}
