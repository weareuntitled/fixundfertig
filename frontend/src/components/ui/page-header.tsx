/**
 * @schema PageHeader
 * @purpose Consistent page header matching Lumina Ledger HTML: back link, heading, subtitle, actions
 */
import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  backTo?: string;
  backLabel?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, backTo, backLabel = "Zurück", actions }: PageHeaderProps) {
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between mb-[var(--space-xl)] gap-4">
      <div>
        {backTo && (
          <Link
            to={backTo}
            className="inline-flex items-center gap-1 text-[14px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-heading)] transition-colors mb-2"
          >
            <ArrowLeft size={14} />
            {backLabel}
          </Link>
        )}
        <h2 className="text-[24px] md:text-[32px] font-semibold tracking-[-0.01em] text-[var(--color-text-heading)] leading-tight">
          {title}
        </h2>
        {subtitle && (
          <p className="text-[14px] text-[var(--color-text-secondary)] mt-1">
            {subtitle}
          </p>
        )}
      </div>
      {actions && <div className="flex items-center gap-3 flex-wrap">{actions}</div>}
    </div>
  );
}
