/**
 * @schema QuoteUI
 * @purpose Gemeinsame Styles und Formate der Angebots-Komponenten (Zahlungsplan, Angebotsseite).
 *   Vorher waren INPUT, ICON_BUTTON, SECONDARY_BUTTON und der Euro-Formatter in drei Dateien kopiert.
 * @output Style-Konstanten INPUT, ICON_BUTTON, SECONDARY_BUTTON, PRIMARY_BUTTON und die Formate
 *   `eur` (Betrag) und `settlementLabel` (Abrechnungsstand)
 */
import type { QuoteSettlement } from "@/lib/schemas/invoice";

/** Textfeld der Angebots-Formulare (Mindesthöhe 44 px für Touch). */
export const INPUT =
  "w-full min-h-[44px] bg-white border border-[var(--color-border)] rounded-[var(--radius-lg)] px-[var(--space-sm)] py-2 text-[14px] text-[var(--color-text-primary)] outline-none focus:border-[#001a42] focus:ring-1 focus:ring-[#001a42]";

/** Icon-Knopf mit 44-px-Touchziel. */
export const ICON_BUTTON =
  "inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-[var(--radius)] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-container-low)] disabled:opacity-30";

/** Sekundärer Knopf: weiß, gerahmt, 44 px hoch. */
export const SECONDARY_BUTTON =
  "inline-flex min-h-[44px] items-center gap-1.5 rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-white px-[var(--space-md)] text-[14px] font-semibold text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-container-low)] disabled:cursor-not-allowed disabled:opacity-50";

/** Primärknopf: der nächste sinnvolle Schritt. Es gibt genau einen je Status. */
export const PRIMARY_BUTTON =
  "inline-flex min-h-[44px] items-center gap-1.5 rounded-[var(--radius-lg)] bg-[#001a42] px-[var(--space-md)] text-[14px] font-semibold text-white transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50";

/** Betrag in Euro, deutsches Format: 1.234,56 € */
export const eur = (value: number): string =>
  `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;

/**
 * Der Abrechnungsstand als Text: „abgerechnet 714,00 € von 1.785,00 € · offen 1.071,00 €“.
 * Ohne Rechnung steht „noch nichts abgerechnet“.
 */
export function settlementLabel(settlement: QuoteSettlement | null | undefined): string {
  if (!settlement) return "noch nichts abgerechnet";
  if (settlement.billed_count === 0) return "noch nichts abgerechnet";
  return `abgerechnet ${eur(settlement.billed_brutto)} von ${eur(settlement.total_brutto)} · offen ${eur(settlement.open_brutto)}`;
}

/** Wie viel vom Angebot ist abgerechnet, in Prozent (0–100). */
export function settlementPercent(settlement: QuoteSettlement | null | undefined): number {
  if (!settlement || settlement.total_brutto <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((settlement.billed_brutto / settlement.total_brutto) * 100)));
}
