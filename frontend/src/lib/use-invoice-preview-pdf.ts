import { useQuery } from "@tanstack/react-query";

/**
 * Lädt die PDF-Vorschau einer finalisierten Rechnung vom Server.
 *
 * Backend: `GET /api/invoices/{id}/preview-pdf` (siehe `app/api/invoices.py`).
 * Liefert application/pdf als Blob.
 */
export function useInvoicePreviewPdf(invoiceId: number | null) {
  return useQuery({
    queryKey: ["invoice-preview-pdf", invoiceId],
    queryFn: async () => {
      if (!invoiceId) return null;
      const response = await fetch(`/api/invoices/${invoiceId}/preview-pdf`, {
        credentials: "include",
      });
      if (!response.ok) return null;
      return response.blob();
    },
    enabled: invoiceId !== null,
    staleTime: 60_000,
  });
}
