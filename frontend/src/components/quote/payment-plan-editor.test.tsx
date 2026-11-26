import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PaymentPlanEditor } from "./payment-plan-editor";

describe("PaymentPlanEditor", () => {
  it("names a wrong percent right at the field", () => {
    render(<PaymentPlanEditor value={[{ percent: 0, label: "bei Auftrag" }]} gross={1190} onChange={() => {}} />);
    const percent = screen.getByLabelText("Prozent Rate 1");
    expect(percent).toHaveAttribute("aria-invalid", "true");
    expect(percent).toHaveAccessibleDescription("Prozent größer 0 eintragen");
  });

  it("leaves a valid percent without error text", () => {
    render(<PaymentPlanEditor value={[{ percent: 100, label: "bei Auftrag" }]} gross={1190} onChange={() => {}} />);
    expect(screen.getByLabelText("Prozent Rate 1")).not.toHaveAccessibleDescription();
  });
});
