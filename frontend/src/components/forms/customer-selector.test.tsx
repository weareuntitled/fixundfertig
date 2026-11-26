import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CustomerSelector } from "./customer-selector";

vi.mock("@/lib/use-customers", () => ({
  useCustomers: () => ({ data: [{ id: 7, name: "Sisyphos Event GmbH", vorname: "", nachname: "", email: "" }], isLoading: false }),
  useCreateCustomer: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

/**
 * Der Dialog „Neuen Kunden anlegen“ hält denselben Tastaturvertrag wie die
 * anderen Dialoge (#500): Fokus hinein, Tab bleibt drin, Escape schließt,
 * der Fokus kehrt zum Auslöser zurück.
 */
describe("CustomerSelector", () => {
  it("opens the customer dialog on the trigger and gives the focus back", () => {
    render(<CustomerSelector value={null} onChange={() => {}} />);
    const trigger = screen.getByRole("button", { name: "Neuen Kunden anlegen" });
    trigger.focus();
    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog", { name: "Neuen Kunden anlegen" });
    expect(dialog.contains(document.activeElement)).toBe(true);

    // Tab bleibt im Dialog.
    const last = screen.getByRole("button", { name: "Anlegen" });
    last.focus();
    fireEvent.keyDown(document.activeElement!, { key: "Tab" });
    expect(dialog.contains(document.activeElement)).toBe(true);

    // Escape schließt und der Fokus kehrt zum Auslöser zurück.
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("offers a 44 px target for the add button", () => {
    render(<CustomerSelector value={null} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Neuen Kunden anlegen" }).className).toContain("h-11");
  });
});
