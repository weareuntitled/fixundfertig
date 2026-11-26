/**
 * Keyboard contract every dialog on the quote and invoice pages keeps (#500):
 * focus moves into the dialog on open, Tab and Shift+Tab stay inside, Escape closes,
 * and focus goes back to the button that opened it.
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState, type ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { ConfirmDialog } from "./confirm-dialog";
import { PdfPreviewModal } from "./pdf-preview-modal";
import { LineItemDialog } from "@/components/forms/line-item-dialog";
import { SendInvoiceSheet } from "@/components/invoice/send-invoice-sheet";

type RenderDialog = (open: boolean, close: () => void) => ReactNode;

function Harness({ renderDialog }: { renderDialog: RenderDialog }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button">Davor</button>
      <button type="button" onClick={() => setOpen(true)}>
        Öffnen
      </button>
      {renderDialog(open, () => setOpen(false))}
    </>
  );
}

function openDialog(renderDialog: RenderDialog) {
  document.body.innerHTML = '<div id="portal-root"></div>';
  render(<Harness renderDialog={renderDialog} />);
  const trigger = screen.getByRole("button", { name: "Öffnen" });
  trigger.focus();
  fireEvent.click(trigger);
  return trigger;
}

const CASES: { name: string; role: "dialog" | "alertdialog"; first: string; last: string; render: RenderDialog }[] = [
  {
    name: "ConfirmDialog",
    role: "alertdialog",
    first: "Abbrechen",
    last: "Annehmen",
    render: (open, close) => (
      <ConfirmDialog open={open} title="Angebot annehmen?" message="Text" confirmLabel="Annehmen" onConfirm={close} onCancel={close} />
    ),
  },
  {
    name: "PdfPreviewModal",
    role: "dialog",
    first: "Schließen",
    last: "Schließen",
    render: (open, close) => <PdfPreviewModal open={open} pdfUrl={null} invoiceNr="A-1" onClose={close} />,
  },
  {
    name: "LineItemDialog",
    role: "dialog",
    first: "Beschreibung",
    last: "Abbrechen",
    render: (open, close) => <LineItemDialog open={open} onSave={close} onCancel={close} />,
  },
  {
    name: "SendInvoiceSheet",
    role: "dialog",
    first: "Persönliche Nachricht (optional)",
    last: "Senden",
    render: (open, close) => <SendInvoiceSheet open={open} recipientName="Kunde" onSend={close} onCancel={close} />,
  },
];

function byName(name: string) {
  return screen.queryByRole("button", { name }) ?? screen.queryByRole("link", { name }) ?? screen.getByLabelText(name);
}

describe.each(CASES)("$name keyboard", ({ role, first, last, render: renderDialog }) => {
  it("moves focus into the dialog when it opens", () => {
    openDialog(renderDialog);
    const dialog = screen.getByRole(role);
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("keeps Tab and Shift+Tab inside the dialog", () => {
    openDialog(renderDialog);
    const firstEl = byName(first);
    const lastEl = byName(last);
    lastEl.focus();
    fireEvent.keyDown(document.activeElement!, { key: "Tab" });
    expect(document.activeElement).toBe(firstEl);
    fireEvent.keyDown(document.activeElement!, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(lastEl);
  });

  it("pulls focus back when it lands behind the dialog", () => {
    openDialog(renderDialog);
    act(() => {
      screen.getByRole("button", { name: "Davor", hidden: true }).focus();
    });
    expect(screen.getByRole(role).contains(document.activeElement)).toBe(true);
  });

  it("closes on Escape and gives focus back to the button that opened it", () => {
    const trigger = openDialog(renderDialog);
    act(() => {
      fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    });
    expect(screen.queryByRole(role)).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
});
