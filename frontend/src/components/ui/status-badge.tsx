/**
 * @schema StatusBadge
 * @purpose Colored badge indicating invoice status with dot indicator
 * @input {string} status - Invoice or quote status value (incl. derived EXPIRED for quotes)
 * @input {"sm" | "md"} size - Badge size variant
 * @output Renders pill-shaped badge with colored dot and label text
 * @tokens Uses: color-status-*, color-text-on-brand
 */
type Status =
  | "DRAFT"
  | "OPEN"
  | "SENT"
  | "PAID"
  | "FINALIZED"
  | "CANCELLED"
  | "ACCEPTED"
  | "REJECTED"
  | "EXPIRED";

const STATUS_CONFIG: Record<
  Status,
  { label: string; dot: string; bg: string; text: string }
> = {
  DRAFT: {
    label: "Entwurf",
    dot: "bg-[var(--color-status-draft)]",
    bg: "bg-[var(--color-status-draft-bg)]",
    text: "text-[var(--color-status-draft-text)]",
  },
  OPEN: {
    label: "Offen",
    dot: "bg-[var(--color-status-open)]",
    bg: "bg-[var(--color-status-open-bg)]",
    text: "text-[var(--color-status-open-text)]",
  },
  SENT: {
    label: "Gesendet",
    dot: "bg-[var(--color-status-sent)]",
    bg: "bg-[var(--color-status-sent-bg)]",
    text: "text-[var(--color-status-sent-text)]",
  },
  PAID: {
    label: "Bezahlt",
    dot: "bg-[var(--color-status-paid)]",
    bg: "bg-[var(--color-status-paid-bg)]",
    text: "text-[var(--color-status-paid-text)]",
  },
  FINALIZED: {
    label: "Finalisiert",
    dot: "bg-[var(--color-status-open)]",
    bg: "bg-[var(--color-status-open-bg)]",
    text: "text-[var(--color-status-open-text)]",
  },
  CANCELLED: {
    label: "Storniert",
    dot: "bg-[var(--color-status-cancelled)]",
    bg: "bg-[var(--color-status-cancelled-bg)]",
    text: "text-[var(--color-status-cancelled-text)]",
  },
  ACCEPTED: {
    label: "Angenommen",
    dot: "bg-[var(--color-status-paid)]",
    bg: "bg-[var(--color-status-paid-bg)]",
    text: "text-[var(--color-status-paid-text)]",
  },
  REJECTED: {
    label: "Abgelehnt",
    dot: "bg-[var(--color-status-cancelled)]",
    bg: "bg-[var(--color-status-cancelled-bg)]",
    text: "text-[var(--color-status-cancelled-text)]",
  },
  EXPIRED: {
    label: "Abgelaufen",
    dot: "bg-[var(--color-status-expired)]",
    bg: "bg-[var(--color-status-expired-bg)]",
    text: "text-[var(--color-status-expired-text)]",
  },
};

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const c = STATUS_CONFIG[status as Status] || STATUS_CONFIG.DRAFT;
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold tracking-wide uppercase ${c.bg} ${c.text} ${sizeClasses}`}
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}

export const STATUS_LABELS: Record<string, string> = {
  ALL: "Alle",
  DRAFT: "Entwurf",
  OPEN: "Offen",
  SENT: "Gesendet",
  PAID: "Bezahlt",
  FINALIZED: "Finalisiert",
  CANCELLED: "Storniert",
  ACCEPTED: "Angenommen",
  REJECTED: "Abgelehnt",
  EXPIRED: "Abgelaufen",
};
