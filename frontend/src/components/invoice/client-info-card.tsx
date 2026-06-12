/**
 * @schema ClientInfoCard
 * @purpose Displays client billing information with avatar, name, address, and due date
 * @input {object} client - Customer object with name, email, address fields
 * @input {string} dueDate - Invoice due date string
 * @output Renders card with client avatar, company details, and due date
 * @tokens Uses: card-bg, card-border, card-radius, card-shadow, color-brand-text, color-text-*
 */
interface ClientInfoCardProps {
  client: {
    name?: string;
    email?: string;
    strasse?: string;
    plz?: string;
    ort?: string;
  } | null;
  dueDate?: string;
}

export function ClientInfoCard({ client, dueDate }: ClientInfoCardProps) {
  const displayName = client?.name || "Kein Kunde";
  const initials = displayName.charAt(0).toUpperCase();

  return (
    <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-[var(--card-radius)] shadow-[var(--card-shadow)] p-5">
      <div className="flex justify-between items-start mb-4 border-b border-[var(--color-border)] pb-3">
        <h3 className="text-base font-semibold text-[var(--color-text-primary)]">Rechnungsempfänger</h3>
        {dueDate && (
          <div className="text-right">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
              Fälligkeitsdatum
            </p>
            <p className="text-sm font-semibold text-[var(--color-text-primary)]">{dueDate}</p>
          </div>
        )}
      </div>

      <div className="flex items-start gap-4">
        {/* Avatar */}
        <div className="w-12 h-12 rounded-[var(--radius-lg)] bg-[var(--color-brand-surface)] flex items-center justify-center text-[var(--color-brand-text)] font-bold text-base shrink-0">
          {initials}
        </div>

        {/* Details */}
        <div>
          <p className="text-sm font-semibold text-[var(--color-text-primary)]">{displayName}</p>
          {(client?.strasse || client?.plz || client?.ort) && (
            <p className="text-sm text-[var(--color-text-muted)] mt-1 leading-relaxed">
              {client.strasse && <>{client.strasse}<br /></>}
              {client.plz} {client.ort}
            </p>
          )}
          {client?.email && (
            <a
              href={`mailto:${client.email}`}
              className="text-sm text-[var(--color-brand-text)] hover:underline mt-2 inline-block"
            >
              {client.email}
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
