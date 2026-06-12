import { useQuery } from "@tanstack/react-query";
import type { InvoiceDraft } from "./schemas/invoice";
import { useDebounce } from "@/hooks/use-debounce";

/**
 * Debounced query for the live PDF preview.
 * Returns a Blob (application/pdf) once the user pauses typing for `delay` ms.
 *
 * Backend: `POST /api/invoices/preview-pdf` — siehe `app/api/invoices.py`.
 */
export function useInvoicePreview(draft: InvoiceDraft, delay: number = 800) {
  const debounced = useDebounce(draft, delay);

  return useQuery({
    queryKey: ["invoice-preview", debounced],
    queryFn: async () => {
      const response = await fetch("/api/invoices/preview-pdf", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(debounced),
      });
      if (!response.ok) return null;
      return response.blob();
    },
    enabled: debounced.items.length > 0,
    staleTime: 60_000,
  });
}
