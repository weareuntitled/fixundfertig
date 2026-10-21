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
});
