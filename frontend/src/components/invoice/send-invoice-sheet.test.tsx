import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SendInvoiceSheet } from "./send-invoice-sheet";

function setup(props: Partial<React.ComponentProps<typeof SendInvoiceSheet>> = {}) {
  const onSend = vi.fn();
  const onCancel = vi.fn();
  render(
    <SendInvoiceSheet
      open
      recipientName="Sisyphos Event GmbH"
      recipientEmail="buchhaltung@sisyphos.example"
      onSend={onSend}
      onCancel={onCancel}
      {...props}
    />,
  );
  return { onSend, onCancel };
}

describe("SendInvoiceSheet", () => {
  it("shows who gets the invoice", () => {
    setup();
    expect(screen.getByText("Sisyphos Event GmbH")).toBeTruthy();
    expect(screen.getByText("buchhaltung@sisyphos.example")).toBeTruthy();
  });

  it("sends the personal message without surrounding whitespace", () => {
    const { onSend } = setup();
    fireEvent.change(screen.getByLabelText("Persönliche Nachricht"), { target: { value: "  Danke für die Nacht!  " } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).toHaveBeenCalledWith("Danke für die Nacht!");
  });

  it("sends an empty message when nothing was typed", () => {
    const { onSend } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).toHaveBeenCalledWith("");
  });

  it("cancels from the button, the escape key and the backdrop", () => {
    const { onCancel } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Abbrechen" }));
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.mouseDown(screen.getByRole("dialog").parentElement as HTMLElement);
    expect(onCancel).toHaveBeenCalledTimes(3);
  });

  it("cannot be sent twice or dismissed while sending", () => {
    const { onSend, onCancel } = setup({ pending: true });
    fireEvent.click(screen.getByRole("button", { name: "Sende…" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onSend).not.toHaveBeenCalled();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("renders nothing while closed", () => {
    setup({ open: false });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
