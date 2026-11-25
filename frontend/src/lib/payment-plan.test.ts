import { describe, expect, it } from "vitest";
import { installmentAmounts, planPercentTotal, percentLabel, roundCents } from "./payment-plan";

/**
 * Die Ratenbeträge des Zahlungsplans. Dieselben Fälle stehen in
 * tests/test_payment_plan_rounding.py: Anzeige und Backend müssen denselben Cent
 * zeigen (kaufmännisch auf Cent runden, half-up).
 */
describe("roundCents", () => {
  it("rounds to cents, half up", () => {
    expect(roundCents(0.125)).toBe(0.13);
    expect(roundCents(2.345)).toBe(2.35);
    expect(roundCents(5.025)).toBe(5.03);
    expect(roundCents(50.005)).toBe(50.01);
    expect(roundCents(1.005)).toBe(1.01);
  });

  it("keeps amounts that are already cents", () => {
    expect(roundCents(2380)).toBe(2380);
    expect(roundCents(33.33)).toBe(33.33);
    expect(roundCents(0)).toBe(0);
  });

  it("rounds down below the half", () => {
    expect(roundCents(0.124)).toBe(0.12);
    expect(roundCents(50.004)).toBe(50);
  });

  it("rounds negative amounts away from zero", () => {
    expect(roundCents(-0.125)).toBe(-0.13);
  });
});

describe("installmentAmounts", () => {
  it("computes the amount of every installment from the gross total", () => {
    expect(installmentAmounts(4760, [50, 50])).toEqual([2380, 2380]);
    expect(installmentAmounts(4000, [50, 25, 25])).toEqual([2000, 1000, 1000]);
  });

  it("rounds the installments the same way as the backend", () => {
    expect(installmentAmounts(100.01, [50])).toEqual([50.01]);
    expect(installmentAmounts(10.05, [50])).toEqual([5.03]);
    expect(installmentAmounts(0.125, [100])).toEqual([0.13]);
  });

  it("gives the rounding rest to the last installment of a 100 % plan", () => {
    const amounts = installmentAmounts(1190, [50, 33.33, 16.67]);

    expect(amounts).toEqual([595, 396.63, 198.37]);
    expect(Math.round(amounts.reduce((sum, a) => sum + a, 0) * 100) / 100).toBe(1190);
  });
});

describe("percent helpers", () => {
  it("sums the percentages of a plan", () => {
    expect(planPercentTotal([{ percent: 50, label: "" }, { percent: 50, label: "" }])).toBe(100);
    expect(planPercentTotal([{ percent: 33.33, label: "" }, { percent: 33.33, label: "" }])).toBe(66.66);
  });

  it("labels a percentage in German", () => {
    expect(percentLabel(50)).toBe("50 %");
    expect(percentLabel(33.33)).toBe("33,33 %");
  });
});
