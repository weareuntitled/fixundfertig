import type { PaymentInstallment } from "./schemas/invoice";

/**
 * Kaufmännisch auf Cent runden (half-up): 0,125 → 0,13; 2,345 → 2,35.
 *
 * Spiegelt `round_cents` in app/services/payment_plan.py: gerundet wird die
 * geschriebene Zahl (kürzeste Dezimaldarstellung), nicht ihre Binär-Annäherung.
 * So zeigen Anzeige, Backend und PDF denselben Cent.
 */
export function roundCents(value: number): number {
  if (!Number.isFinite(value)) return 0;
  const negative = value < 0;
  const abs = Math.abs(value);
  const shortest = abs.toString();
  // Exponentnotation (1e-7) in eine Dezimaldarstellung bringen.
  const text = shortest.includes("e") ? abs.toFixed(20) : shortest;
  const [wholeRaw, fractionRaw = ""] = text.split(".");
  const fraction = fractionRaw.padEnd(3, "0");
  // Die dritte Nachkommastelle entscheidet: .5 geht immer nach oben.
  const third = fraction.charCodeAt(2) - 48;
  const cents = Math.round(Number(wholeRaw) * 100) + Number(fraction.slice(0, 2));
  const rounded = third >= 5 ? cents + 1 : cents;
  return (negative ? -rounded : rounded) / 100;
}

/**
 * Gross amount per installment, rounded to cents. Mirrors `installment_amounts` in
 * app/services/payment_plan.py: at 100 % the last installment takes the rounding rest.
 */
export function installmentAmounts(gross: number, percents: number[]): number[] {
  const amounts = percents.map((p) => roundCents((gross * p) / 100));
  const total = percents.reduce((sum, p) => sum + p, 0);
  if (amounts.length > 0 && Math.abs(total - 100) < 1e-6) {
    const rest = amounts.slice(0, -1).reduce((sum, a) => sum + a, 0);
    amounts[amounts.length - 1] = roundCents(gross - rest);
  }
  return amounts;
}

export function planPercentTotal(plan: PaymentInstallment[]): number {
  return Math.round(plan.reduce((sum, rate) => sum + (Number(rate.percent) || 0), 0) * 100) / 100;
}

/** "50 %" / "33,33 %" */
export function percentLabel(percent: number): string {
  return `${percent.toLocaleString("de-DE", { maximumFractionDigits: 2 })} %`;
}
