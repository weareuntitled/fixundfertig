import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PdfPreviewModal } from "./pdf-preview-modal";

describe("PdfPreviewModal", () => {
  it("shows the generated PDF itself", () => {
    document.body.innerHTML = '<div id="portal-root"></div>';
    const pdfUrl = "blob:https://app.example.test/invoice.pdf";

    render(<PdfPreviewModal open pdfUrl={pdfUrl} invoiceNr="10057" onClose={() => {}} />);

    expect(screen.getByTitle("PDF-Rechnung 10057").getAttribute("src")).toBe(pdfUrl);
  });

  it("uses the server download for existing documents so their configured filename is retained", () => {
    render(<PdfPreviewModal open pdfUrl="blob:pdf" invoiceNr="10057" downloadUrl="/api/invoices/43/download" onClose={() => {}} />);
    const link = screen.getByRole("link", { name: "PDF herunterladen" });
    expect(link).toHaveAttribute("href", "/api/invoices/43/download");
    expect(link).not.toHaveAttribute("download");
  });
});
