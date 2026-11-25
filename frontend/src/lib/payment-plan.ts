import type { PaymentInstallment } from "./schemas/invoice";

/**
 * Gross amount per installment, rounded to cents. Mirrors `installment_amounts` in
 * app/services/payment_plan.py: at 100 % the last installment takes the rounding rest.
 */
export function installmentAmounts(gross: number, percents: number[]): number[] {
  const amounts = percents.map((p) => Math.round(gross * p) / 100);
  const total = percents.reduce((sum, p) => sum + p, 0);
  if (amounts.length > 0 && Math.abs(total - 100) < 1e-6) {
    const rest = amounts.slice(0, -1).reduce((sum, a) => sum + a, 0);
    amounts[amounts.length - 1] = Math.round((gross - rest) * 100) / 100;
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
