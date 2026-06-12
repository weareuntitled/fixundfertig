/**
 * @schema StatusBadge
 * @purpose Colored badge indicating invoice status with dot indicator
 * @input {string} status - Invoice status value
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
  | "CANCELLED";

const STATUS_CONFIG: Record<
  Status,
  { label: string; dot: string; bg: string; text: string }
> = {
  DRAFT: {
    label: "Entwurf",
    dot: "bg-[var(--color-status-draft)]",
    bg: "bg-[var(--color-status-draft-bg)]",
    text: "text-[var(--color-status-draft)]",
  },
  OPEN: {
    label: "Offen",
    dot: "bg-[var(--color-status-open)]",
    bg: "bg-[var(--color-status-open-bg)]",
    text: "text-[var(--color-status-open)]",
  },
  SENT: {
    label: "Gesendet",
    dot: "bg-[var(--color-status-sent)]",
    bg: "bg-[var(--color-status-sent-bg)]",
    text: "text-[var(--color-status-sent)]",
  },
  PAID: {
    label: "Bezahlt",
    dot: "bg-[var(--color-status-paid)]",
    bg: "bg-[var(--color-status-paid-bg)]",
    text: "text-[var(--color-status-paid)]",
  },
  FINALIZED: {
    label: "Finalisiert",
    dot: "bg-[var(--color-status-open)]",
    bg: "bg-[var(--color-status-open-bg)]",
    text: "text-[var(--color-status-open)]",
  },
  CANCELLED: {
    label: "Storniert",
    dot: "bg-[var(--color-status-cancelled)]",
    bg: "bg-[var(--color-status-cancelled-bg)]",
    text: "text-[var(--color-status-cancelled)]",
  },
};

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const c = STATUS_CONFIG[status as Status] || STATUS_CONFIG.DRAFT;
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold tracking-wide uppercase ${c.bg} ${c.text} ${sizeClasses}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
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
};
