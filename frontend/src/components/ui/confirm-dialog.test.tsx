import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./confirm-dialog";

function setup(props: Partial<React.ComponentProps<typeof ConfirmDialog>> = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(
    <ConfirmDialog open title="Rechnung erstellen?" message="Die Nummer wird jetzt vergeben." confirmLabel="Erstellen" onConfirm={onConfirm} onCancel={onCancel} {...props} />,
  );
  return { onConfirm, onCancel };
}

describe("ConfirmDialog", () => {
  it("names the step and what it does", () => {
    setup();
    expect(screen.getByRole("alertdialog", { name: "Rechnung erstellen?" })).toBeTruthy();
    expect(screen.getByText("Die Nummer wird jetzt vergeben.")).toBeTruthy();
  });

  it("confirms and cancels", () => {
    const { onConfirm, onCancel } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Erstellen" }));
    fireEvent.click(screen.getByRole("button", { name: "Abbrechen" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(2);
  });

  it("ignores everything while the step is running", () => {
    const { onConfirm, onCancel } = setup({ pending: true });
    fireEvent.click(screen.getByRole("button", { name: "Erstellen" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("renders nothing while closed", () => {
    setup({ open: false });
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });
});
