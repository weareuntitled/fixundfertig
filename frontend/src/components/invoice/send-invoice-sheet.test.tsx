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
    expect(screen.getByRole("dialog").textContent).toContain("Sisyphos Event GmbH");
    expect(screen.getByRole("dialog").textContent).toContain("buchhaltung@sisyphos.example");
  });

  it("sends the personal message without surrounding whitespace", () => {
    const { onSend } = setup();
    fireEvent.change(screen.getByLabelText(/Persönliche Nachricht/), { target: { value: "  Danke für die Nacht!  " } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).toHaveBeenCalledWith("Danke für die Nacht!", false);
  });

  it("sends an empty message when nothing was typed", () => {
    const { onSend } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).toHaveBeenCalledWith("", false);
  });

  it("sends attached receipts by default and lets them be excluded", () => {
    const { onSend } = setup({ attachmentCount: 2 });
    const checkbox = screen.getByRole("checkbox", { name: /Belege mitschicken/ });
    expect(checkbox).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).toHaveBeenCalledWith("", true);

    onSend.mockClear();
    fireEvent.change(screen.getByLabelText(/Persönliche Nachricht/), { target: { value: "Danke" } });
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).toHaveBeenCalledWith("Danke", false);
  });

  it("keeps the typed message when the attachment count changes while open", () => {
    const props = { open: true, recipientName: "Sisyphos", onSend: vi.fn(), onCancel: vi.fn() };
    const { rerender } = render(<SendInvoiceSheet {...props} attachmentCount={1} />);
    fireEvent.change(screen.getByLabelText(/Persönliche Nachricht/), { target: { value: "Hallo" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /Belege mitschicken/ }));
    rerender(<SendInvoiceSheet {...props} attachmentCount={2} />);
    expect(screen.getByLabelText(/Persönliche Nachricht/)).toHaveValue("Hallo");
    expect(screen.getByRole("checkbox", { name: /Belege mitschicken/ })).not.toBeChecked();
  });

  it("checks the box when receipts appear while the dialog is open", () => {
    const props = { open: true, recipientName: "Sisyphos", onSend: vi.fn(), onCancel: vi.fn() };
    const { rerender } = render(<SendInvoiceSheet {...props} attachmentCount={0} />);
    rerender(<SendInvoiceSheet {...props} attachmentCount={1} />);
    expect(screen.getByRole("checkbox", { name: /Belege mitschicken/ })).toBeChecked();
  });

  it("cancels from the button, the escape key and the backdrop", () => {
    const { onCancel } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Abbrechen" }));
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.click(screen.getByRole("dialog").previousElementSibling as HTMLElement);
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
