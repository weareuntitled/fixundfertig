import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InvoiceAttachmentsCard } from "./invoice-attachments-card";

vi.mock("@/lib/use-notifications", () => ({ useNotification: () => ({ notify: vi.fn() }) }));

const invoiceBody = { id: 7, customer_id: 1, attachments: [] };

afterEach(() => vi.unstubAllGlobals());

describe("InvoiceAttachmentsCard", () => {
  it("uploads a file and attaches it to the invoice", async () => {
    const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
      if (url === "/api/documents/upload") return Response.json({ id: 42, original_filename: "beleg.png" }, { status: 201 });
      if (url === "/api/invoices/7/attachments") return Response.json(invoiceBody, { status: 201 });
      return Response.json([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <InvoiceAttachmentsCard invoiceId={7} attachments={[]} />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("button", { name: /Anlage hochladen/ })).toBeInTheDocument();
    const file = new File(["x"], "beleg.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Anlage auswählen"), { target: { files: [file] } });

    await waitFor(() => {
      const attach = fetchMock.mock.calls.find(([url]) => url === "/api/invoices/7/attachments");
      expect(attach?.[1]?.body).toBe(JSON.stringify({ document_id: 42 }));
    });
  });
});
