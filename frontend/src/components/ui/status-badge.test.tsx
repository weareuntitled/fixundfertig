import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge, STATUS_LABELS } from "./status-badge";

/**
 * Eine Rechnung gilt als gestellt, sobald sie weder Entwurf noch storniert ist.
 * Für diesen Zustand gibt es genau ein Wort in der Oberfläche.
 */
describe("StatusBadge", () => {
  it("calls an issued invoice 'Gestellt'", () => {
    render(<StatusBadge status="OPEN" />);
    expect(screen.getByText("Gestellt")).toBeInTheDocument();
    expect(screen.queryByText("Offen")).toBeNull();
  });

  it("calls a finalized invoice 'Gestellt' too", () => {
    render(<StatusBadge status="FINALIZED" />);
    expect(screen.getByText("Gestellt")).toBeInTheDocument();
    expect(screen.queryByText("Finalisiert")).toBeNull();
  });

  it("uses the same word in the labels of the status lists", () => {
    expect(STATUS_LABELS.OPEN).toBe("Gestellt");
    expect(STATUS_LABELS.FINALIZED).toBe("Gestellt");
    expect(STATUS_LABELS.DRAFT).toBe("Entwurf");
    expect(STATUS_LABELS.CANCELLED).toBe("Storniert");
  });
});
